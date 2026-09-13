# Testing Sensei

Written for: whoever is reviewing this. Everything below is real — there is no
seeded fiction, and the numbers are what the agent actually produced.

---

## The demo account

| | |
|---|---|
| URL | `<LIVE_URL>` ← fill in after deploying, or run locally (§4) |
| Email | `judge@sensei.demo` |
| Password | `Demo-miwVU8NczE6N` |

It owns **Sensei Demo Project**, which has this project's own documentation
connected — README, PRD, architecture, agent design, hackathon rules — plus a
GitHub repository and a Confluence space. Around 260 indexed passages.

---

## 1. The thing worth seeing first

Open **Dashboard**. Near the top is *"What the agent has been doing"*, and some
entries are tagged **"on its own"**.

Those happened with nobody asking:

- **Wrote an onboarding brief** — triggered when a teammate was added
- **Audited the documentation, found 8 gaps** — triggered when a source finished
  indexing

That tag is the product. Everything else follows from it.

---

## 2. Five minutes, in order

**Your brief** — written for whoever is logged in, before they first signed in.
Sections cite their sources. The last card, *"What nobody wrote down"*, lists
what a joiner needs that the sources cannot tell them. That section is the
honest one; an agent that only reports what it found is selling something.

**Gaps** — what the project failed to document. Eight of them, with severity and
what made the agent notice. Three say **"Write it for me"**: the sources contain
enough to draft them. Click one. You get a real document with its sources, and
an amber panel headed *"Verify these before you publish"* listing everything the
agent inferred rather than found.

The five it declines are the interesting half. An incident runbook cannot be
written from documentation that never mentions incidents, and it says so rather
than inventing one.

**Chat** — ask *"What is the difference between contributors and collaborators?"*
Watch the tool calls narrate themselves — *"Taking stock of what's indexed…
Searching the project's documents…"* — then the answer streams in with citations.
First token lands in about a second.

Then ask something the project has never documented: *"What is our AWS bill this
month?"* It declines. It does not guess.

**Answers** — that declined question is now in the ledger. As the owner you can
answer it in one sentence; it is indexed immediately and the agent has it
permanently. There is already a worked example: someone asked which cloud
provider this deploys to, the owner answered once, and the agent now replies
*"AWS, us-east-1, account 345182672204"* citing **Team answers**.

The page also carries the number this product lives on: **answered without a
human**.

**Trust** — every source, with two columns: what Sensei reads, and what the
credential *could* reach. Those differ, and most tools show only the first. A
Confluence API token authorises as its owner across the whole site while Sensei
reads one named space — the page says so, and suggests the tighter arrangement.

It also reports its own shortcomings. One source was connected before
credential encryption existed, and it is labelled accordingly rather than
quietly included in the reassurance.

---

## 3. The access model (needs two accounts)

1. As the owner, **Dashboard → Team** → add any email address.
2. You get a single-use invite link (mail sending is optional; the link is shown
   so a reviewer can use it without an inbox they control).
3. Open it in a private window. Set a password — **no password is ever emailed**.
4. You land in the project as a **member**: Sources is read-only, Gaps has no
   "Write it for me", the ledger shows only your own questions.

Worth trying: registering directly as a team member is refused. The owner's list
is the only way in, and an invite token is bound to one address — signing in as
anyone else and opening the link returns a 403 naming the address it was issued
to.

And: adding someone starts a brief for them. It takes a few minutes; the
dashboard card shows it working.

---

## 4. Running it locally

```bash
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # MONGO_DB, JWT_SECRET, SECRET_ENCRYPTION_KEY, GROQ_API_KEY, DEBUG=true
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev    # second terminal
```

http://localhost:5173. No AWS account needed — `LLM_BACKEND` defaults to Groq.

**Tests:** `cd backend && python -m pytest tests/ -q` — 27 tests, no model
calls, under half a second.

---

## 5. Connecting your own sources

As the owner, on **Sources**:

- **GitHub** — a PAT with `repo`, `user`, `project`. Pulls 19 data types.
- **Confluence** — paste any page URL; the site and space key are extracted from
  it. The form states what the token could reach before you paste one.
- **File** — pdf, docx, md, txt.
- **URL** — any public page, reachability-checked before it is stored.

A source finishing triggers a fresh documentation audit.

---

## 6. What is not built

Stated so nothing in the demo is mistaken for more than it is.

- **Teams and Slack** — the channel abstraction and the rule for when the agent
  should speak unbidden are written and tested; no transport is connected.
- **Per-item ACLs** — every member of a project sees the same corpus. Access is
  controlled at the project boundary, not per document.
- **Jira, ServiceNow, SharePoint** — not connected.
- **The container image has never been built** — Docker is not installed on the
  development machine. The Dockerfile is checked statically and both build steps
  succeed natively.

The plan for these is in
[docs/FEATURE_BACKLOG.md](docs/FEATURE_BACKLOG.md).
