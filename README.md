# Sensei

**A colleague you onboard, not a chatbot you prompt.**

A project owner gives Sensei what they would give a new hire: the wiki space,
the repo, the ticket project, and accounts on the tools the team uses. Then
they add their team. From that point Sensei works for those people — before
they ask, when they ask, and in the room with them.

Built on the [Strands Agents SDK](https://strandsagents.com/). Entered in the
Agents for Humans hackathon, Professional Agents track.

![Architecture](docs/assets/architecture.png)

- **[TESTING.md](TESTING.md)** — two demo projects, two owners, what to try
- **[DEPLOY.md](DEPLOY.md)** — one container on AWS with HTTPS, one command
- **[docs/CONNECTOR_ACCESS.md](docs/CONNECTOR_ACCESS.md)** — what each credential and tool grant actually authorises
- **[docs/SUBMISSION.md](docs/SUBMISSION.md)** — the pitch, the video script, the judge notes

---

## What it does

### Before anyone asks

| | |
|---|---|
| **Onboarding brief** | An owner adds someone. A Strands `Graph` of three agents researches the project *for that person* and writes a typed, cited brief — what this is, who owns what, what to read first, and an honest list of what the sources cannot tell them. It is waiting when they first log in. |
| **Gap hunter** | When a source lands, the agent audits its own knowledge for what is *absent*: documents that should exist, components with no owner, references that go nowhere. Where the sources can support it, it drafts the missing page and flags every line it inferred. |
| **Change watch** | It re-reads sources on a schedule, diffs them, and decides whether anything *material* moved. A typo: silence. A runbook deleted: a digest, and every brief written against the old state marked stale. |
| **Answer ledger** | A question it could not ground is recorded. An owner answers once; it is indexed, and the agent answers it for everyone from then on. |
| **Self-interview** | Once the sources settle, it writes the eight questions a new joiner would ask *this* project, tries to answer each from the sources alone, and grades itself: "ready for 5 of 8". The ones it fails go into the ledger before any person hits the gap. Two model calls; the honest number on the dashboard. |

### When asked

- **Cited answers**, streamed token by token, every tool call narrated as it runs.
- **Who did what** — "what has Priya changed recently" reads her commits, PRs and tickets, not prose that mentions her.
- **Jira, live** — ticket status is read from Jira at the moment of asking, never from the index. A Confluence credential is a Jira credential too.
- **Work, handed back as a file** — "put the open issues in a spreadsheet" produces an `.xlsx`; "write me a handover note" produces a `.docx`, attached to the reply.
- **Tools the owner granted** — any MCP server, connected two ways: **sign in** (Atlassian, Notion, Linear, Sentry, Asana, Intercom — MCP's OAuth profile with dynamic client registration, so the owner logs in on the vendor's page and Sensei receives a token it refreshes itself), or a pasted token (GitHub, Zapier for Gmail/Sheets/Slack, an internal API). Its tools appear in the agent loop with the service's name as a prefix. Writes are refused, inside the loop, unless the owner switched them on for that connection — and the agent says exactly that instead of pretending.

### In the room

Sensei sits in a meeting — via the browser's microphone beside any call, or as
a participant in a Google Meet that reads the live captions. It answers when
addressed by name. It corrects a claim only when a typed verdict says the
project's own documentation contradicts it, with confidence ≥ 0.8 and a
citation; anything less and it stays quiet, and records why. When the call
ends it writes the notes — decisions, action items, open questions — and
indexes them, so next week's "what did we decide" is answerable with a citation
to the meeting.

### In Slack

Add the Slack app to a channel and Sensei is in the room there too. It reads
what people post and indexes it as it arrives, so a decision made at 10:02 can
be asked about at 10:03. It answers when mentioned or messaged directly, and it
answers a question nobody addressed to it only when the project's sources can
cite the answer, in the message's thread, with the sources named. Everything
else it leaves alone. A mention it cannot answer goes to the Answers ledger for
an owner to close. Setup: point the Slack app's Event Subscriptions at
`https://<host>/api/slack/events`, subscribe the bot to `app_mention`,
`message.channels` and `message.im`, and put the app's signing secret in
`SLACK_SIGNING_SECRET` so the endpoint can prove requests came from Slack.

---

### Onboarding is a conversation

A new colleague's first day is a conversation, not a form. Sensei asks what the
project is called, where the team keeps its knowledge, which accounts it gets,
and who may ask it things; the owner answers by connecting. The last message
is Sensei stating exactly what it can now reach — the same numbers the Trust
page carries.

## Trust

An agent with access to your project should be able to show exactly what that
access is.

- **Nobody reaches a project unless the owner added their email.** Invite tokens are bound to one address and spent on first use.
- **Credentials are encrypted at rest** and never returned by the API. Sources are read-only by construction.
- **Every tool is classified read or write on connection**, and write calls are cancelled by a Strands hook unless the owner allowed them. Unprompted work never writes anywhere.
- **Two members can get different answers.** An owner narrows what any teammate is answered from; the filter runs inside the vector query, so a restricted person gets *different* results rather than fewer.
- **Meeting transcripts are hearsay.** They are indexed for "what did we discuss", and excluded from claim checks, so one wrong remark never becomes "supported by the sources".
- **The Trust page states each credential's ceiling, not just its floor.** A Confluence token authorises as its owner across the whole site while Sensei reads one space — the page says so.

---

## Setup

**Prerequisites:** Python 3.12+, Node 18+, MongoDB Atlas (free tier), and a
model provider — [Groq](https://console.groq.com) is free and needs no AWS.

```bash
# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit it
uvicorn main:app --reload --port 8000

# frontend, second terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5173.

`backend/.env`:

```
MONGO_DB=mongodb+srv://...
MONGO_DB_NAME=sensei
JWT_SECRET=                 # openssl rand -hex 32
SECRET_ENCRYPTION_KEY=      # openssl rand -hex 32
GROQ_API_KEY=gsk_...
CHROMA_PERSIST_DIR=./chroma_data
FRONTEND_ORIGIN=http://localhost:5173
DEBUG=true                  # drops the Secure cookie flag so login works over HTTP
```

> Losing `SECRET_ENCRYPTION_KEY` makes existing sources and tool grants
> unreadable — they have to be reconnected.

**Paid Claude:** set `ANTHROPIC_API_KEY` (console.anthropic.com) and Claude
Haiku 4.5 answers chat and does the background work; the free tiers below
become fallbacks. `ANTHROPIC_MODEL` and `ANTHROPIC_BACKGROUND_MODEL` pick
other Claude models. Groq's free tier allows 200,000 tokens a day per model, which
a demo day of testing uses up.

**Free hosted fallbacks:** set any of `CEREBRAS_API_KEY` (cloud.cerebras.ai,
1M tokens/day), `GEMINI_API_KEY` (aistudio.google.com) or `OPENROUTER_API_KEY`
and they join the chain behind Groq. No card, no local model.

**Bedrock instead of Groq:** `LLM_BACKEND=bedrock` with an IAM principal
(not the account root — Bedrock refuses root) that has `bedrock:InvokeModel`,
and a current inference profile such as `us.anthropic.claude-sonnet-4-6`.

### One container

```bash
docker compose up --build      # builds the SPA and serves everything on :8000
```

For a public HTTPS URL on AWS, see [DEPLOY.md](DEPLOY.md) — `deploy/launch-ec2.sh`
is one command from a laptop with AWS credentials to a running instance.

### Tests

```bash
cd backend && python -m pytest -q            # 166 tests, no model calls, ~1s

# browser journeys, against a running server
E2E_OWNER_PASSWORD=... python -m pytest tests/e2e -q
```

---

## How it works

**Equipping the agent.** Before the model runs, Sensei searches the sources
for the question and hands the passages over with it, so most questions are
answered in a single model call instead of three. That search also runs
without tool names like "Confluence", which otherwise pull in pages about the
tool itself, and no single page takes more than two places. Every turn builds a
`Colleague`: the index tools,
the live Jira tools when an Atlassian credential exists, the work tools, and
up to eight connected tools the question actually touches — a server like
GitHub exposes fifty, and their schemas cost more tokens than the question.
When a model refuses a call at its per-minute limit, the turn moves onto the
next model with room and makes the same call again, keeping what it has
already gathered. A quiet spell gets a "still working" notice, and no question
waits past two and a half minutes.
MCP sessions are pooled across turns and closed off the event loop.

**Plain answers and the thinking stream.** Answers read like a colleague's chat
message: plain sentences that lead with the answer, **bold** for the one or two
facts that matter, and "- " bullets only for three or more parallel items. The
prompt forbids citation markers, bracketed source labels, tables and headings,
because the sources are already listed under every answer. `core/formatting.py`
(`plain_answer`) is the net under the prompt: it strips 【1】, [2] and
`[Confluence: SD › …]` labels, turns tables into bullets and headings into a bold
line, and runs on every stored chat answer and every meeting reply. The web
app's `AnswerText` renderer mirrors it, so streaming text and older messages
read the same, and renders only paragraphs, lists and bold — no HTML injection.
While a turn runs, the stream sends steps ("Reading your question", "Searching
the project's documents", each tool's narration, "Writing the answer"). A model
resting at its limit, a switch to another model or a slow provider reaches the
person as one calm step, "Taking a little longer to check", never a model name.
The steps and the turn's duration are stored on the message, and a finished
answer shows them folded away as "Thought for 8s · 3 steps". The agent also
sees the last three exchanges of the chat, so "and what is her target?" is
answered in the context of the question before it; `S3_SESSION_BUCKET` swaps
that replay for a persistent session store.

**The write gate.** `WriteGate` is a Strands `HookProvider` on
`BeforeToolCallEvent`. A granted tool the owner has not permitted gets
`cancel_tool` set with a message; the model receives that message as the tool
result and tells the person. The tool stays *visible* on purpose, so the agent
can say "I can see `create_issue` but I'm not allowed to use it" instead of
pretending the capability does not exist.

**Ingestion.** Each source is fetched, chunked at 800 characters and embedded
into a per-workspace ChromaDB collection. Every chunk carries a provenance
header — `[Confluence: SD › Apollo — Deployment runbook]` — so a document can
be found by its own name. Chunks are 800 rather than 2000 because the default
embedder truncates at 256 tokens.

**Staying quiet.** Three features exist mainly to decide *not* to speak. The
change watcher hashes documents before any model runs. In a channel, the agent
posts only when it can cite a source. In a meeting, a correction needs a typed
`ClaimVerdict` — contradicted, confidence ≥ 0.8, and a citation — retrieved
from documentation with transcripts excluded.

**Model backends.** One flag: `LLM_BACKEND=bedrock | groq | ollama`.
Background agents run a smaller model than interactive chat. On the hosted
free tiers, a chain routes around any model whose quota is exhausted: Claude
first when an Anthropic key is set, then Groq's models, then Cerebras, Gemini
and OpenRouter — each joins the chain when its key is present. A quota error marks that model out for an hour and the
turn retries on the next.

---

## Roles

| | Owner | Member |
|---|---|---|
| Connect sources, grant tools, allow writes | ✅ | — |
| Add and remove teammates, narrow what they see | ✅ | — |
| Answer ledger questions | ✅ | — |
| Ask, get files, bring it into a meeting | ✅ | ✅ |
| See what it can reach and do | ✅ | ✅ |

---

## Project structure

```
backend/
├── agent/          agent.py (build_colleague) · tools.py · people.py · jira.py · work.py
│                   brief.py · gaps.py · watch.py · ingest.py
├── toolgrants/     registry.py (MCP transports, read/write classification, WriteGate) · pool.py · routes.py
├── meetings/       listener.py (answer / correct / silent) · meet_bot.py (Playwright) · routes.py
├── artifacts/      files the agent produced
├── answers/ watch/ channels/ trust/ activity/ auth/ workspaces/ sources/ ingest/ chat/ briefs/ gaps/
├── core/           config · security · secrets · mailer · errors
├── db/             membership.py is the single access rule
├── scripts/        seed_confluence.py · seed_apollo.py — the demo projects, built through the API
└── tests/          166 unit tests + 7 browser journeys
frontend/src/pages/ Dashboard · Brief · Gaps · Answers · Trust · Sources · Tools · Meetings · Chat
deploy/             docker-compose.prod.yml · Caddyfile · launch-ec2.sh
```

---

## License

MIT — see [LICENSE](LICENSE).
