# Testing Sensei

Written for: whoever is reviewing this. Everything below is real — the sample
project was built through the same API a customer would use, and the numbers
are what the agent actually produced.

---

## Two projects, two owners

| | Owner | Password | Project |
|---|---|---|---|
| Realistic team | `maya@apollo.demo` | `Apollo-Demo-2026!` | **Apollo Delivery** — a last-mile dispatch platform: a GitHub repo, a Confluence space of runbooks and decisions, and GitHub tools with writes allowed |
| This codebase | `judge@sensei.demo` | `Demo-miwVU8NczE6N` | **Sensei Demo Project** — Sensei's own docs, repo and Confluence; GitHub tools connected read-only |

Members of Apollo, same password, who see it as teammates:
`priya@apollo.demo` and `ravi@apollo.demo`.

URL: `<LIVE_URL>` ← fill in after deploying, or run locally (§6).

No AWS account, Google account or credential of your own is needed.

---

## 1. Five minutes, as Maya

**Tools.** One GitHub connection, 47 tools, 28 read and 19 write. Writes are
allowed on this project — read the panel that says what that means and does
not mean. Open the tool list; every tool is classified.

**Chat.** Ask, in this order:

1. *Who is on call the week of 15 September, and who is the release captain?*
   — cited from the Confluence on-call page.
2. *What has Daniel Okafor worked on recently?* — watch the tool trail say
   "Reading the activity records": that is `who_did_what` over commits and PRs,
   not a search over prose.
3. *List the open issues and pull requests in apollo-delivery-service and put
   them in a spreadsheet with number, title, state and author.* — the trail
   shows GitHub tools running, then "Building the spreadsheet", then a
   download chip. Open the `.xlsx`.
4. *Create a GitHub issue titled "Assign an owner to notify-service", body
   from the team directory page.* — it does, and links it. (Then look at the
   repo: it is there.)

**Meetings.** Start a companion meeting. Type as different speakers — the
speaker box is editable — or use the microphone in Chrome:

- `Ravi`: *We deploy Apollo to us-east-1.* → a correction, citing the
  architecture page and ADR-003, with its confidence shown.
- `Ravi`: *The primary database is PostgreSQL 15 on RDS.* → silence, and the
  small grey line says why: supported by the sources.
- `Priya`: *Sensei, who owns the routing worker?* → an answer, spoken aloud
  if the speaker icon is on.
- `Priya`: *Lets grab lunch after this.* → silence: not a factual assertion.

End the meeting. Within a minute the notes appear — summary, decisions, action
items — and the meeting is a source. Ask in chat: *What was said about the
deployment region in the architecture review?* It cites the meeting, and it
reports the correction, not just the wrong claim.

**Trust.** The credential ceilings, the tools by class, the write switch, and
the "never" list — which changed wording when writes were allowed, because it
has to stay true.

## 2. As Priya (a member)

Log in as `priya@apollo.demo`. Her **brief** was written when Maya added her,
before she first logged in. Sources and Tools are read-only. Chat works the
same; her questions she could not get answered appear in her own **Answers**
ledger only.

Try: *Create an issue…* — it still works, because Maya allowed writes on the
connection, and the agent only writes when a person asks. Then, as Maya,
switch the GitHub connection to read-only and try again as Priya: the trail
shows the attempt, and the answer explains the refusal and who can lift it.

## 3. As the judge account

The **Sensei Demo Project** is this codebase describing itself. The GitHub
tools here are read-only, so "create an issue" shows the refusal path without
touching anything. **Gaps** shows what this project failed to document, with
three drafts on offer. **Answers** has a worked ledger example.

## 4. The Google Meet bot

On **Meetings**, choose *Join a Google Meet*, paste a meet link, and send it.
A headless browser joins as "Sensei (AI colleague)"; admit it. It turns on
captions, reads them, and posts answers and corrections into the meeting
chat, with the source named. Each step it takes is reported on the page
(`bot: waiting to be admitted`, `bot: listening`), because Google changes
Meet's markup without notice and a silent failure would be worse than a
visible one.

This needs a server that can run Chromium (the container image includes it)
and a Meet that allows guests. If your organisation's Meet requires a signed-in
Google account, the bot reports that and stops.

## 5. What is not built

Stated so nothing in the demo is mistaken for more than it is.

- **Voice in Google Meet.** The bot speaks in the meeting chat. Speaking aloud
  needs a virtual audio device wired into the browser; the companion mode
  speaks aloud on the device running it.
- **Teams and Slack** — the channel abstraction and the speak-or-stay-quiet
  rule are written and tested; no transport is connected.
- **Per-item ACLs** — visibility is per source per member, not per document.
- **Jira on the sample site** — the Atlassian site used for the demo has
  Confluence but not Jira, so the live Jira tools report exactly that. Connect
  a site with Jira and they light up.

## 6. Running it locally

```bash
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # MONGO_DB, JWT_SECRET, SECRET_ENCRYPTION_KEY, GROQ_API_KEY, DEBUG=true
uvicorn main:app --port 8000

cd frontend && npm install && npm run dev    # second terminal
```

http://localhost:5173. No AWS account needed — `LLM_BACKEND` defaults to Groq.

**Tests:** `cd backend && python -m pytest -q` — 48 tests, no model calls,
under half a second. They cover the judgement: which tools are permitted,
which are offered, and when the agent speaks in a meeting.

**Rebuilding the sample project:** `python scripts/seed_confluence.py <ws> SD`
writes the Apollo pages into a Confluence space; `python scripts/seed_apollo.py`
creates Maya's project, sources, tool grant and team through the API.

## 7. Connecting your own

As an owner:

- **Sources** — GitHub (a PAT), Confluence or Jira (an Atlassian API token;
  the same token serves both), files, URLs.
- **Tools** — any MCP server. Presets for GitHub, Zapier and Sentry fill the
  URL; paste your token as the Authorization header. It connects once to list
  the tools before anything is stored, so a wrong URL fails in the form.
- **Team** — Dashboard → add an email. The invite link is shown so a reviewer
  can use it without an inbox.
