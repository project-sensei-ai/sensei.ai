"""
A Google Meet participant named Sensei.

Playwright drives a headless Chromium into the call as a guest, switches on
live captions, and reads them off the page. Each finished caption line goes
through the same `listener.consider` as the browser companion; anything the
agent decides to say is typed into the meeting chat, where every participant
sees it with the source named.

Why chat and not voice: a spoken reply needs a virtual audio device wired
into the browser, which is a per-machine setup no judge can reproduce. The
chat panel is visible to everyone in the room, is logged by Meet, and works
on any host. Voice is the obvious next step once a transport exists.

Honest about its fragility: Google changes Meet's DOM without notice, so the
caption selectors are a list of candidates, and every stage reports its state
to the meeting record (`bot_status`) so a failure is visible on the Meetings
page rather than silent.
"""
import asyncio
import re
from datetime import datetime, timezone
from uuid import uuid4

from db.membership import visible_sources
from meetings import listener

BOT_NAME = "Sensei (AI colleague)"

# What the caption pane has looked like across recent Meet builds. Checked in
# order; the first that yields anything wins for the rest of the call.
CAPTION_SCRIPTS = [
    # 2025: each caption block = speaker name element + text element
    """(() => {
        const out = [];
        const blocks = document.querySelectorAll('div[jsname="tgaKEf"], div.a4cQT');
        for (const b of blocks) {
            const name = b.querySelector('.NWpY1d, .zs7s8d, .KcIKyf')?.textContent?.trim();
            const text = b.querySelector('.bh44bd, .iTTPOb, .ygicle')?.textContent?.trim();
            if (text) out.push({speaker: name || 'Someone', text});
        }
        return out;
    })()""",
    # Generic: the captions region is aria-labelled; take name/text pairs by structure
    """(() => {
        const region = document.querySelector('[aria-label="Captions"], [aria-label="Live captions"]');
        if (!region) return [];
        const out = [];
        for (const row of region.querySelectorAll(':scope > div, :scope div[role="presentation"] > div')) {
            const spans = Array.from(row.querySelectorAll('span, div')).map(e => e.textContent.trim()).filter(Boolean);
            if (spans.length >= 2) out.push({speaker: spans[0].slice(0, 60), text: spans.slice(1).join(' ')});
            else if (spans.length === 1 && spans[0].length > 3) out.push({speaker: 'Someone', text: spans[0]});
        }
        return out;
    })()""",
]


async def _snap(page, meeting_id: str, tag: str) -> None:
    """A screenshot per stage, so a failure can be looked at rather than guessed."""
    try:
        import os
        from core.config import settings
        folder = os.path.join(settings.CHROMA_PERSIST_DIR, "meet-bot")
        os.makedirs(folder, exist_ok=True)
        await page.screenshot(path=os.path.join(folder, f"{meeting_id[:8]}-{tag}.png"))
    except Exception:
        pass


async def _set_status(db, meeting_id: str, status: str, detail: str = "") -> None:
    await db.meetings.update_one(
        {"_id": meeting_id},
        {"$set": {"bot_status": status, "bot_detail": detail[:300],
                  "bot_updated_at": datetime.now(timezone.utc)}},
    )
    print(f"[meet-bot] {meeting_id[:8]} {status} {detail[:120]}")


async def _click_if_present(page, selectors: list[str], timeout: int = 1500) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.click()
            return True
        except Exception:
            continue
    return False


async def _post_to_chat(page, text: str) -> bool:
    """Open the chat panel if needed and send one message."""
    try:
        box = page.locator('textarea[aria-label*="Send a message"], textarea[placeholder*="Send a message"]').first
        if not await box.is_visible():
            await _click_if_present(page, [
                'button[aria-label*="Chat with everyone"]', 'button[aria-label*="Open chat"]',
                'button[aria-label*="chat"]',
            ], timeout=3000)
            await box.wait_for(state="visible", timeout=5000)
        await box.fill(text[:1500])
        await box.press("Enter")
        return True
    except Exception as exc:
        print(f"[meet-bot] chat post failed: {exc.__class__.__name__}")
        return False


