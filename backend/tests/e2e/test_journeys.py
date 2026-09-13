"""
End-to-end journeys, through a real browser against a running server.

Kept apart from the unit suite because it needs both: the unit tests run in half
a second with no dependencies, these need `uvicorn main:app` on :8000 and a
model provider that answers.

    python -m pytest tests/e2e -q --base-url http://localhost:8000
"""
import os
import re
import uuid

import pytest
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
OWNER_EMAIL = "judge@sensei.demo"
OWNER_PASSWORD = os.environ.get("E2E_OWNER_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not OWNER_PASSWORD, reason="set E2E_OWNER_PASSWORD to run the browser journeys"
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def sign_in(browser, email: str, password: str):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = ctx.new_page()
    page.goto(f"{BASE}/login")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard", timeout=20000)
    return ctx, page


def test_owner_sees_work_the_agent_did_unprompted(browser):
    """The dashboard's whole argument is the 'on its own' tag."""
    ctx, page = sign_in(browser, OWNER_EMAIL, OWNER_PASSWORD)
    expect(page.get_by_text("What the agent has been doing")).to_be_visible()
    expect(page.get_by_text("on its own").first).to_be_visible(timeout=10000)
    ctx.close()


def test_gaps_separate_what_it_can_write_from_what_it_cannot(browser):
    ctx, page = sign_in(browser, OWNER_EMAIL, OWNER_PASSWORD)
    page.goto(f"{BASE}/gaps")
    expect(page.get_by_text("What nobody wrote down")).to_be_visible(timeout=15000)
    # Both halves must be present: offering to write everything would mean the
    # agent is not actually judging whether it can.
    expect(page.get_by_role("button", name=re.compile("Write it for me")).first).to_be_visible()
    expect(page.get_by_text(re.compile("needs a person")).first).to_be_visible()
    ctx.close()


def test_trust_states_the_ceiling_not_just_the_floor(browser):
    ctx, page = sign_in(browser, OWNER_EMAIL, OWNER_PASSWORD)
    page.goto(f"{BASE}/trust")
    expect(page.get_by_text("What the agent can reach")).to_be_visible(timeout=15000)
    expect(page.get_by_text("The credential could reach").first).to_be_visible()
    expect(page.get_by_text("What it never does")).to_be_visible()
    ctx.close()


def test_chat_narrates_its_tools_then_streams(browser):
    ctx, page = sign_in(browser, OWNER_EMAIL, OWNER_PASSWORD)
    page.goto(f"{BASE}/chat")
    box = page.locator('textarea[placeholder*="Ask anything"]')
    if not box.count():
        # No history at all — start one.
        page.get_by_role("button", name="New chat").first.click()
    expect(box).to_be_visible(timeout=15000)
    box.fill("Which sources are indexed for this project?")
    box.press("Enter")
    # The tool trail must appear before the answer — that ordering is the
    # feature, not an implementation detail.
    expect(page.get_by_text(re.compile("Taking stock|Searching the project"))).to_be_visible(timeout=45000)
    page.wait_for_timeout(20000)
    assert len(page.inner_text("body")) > 500
    ctx.close()


def test_a_member_joins_by_invitation_and_gets_less(browser):
    """
    The whole access model in one journey: the owner adds an address, the
    invitee sets their own password, and what they land in is read-only.
    """
    ctx, page = sign_in(browser, OWNER_EMAIL, OWNER_PASSWORD)
    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"

    page.goto(f"{BASE}/dashboard")
    page.fill('input[placeholder*="teammate@"]', email)
    page.get_by_role("button", name="Add").click()

    # No mail provider configured, so the owner is handed the link directly —
    # which is also how a reviewer exercises this without an inbox.
    expect(page.get_by_role("button", name=re.compile("Copy link"))).to_be_visible(timeout=15000)

    invite_url = page.evaluate("""() => {
        const m = document.body.innerHTML.match(/\\/join\\?token=[A-Za-z0-9_-]+/);
        return m ? m[0] : null;
    }""")
    if not invite_url:
        # The link lives behind the copy button; read it from the API instead.
        invite_url = page.evaluate("""async () => {
            const r = await fetch('/api/workspaces/members', {credentials:'include'});
            const d = await r.json();
            const m = d.members.find(x => x.invite_url);
            return m ? new URL(m.invite_url).pathname + new URL(m.invite_url).search : null;
        }""")
    assert invite_url, "the owner was never shown an invite link"

    member_ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    mpage = member_ctx.new_page()
    mpage.goto(f"{BASE}{invite_url}")
    expect(mpage.get_by_text(re.compile(r"^Join ", re.I)).first).to_be_visible(timeout=15000)
    # The invite names the address it was issued to — a link alone is not access.
    expect(mpage.get_by_text(email, exact=True)).to_be_visible()
    mpage.fill('input[type="password"]', "MemberChosen!123")
    mpage.get_by_role("button", name=re.compile("Set password and join")).click()
    mpage.wait_for_url("**/dashboard", timeout=20000)

    # A member manages nothing.
    mpage.goto(f"{BASE}/sources")
    expect(mpage.get_by_text("Read-only")).to_be_visible(timeout=15000)
    assert mpage.get_by_role("button", name="Add source").count() == 0

    # And the onboarding wizard is not theirs, even by URL.
    mpage.goto(f"{BASE}/onboarding")
    mpage.wait_for_timeout(2000)
    assert "/onboarding" not in mpage.url, "a member reached the owner's wizard"

    # Clean up so repeated runs do not litter the demo workspace.
    page.evaluate("""async (email) => {
        const r = await fetch('/api/workspaces/members', {credentials:'include'});
        const d = await r.json();
        const m = d.members.find(x => x.email === email);
        if (m) await fetch('/api/workspaces/members/' + m.user_id,
                           {method:'DELETE', credentials:'include'});
    }""", email)

    member_ctx.close()
    ctx.close()
