"""
Draws docs/assets/architecture.svg (and .png via Playwright).

    python docs/assets/make_diagram.py

Hand-laid boxes rather than a graph layout, because the reader should see
the shape of the argument — triggers on the left, judgement in the middle,
access on the right — not whatever a layout engine finds shortest.
"""
import os
import textwrap

W, H = 1600, 1180
OUT = os.path.join(os.path.dirname(__file__), "architecture")

INK, MUTED, BG = "#14161a", "#5f6570", "#fbfbfd"
BLUE, BLUE_S = "#eef2ff", "#7c8ff5"
PINK, PINK_S = "#fdf0f6", "#e07aa8"
GREEN, GREEN_S = "#eefaf3", "#38a36f"
AMBER, AMBER_S = "#fff7e8", "#e0a23a"
PURPLE, PURPLE_S = "#f3efff", "#8f71cf"
GREY, GREY_S = "#f3f4f7", "#c3c8d2"

parts = []


def text(x, y, s, size=13, weight=400, fill=INK, anchor="start"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{fill}">{s}</text>')


def box(x, y, w, h, title, lines, fill=GREY, stroke=GREY_S, dashed=False, badge=None):
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/>')
    text(x + w / 2, y + 24, title, 14.5, 600, INK, "middle")
    if badge:
        # Bottom-right, where it cannot collide with the title.
        parts.append(f'<rect x="{x + w - 92}" y="{y + h - 24}" width="84" height="18" rx="9" fill="{stroke}"/>')
        text(x + w - 50, y + h - 11, badge, 10.5, 700, "#fff", "middle")
    yy = y + 44
    for ln in lines:
        text(x + w / 2, yy, ln, 12, 400, MUTED, "middle")
        yy += 17


def arrow(x1, y1, x2, y2, color=GREY_S, marker="a"):
    parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="1.8" fill="none" marker-end="url(#{marker})"/>')


def section(x, y, label):
    text(x, y, label, 12, 700, MUTED)


# ── Header ────────────────────────────────────────────────────────────────────
parts.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
text(44, 50, "Sensei — a colleague you onboard, not a chatbot you prompt", 27, 700)
text(44, 78, "Strands Agents SDK.   Pink = acting on its own.   Amber = a gate that says no.   Green = tools it was handed.", 14, 400, MUTED)

# ── 1. Triggers ───────────────────────────────────────────────────────────────
section(44, 118, "1 — WHAT SETS IT OFF")
col = 44
box(col, 130, 300, 86, "A person asks", ["chat, streamed, tool calls narrated"], BLUE, BLUE_S)
box(col, 228, 300, 86, "An owner adds a teammate", ["nobody asks for anything"], PINK, PINK_S, badge="unprompted")
box(col, 326, 300, 86, "A source finishes indexing", ["the corpus changed"], PINK, PINK_S, badge="unprompted")
box(col, 424, 300, 86, "Something is said in a meeting or Slack", ["companion mic, the Meet bot, or a channel"], BLUE, BLUE_S)
box(col, 522, 300, 86, "The clock", ["sources re-read on a schedule"], PINK, PINK_S, badge="unprompted")

# ── 2. The judgement ──────────────────────────────────────────────────────────
section(392, 118, "2 — ONE STRANDS AGENT LOOP, EQUIPPED PER TURN")
parts.append(f'<rect x="392" y="130" width="720" height="478" rx="12" fill="#fff" stroke="{GREY_S}" stroke-width="1.6"/>')
text(752, 158, "build_colleague()  →  Agent(tools=[…], hooks=[WriteGate])", 13, 600, INK, "middle")
text(752, 176, "the index tools · live Jira · work tools · the dozen most relevant granted tools for this question", 11.5, 400, MUTED, "middle")

box(408, 196, 220, 118, "Index tools", ["search_project_docs", "list_project_knowledge", "who_did_what — commits,", "PRs, tickets by person"], BLUE, BLUE_S)
box(642, 196, 220, 118, "Live tools", ["jira_search · jira_issue", "status read NOW, never", "from the index", "(rides on the Confluence token)"], BLUE, BLUE_S)
box(876, 196, 220, 118, "Work tools", ["create_spreadsheet → .xlsx", "write_document → .docx", "files attached to the reply"], BLUE, BLUE_S)

box(408, 330, 454, 118, "Granted tools  (MCPClient, per server prefix)", ["github_list_issues · github_issue_write · zapier_gmail_send · …",
    "every tool classified read / write on connection", "descriptions trimmed, top-12 by relevance offered per turn",
    "sessions pooled across turns, closed off the event loop"], GREEN, GREEN_S)
box(876, 330, 220, 118, "WriteGate", ["BeforeToolCallEvent hook", "cancel_tool unless the owner", "allowed writes on that grant", "— the agent says so, plainly"], AMBER, AMBER_S, badge="gate")

box(408, 464, 220, 128, "Onboarding brief", ["Graph: scout → facts → people", "structured_output → typed brief", "+ what the sources can't say", "research once, compose per person"], PINK, PINK_S, badge="unprompted")
box(642, 464, 220, 128, "Gap hunter · Change watch", ["audits for what is ABSENT", "drafts what it can, flags inference", "diffs first; a model only if", "something actually moved"], PINK, PINK_S, badge="unprompted")
box(876, 464, 220, 128, "Meeting listener", ["addressed by name → answer", "claim + typed verdict + conf ≥ 0.8", "+ citation → correction", "anything else → silent, with why"], AMBER, AMBER_S, badge="gate")

for y in (173, 271, 369, 467, 565):
    arrow(344, y, 392, y)

# ── 3. Access ─────────────────────────────────────────────────────────────────
section(1160, 118, "3 — WHAT THE OWNER HANDED IT")
box(1160, 130, 396, 122, "Sources  (read, indexed)", ["GitHub — 19 data types", "Confluence — one named space", "Jira — one project (status stays live)",
    "URLs · files · meeting notes", "chunk 800 · provenance header embedded"], BLUE, BLUE_S)
box(1160, 266, 396, 108, "Tool grants  (use)", ["any MCP server: HTTP · SSE · stdio", "owner's credential, encrypted at rest",
    "read / write per tool · writes off by default", "revocation takes effect next turn"], GREEN, GREEN_S)
box(1160, 388, 396, 96, "Per person", ["owner's allowlist is the only way in",
    "each member answered from their own", "subset of sources — filtered inside the vector query"], PURPLE, PURPLE_S)
box(1160, 498, 396, 110, "Trust page", ["each credential: floor (what we read)", "beside ceiling (what it COULD reach)",
    "every granted tool by name and class", "what it never does — and it's true"], AMBER, AMBER_S)

arrow(1112, 240, 1160, 200, GREEN_S, "ag")
arrow(1112, 380, 1160, 320, GREEN_S, "ag")

# ── 4. Serving + state ────────────────────────────────────────────────────────
section(44, 660, "4 — SERVING")
box(44, 672, 300, 96, "FastAPI · one container · one URL", ["/api/* + built SPA", "SSE: tool calls, tokens, files", "Caddy for HTTPS on EC2"], GREY, GREY_S)
box(44, 782, 300, 96, "Model backends, one flag", ["Claude Haiku 4.5 (Anthropic) first", "Groq free tier as the fallback chain", "Bedrock · Ollama · a limit moves the call on"], GREY, GREY_S)
box(44, 892, 300, 96, "Auth", ["JWT in an httpOnly cookie", "single-use invites bound to an email", "passwords never emailed"], GREY, GREY_S)

section(392, 660, "5 — STATE")
box(392, 672, 340, 130, "MongoDB", ["users · members · sources · tool_grants", "briefs · gap_reports · drafts · unanswered",
    "meetings · artifacts · change_digests", "research_cache · token_usage"], GREY, GREY_S)
box(392, 816, 340, 96, "ChromaDB  (per workspace)", ["ws_{id}: chunks + provenance metadata", "data_type lets meetings be excluded", "from claim checks — hearsay ≠ docs"], GREY, GREY_S)
box(392, 926, 340, 62, "Disk", ["artifacts/ (xlsx, docx) · uploads/"], GREY, GREY_S)

section(772, 660, "6 — WHAT COMES OUT")
box(772, 672, 340, 96, "Answers", ["plain sentences, the key facts in bold", "the steps it took, kept on the message", "sources shown · freshness stated · refusals stated"], BLUE, BLUE_S)
box(772, 782, 340, 96, "Artifacts", ["a brief · a drafted page · a digest", "a spreadsheet · a document", "meeting notes: decisions, actions"], PINK, PINK_S)
box(772, 892, 340, 96, "The ledger", ["what it could not answer", "one human reply → indexed forever", "answered-without-a-human, week on week"], PINK, PINK_S)

section(1160, 660, "7 — WHERE IT SPEAKS")
box(1160, 672, 396, 96, "Web chat", ["the tool trail, live", "downloads attached to the reply"], BLUE, BLUE_S)
box(1160, 782, 396, 96, "Meetings", ["companion: browser speech → text → judgement", "Google Meet bot: captions in, chat replies out"], BLUE, BLUE_S)
box(1160, 892, 396, 96, "Slack (connected)", ["mention or DM → always answers, in the thread", "an unaddressed question → only with a citation", "messages indexed as they arrive · Teams adapter ready"], BLUE, BLUE_S)

text(44, 1060, "Strands surface used:  Agent · @tool · MCPClient · hooks (BeforeToolCallEvent) · multiagent.GraphBuilder · structured_output_async · stream_async · AnthropicModel / OpenAIModel · AfterModelCallEvent failover · S3SessionManager",
     12.5, 500, MUTED)
text(44, 1084, "Every gate is code, not prompt: writes are cancelled in the hook, members are filtered in the vector query, corrections need a typed verdict, a floor and a citation.",
     12.5, 400, MUTED)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       'font-family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif">'
       '<defs>'
       f'<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{GREY_S}"/></marker>'
       f'<marker id="ag" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN_S}"/></marker>'
       '</defs>' + "".join(parts) + "</svg>")

with open(OUT + ".svg", "w") as f:
    f.write(svg)
print("wrote", OUT + ".svg")

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg.set_content(f'<html><body style="margin:0">{svg}</body></html>')
        pg.screenshot(path=OUT + ".png", full_page=True)
        b.close()
    print("wrote", OUT + ".png")
except Exception as exc:
    print("png skipped:", exc)