async def run_bot(db, chroma_client, meeting_id: str, user_id: str) -> None:
    doc = await db.meetings.find_one({"_id": meeting_id})
    if not doc:
        return
    url = doc.get("meet_url")
    ws_id = doc["workspace_id"]
    allowed = await visible_sources(db, ws_id, user_id)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        await _set_status(db, meeting_id, "error", "Playwright is not installed on this server")
        return

    await _set_status(db, meeting_id, "launching", url or "")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--disable-blink-features=AutomationControlled",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            ctx = await browser.new_context(
                permissions=["microphone", "camera"],
                viewport={"width": 1280, "height": 800},
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
                locale="en-US",
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(4000)

            # Guest entry: name, mic and camera off, ask to join. Meet shows the
            # guest door only while the host is in the call; before that it
            # says "You can't join this video call", and a sign-in wall means
            # the meeting is restricted to the organisation.
            await _set_status(db, meeting_id, "at the door", "filling in a name and asking to join")
            name_box = None
            for _ in range(20):        # up to ~2 minutes for the host to open the room
                body = (await page.evaluate("document.body.innerText")) or ""
                if "can't join this video call" in body or "can’t join this video call" in body:
                    await _set_status(db, meeting_id, "waiting for the host",
                                      "Meet says nobody can join yet — the host needs to be in the call first")
                    await page.wait_for_timeout(6000)
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(4000)
                    continue
                if "Sign in" in body and "Ask to join" not in body and "Join now" not in body:
                    await _set_status(db, meeting_id, "error",
                                      "This meeting requires a Google sign-in, so a guest cannot join. "
                                      "Turn on 'Guests can join' (host controls → Access → Open), or use companion mode.")
                    await browser.close()
                    return
                loc = page.locator('input[aria-label*="name" i], input[placeholder*="name" i]').first
                if await loc.count() > 0 and await loc.is_visible():
                    name_box = loc
                    break
                await page.wait_for_timeout(3000)
            if name_box is None:
                await _set_status(db, meeting_id, "error",
                                  "Meet never offered the guest door. The host must be in the call, and guests must be allowed.")
                await browser.close()
                return
            await name_box.fill(BOT_NAME)
            await _click_if_present(page, ['[aria-label*="Turn off microphone"]', '[data-tooltip*="microphone"]'])
            await _click_if_present(page, ['[aria-label*="Turn off camera"]', '[data-tooltip*="camera"]'])
            joined = await _click_if_present(page, [
                'button:has-text("Ask to join")', 'button:has-text("Join now")', 'button:has-text("Join")',
            ], timeout=5000)
            if not joined:
                await _set_status(db, meeting_id, "error", "No join button found on the Meet page")
                await browser.close()
                return

            await _set_status(db, meeting_id, "waiting to be admitted", "the host needs to let Sensei in")
            await _snap(page, meeting_id, "asked")
            # Google's answer to an automated guest is usually immediate: a
            # refusal page, or a page that renders nothing at all. Say so now
            # rather than after four minutes of silence.
            await page.wait_for_timeout(5000)
            after = (await page.evaluate("document.body.innerText")) or ""
            if "can't join this video call" in after or "can’t join this video call" in after or not after.strip():
                await _snap(page, meeting_id, "refused")
                await _set_status(db, meeting_id, "error",
                                  "Google Meet refused the automated guest right after it knocked. This happens for "
                                  "unsigned-in browsers driven by automation. Use companion mode beside the call — "
                                  "same judgement, and it works.")
                await browser.close()
                return
            admitted = False
            for _ in range(120):   # up to ~4 minutes
                if await page.locator('[aria-label*="Leave call"]').count() > 0:
                    admitted = True
                    break
                # A request made before the host arrived is dropped by Meet;
                # the door comes back. Knock again whenever it does.
                body = (await page.evaluate("document.body.innerText")) or ""
                if _ % 10 == 0:
                    await _snap(page, meeting_id, "waiting")
                if "Ask to join" in body or "Join now" in body:
                    await _click_if_present(page, ['button:has-text("Ask to join")', 'button:has-text("Join now")'], timeout=2000)
                elif "can't join this video call" in body or "can’t join this video call" in body or "Return to home screen" in body:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(4000)
                    box = page.locator('input[aria-label*="name" i], input[placeholder*="name" i]').first
                    if await box.count() > 0:
                        await box.fill(BOT_NAME)
                        await _click_if_present(page, ['button:has-text("Ask to join")', 'button:has-text("Join now")'], timeout=5000)
                live = await db.meetings.find_one({"_id": meeting_id}, {"status": 1})
                if not live or live.get("status") != "live":
                    await browser.close()
                    await _set_status(db, meeting_id, "left", "meeting ended before admission")
                    return
                await page.wait_for_timeout(2000)
            if not admitted:
                await _snap(page, meeting_id, "not-admitted")
                await _set_status(db, meeting_id, "error", "Nobody admitted Sensei within four minutes")
                await browser.close()
                return

            await _set_status(db, meeting_id, "in the call", "turning on captions")
            await page.wait_for_timeout(2000)
            if not await _click_if_present(page, ['[aria-label*="Turn on captions"]', 'button:has-text("Turn on captions")'], timeout=4000):
                await page.keyboard.press("c")   # Meet's caption shortcut
            await page.wait_for_timeout(1500)
            await _post_to_chat(page, "Sensei here — I'll stay quiet unless someone asks me, or says something the project docs contradict.")
            await _snap(page, meeting_id, "in-call")
            await _set_status(db, meeting_id, "listening", "reading live captions")

            seen: dict[str, str] = {}       # speaker -> last full text committed
            script_idx = 0
            idle_polls = 0
            while True:
                live = await db.meetings.find_one({"_id": meeting_id}, {"status": 1, "transcript": {"$slice": -6}})
                if not live or live.get("status") != "live":
                    break
                if await page.locator('[aria-label*="Leave call"]').count() == 0:
                    await _set_status(db, meeting_id, "left", "the call ended or Sensei was removed")
                    break

                captions = []
                for i in range(len(CAPTION_SCRIPTS)):
                    idx = (script_idx + i) % len(CAPTION_SCRIPTS)
                    try:
                        captions = await page.evaluate(CAPTION_SCRIPTS[idx])
                    except Exception:
                        captions = []
                    if captions:
                        script_idx = idx
                        break

                # A caption line keeps growing while someone talks. Commit it
                # when it stops changing between two polls — that is "finished".
                fresh: list[dict] = []
                current = {c["speaker"]: c["text"] for c in captions if c.get("text")}
                for speaker, text in current.items():
                    prev = seen.get(speaker)
                    if prev == text:
                        continue
                    if prev and text.startswith(prev):
                        seen[speaker] = text
                        continue
                    if prev and not text.startswith(prev):
                        fresh.append({"speaker": speaker, "text": prev})
                    seen[speaker] = text
                if not captions and seen:
                    idle_polls += 1
                    if idle_polls >= 3:
                        for speaker, text in seen.items():
                            fresh.append({"speaker": speaker, "text": text})
                        seen = {}
                        idle_polls = 0
                else:
                    idle_polls = 0

                for u in fresh:
                    text = u["text"].strip()
                    if len(text) < 4 or u["speaker"].lower().startswith("sensei"):
                        continue
                    utt = {"speaker": u["speaker"][:80], "text": text[:2000],
                           "at": datetime.now(timezone.utc).isoformat()}
                    await db.meetings.update_one({"_id": meeting_id}, {"$push": {"transcript": utt}})
                    context = "\n".join(f"{x['speaker']}: {x['text']}" for x in (live.get("transcript") or []))
                    try:
                        reply = await listener.consider(ws_id, chroma_client, text, context, allowed)
                    except Exception as exc:
                        reply = listener.Reply(kind="silent", reason=f"could not judge: {exc.__class__.__name__}", trigger=text)
                    reply_doc = {"_id": uuid4().hex, **reply.to_doc()}
                    await db.meetings.update_one({"_id": meeting_id}, {"$push": {"replies": reply_doc}})
                    if reply.kind != "silent":
                        srcs = ", ".join(sorted({c.get("source_label", "") for c in reply.citations if c.get("source_label")}))
                        prefix = "" if reply.kind == "answer" else "Small correction — "
                        suffix = f"  (source: {srcs})" if srcs else ""
                        await _post_to_chat(page, f"{prefix}{reply.text}{suffix}")

                await page.wait_for_timeout(1500)

            await _click_if_present(page, ['[aria-label*="Leave call"]'], timeout=2000)
            await browser.close()
            await _set_status(db, meeting_id, "left", "")
    except Exception as exc:
        await _set_status(db, meeting_id, "error", f"{exc.__class__.__name__}: {str(exc)[:200]}")
