# Sensei

**A project teammate that does the work nobody asked it to do.**

Most AI tools answer questions. Sensei starts before anyone asks one: when a
project owner adds someone to a team, it researches the project and writes that
person a cited onboarding brief. When a source finishes indexing, it audits what
the project has *failed* to write down and offers to draft the missing documents
itself. When it cannot answer something, it records the question so a single
human reply turns into knowledge it has permanently.

Built on the [Strands Agents SDK](https://strandsagents.com/).

![Architecture](docs/assets/architecture.png)

- **[TESTING.md](TESTING.md)** — demo account, what to try
- **[DEPLOY.md](DEPLOY.md)** — one-container deployment
- **[docs/CONNECTOR_ACCESS.md](docs/CONNECTOR_ACCESS.md)** — what each credential actually grants
- **[docs/AGENTIC_PLAN.md](docs/AGENTIC_PLAN.md)** — the design behind the autonomy

---

## What it does

### Work that starts without a prompt

| | |
|---|---|
| **Onboarding brief** | An owner adds someone. Nobody asks for anything. A Strands `Graph` of three agents researches the project *for that person* and writes a typed brief — what this is, who owns what, what to read first, and an honest list of what the sources cannot tell them. It is waiting when they first log in. |
| **Gap hunter** | When a source lands, the agent audits its own knowledge for what is *absent*: documents that should exist, components with no owner, references that go nowhere. For gaps the sources can actually support, it offers to write the document — and flags every line it inferred rather than found. |
| **Answer ledger** | A question it could not ground is recorded rather than discarded. An owner answers once, it is indexed, and the agent answers it for everyone from then on. The project gets documented by being used. |
| **Change watch** | It re-reads the connected sources, diffs them, and decides whether anything *material* moved. A typo: silence. A runbook deleted: a digest, and every brief written against the old state is marked stale. Most checks cost nothing — the diff runs before any model does. |

### Work you ask for

- **Cited chat**, streamed token by token, narrating each tool call as it runs —
  *"Taking stock of what's indexed… Searching the project's documents…"*
- **Sources**: GitHub, Confluence, file upload, URL crawl
- **Trust & access**: every grant, its real ceiling, and how to revoke it

---

## Trust

The product's argument is that an agent with access to your project should be
able to show exactly what that access is.

- **Nobody reaches a project unless the owner added their email.** Invite tokens
  are bound to one address and spent on first use. A link alone is not
  authorisation.
- **Passwords are never emailed.** An invite carries a single-use link and the
  recipient sets their own.
- **Credentials are encrypted at rest** with `SECRET_ENCRYPTION_KEY`, and never
  returned by the API in any form.
- **Every connector is read-only.** Nothing in this build writes to a connected
  system.
- **The Trust page states each credential's ceiling, not just what we read.**
  A Confluence API token authorises as its owner across the whole site while
  Sensei reads one space — and the page says so, because showing only the
  narrower limit is a comfortable half-truth.

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

> Losing `SECRET_ENCRYPTION_KEY` makes existing sources unreadable — they have
> to be reconnected.

### One container instead

```bash
docker compose up --build      # builds the SPA and serves everything on :8000
```

The image builds the React app and FastAPI serves it alongside `/api/*`, so a
deployment is one container and one URL — no CORS, no second service.

### Tests

```bash
cd backend && python -m pytest -q            # 33 tests, no model calls, ~0.4s

# browser journeys, against a running server
E2E_OWNER_PASSWORD=... python -m pytest tests/e2e -q
```

---

## How it works

**Ingestion.** Each source is fetched, chunked at 800 characters and embedded
into a per-workspace ChromaDB collection. Every chunk carries a provenance
header — `[Confluence: ENG › Architecture doc]` — into the embedded text, so a
document can be found by its own name. Chunks are 800 rather than 2000 because
the default embedder truncates at 256 tokens; larger chunks are half-invisible
to search.

**Answering.** The Strands agent loop chooses its tools. `search_project_docs`
for "what does X say", `list_project_knowledge` for "is there a doc about X" —
a question about the shelf, not the books. Answers cite their sources, and the
agent says so plainly when the project does not cover something.

**Background work.** Briefs, audits and change checks run as background tasks.
Research is cached per project and composed per person, so adding five teammates
researches once rather than five times.

**Staying quiet.** Two features exist mainly to decide *not* to speak. The change
watcher hashes documents and diffs them before any model is called, so an
unchanged project costs nothing. And when the agent reads a team channel, it
answers only when it could cite a source — measured on this project, similarity
scores do not separate "documented" from "not", but whether it can produce a
citation does.

**Model backends.** One flag. `LLM_BACKEND=bedrock | groq | ollama`. Background
agents run a smaller model than interactive chat.

---

## Roles

| | Owner | Member |
|---|---|---|
| Connect and manage sources | ✅ | — |
| Add and remove teammates | ✅ | — |
| Answer ledger questions | ✅ | — |
| Ask the agent, read its briefs | ✅ | ✅ |
| See who has access | ✅ | ✅ |

Members never see the onboarding wizard; it is an owner's tool.

---

## Project structure

```
backend/
├── agent/          brief.py · gaps.py · watch.py · tools.py · ingest.py · agent.py
├── answers/        the answer ledger
├── watch/          change digests
├── channels/       channel abstraction + when to speak unbidden
├── trust/          what the agent can reach and how to revoke it
├── activity/       what it did, and which of it was unprompted
├── auth/ workspaces/ sources/ ingest/ chat/ briefs/ gaps/
├── core/           config · security · secrets · mailer · errors
├── db/             membership.py is the single access rule
└── tests/          33 unit tests + 7 browser journeys
frontend/src/pages/ Dashboard · Brief · Gaps · Answers · Trust · Chat · Sources
```

---

## License

MIT — see [LICENSE](LICENSE).
