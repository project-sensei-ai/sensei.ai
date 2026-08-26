# Sensei

A permission-aware platform that learns approved project context and participates through chat and Microsoft Teams meetings. Built with [Strands Agents SDK](https://strandsagents.com/).

## What It Does

New team members spend weeks getting up to speed. Existing members waste time searching for context that's scattered across docs, tickets, code, and chat. This agent joins your project like a teammate — it ingests your sources, builds a knowledge base, and answers questions with citations so you can trust the answer.

---

## User Journey

From zero to first answer in minutes.

```
  ┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌────────────┐
  │  SIGN UP │────►│ CONNECT  │────►│   INGEST &   │────►│   CHAT     │
  │          │     │ SOURCES  │     │   REVIEW     │     │            │
  └──────────┘     └──────────┘     └──────────────┘     └────────────┘
       │                │                 │                     │
  Owner creates    Pick platforms    Agent chunks &        Ask questions,
  workspace +      & authenticate    embeds content        get cited
  invites team     (OAuth / token)   Owner reviews         answers
```

---

## Authentication

Three layers, kept simple.

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — WHO ARE YOU?                                     │
│  Email + password login → JWT token                         │
│  Every request carries this token                           │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2 — WHICH WORKSPACE?                                 │
│  User belongs to one or more workspaces                     │
│  Role: Owner (manages sources) or Member (chats only)       │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3 — CAN WE ACCESS THIS SOURCE?                       │
│  OAuth tokens / API keys stored encrypted per workspace     │
│  Agent uses these to fetch content on behalf of the org     │
└─────────────────────────────────────────────────────────────┘
```

### Hackathon Simplification

| What | Full Vision | MVP |
|---|---|---|
| Login | OAuth (Google, GitHub, Microsoft) | Email + password only |
| Roles | Owner, Admin, Member, Viewer | Owner + Member |
| Source perms | Per-user, per-source ACL | Owner sees all, members chat |
| Token storage | Vault / KMS encrypted | Encrypted at rest in DB |

---

## Ingestion

How content gets into the agent's memory.

```
┌─────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                    │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  GitHub  │  │   File   │  │   URL    │  │ Conflu │ │
│  │   Repo   │  │  Upload  │  │  Crawl   │  │  ence  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│       └──────────────┴──────┬───────┴─────────────┘      │
│                             │                            │
│                    ┌────────▼────────┐                   │
│                    │   CHUNK +       │                   │
│                    │   EMBED         │                   │
│                    └────────┬────────┘                   │
│                             │                            │
│                    ┌────────▼────────┐                   │
│                    │  VECTOR STORE   │                   │
│                    │  (per workspace)│                   │
│                    └─────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

### Supported Sources

| Source | Auth | What It Ingests | Status |
|---|---|---|---|
| **GitHub** | Personal Access Token (repo+user+project scopes) | Files, commits, contributors, collaborators, org members, org teams, PRs+reviews, issues, branches, releases, milestones, CI/CD workflows | ✅ Built |
| **File Upload** | None (platform auth) | PDF, MD, TXT, DOCX | ✅ Built |
| **URLs** | None | Any public web page (pre-validated with HEAD request) | ✅ Built |
| **Confluence** | API token | Wiki spaces, pages | ✅ Built |
| Jira | API token | Tickets, epics, boards | Future |
| SharePoint | MS Graph OAuth | Documents, folders | Future |
| Slack | OAuth | Channel messages | Future |

See `Agents.md` for the full list of data types fetched per source and the contributors vs collaborators distinction.

### Onboarding Wizard

```
Step 1: CREATE WORKSPACE
        Name it → describe the project
        
Step 2: CONNECT SOURCES
        ┌─────────────────────────────────────────┐
        │  [GitHub]  Enter PAT → select repos     │
        │  [Upload]  Drag & drop files             │
        │  [URL]     Paste links to crawl          │
        └─────────────────────────────────────────┘
        
Step 3: REVIEW
        Agent shows what it found:
        ├─ Files indexed: 47
        ├─ Code files: 23
        ├─ Pages crawled: 5
        └─ Owner approves or adjusts scope
        
Step 4: INVITE TEAM
        Send invite link → members start chatting
```

---

## How It Works (System View)

One agent brain. Many entry points. Users interact wherever they already are.

```
                    ┌──────────────────┐
                    │  Microsoft Teams │
                    │  (Bot Framework) │
                    └────────┬─────────┘
                             │
┌─────────────┐    ┌─────────▼──────────┐    ┌──────────────┐
│  Web Chat   │───►│   CHANNEL LAYER     │◄───│  Slack Bot   │
│  (React UI) │    │  Adapters / Bots    │    │  (SDK)       │
└─────────────┘    └─────────┬──────────┘    └──────────────┘
                             │
                    ┌────────▼─────────┐
                    │  STRANDS AGENT   │
                    │                  │
                    │  Agent Loop      │
                    │  ├─ search tool  │
                    │  ├─ github tool  │
                    │  ├─ upload tool  │
                    │  ├─ url tool     │
                    │  └─ memory tool  │
                    │                  │
                    │  Memory Store    │
                    │  (per workspace) │
                    └──────────────────┘

Same agent. Same tools. Same memory. Different mouth.
```

---

## Tech Stack

| Layer | Tech | Role |
|---|---|---|
| Agent Framework | [Strands Agents SDK](https://strandsagents.com/) v1.26 | `@tool` functions, `Agent` agentic loop, `S3SessionManager` |
| Model — production | **AWS Bedrock** `BedrockModel` (`LLM_BACKEND=bedrock`) | Claude / Titan / Llama via Bedrock |
| Model — dev | **Groq** `OpenAIModel` (`LLM_BACKEND=groq`) | `openai/gpt-oss-120b` via Groq API |
| Model — offline | **Ollama** `OpenAIModel` (`LLM_BACKEND=ollama`) | Any local model (qwen3:4b, llama3.2, etc.) |
| Vector Store | **ChromaDB** (local PersistentClient) | Document embeddings, per-workspace `ws_{id}` collections |
| AWS KB | **Bedrock Knowledge Bases** | Uploaded file indexing via `search_knowledge_base` @tool |
| Session Memory | **S3** via `S3SessionManager` | Agent conversation memory per chat session |
| Embedder | sentence-transformers `all-MiniLM-L6-v2` | Default ChromaDB embedder (no API key needed) |
| Auth | JWT (httpOnly cookie) + bcrypt + Google OAuth | Platform authentication |
| Database | **MongoDB Atlas** (Motor async driver) | Users, workspaces, sources, chat sessions metadata |
| Backend | Python 3.12+, FastAPI, Uvicorn | HTTP API |
| Frontend | React 19, TypeScript, Tailwind CSS 4, RTK Query, Redux Toolkit | Chat UI + onboarding wizard |
| Deployment | Docker (`Dockerfile` + `docker-compose.yml`) | AgentCore Runtime / App Runner |

---

## Channels

Each channel is a thin adapter — it receives a message, passes it to the agent, and returns the response. No business logic lives in the channel.

| Channel | How It Works | MVP Status |
|---|---|---|
| **Web Chat** | React UI → FastAPI → Agent | Hackathon MVP |
| **Microsoft Teams** | Bot Framework → FastAPI webhook → Agent | Demo target |
| **Slack** | Slack Bolt SDK → Agent | Stretch goal |
| **CLI** | Terminal → Agent (for dev/testing) | Dev tool |
| **REST API** | Any HTTP client → FastAPI → Agent | Available now |

---

## Project Structure

```
agents-for-humans/
├── backend/
│   ├── main.py                      # FastAPI app, lifespan (MongoDB + ChromaDB init)
│   │
│   ├── auth/                        # Authentication
│   │   ├── routes.py                #   /auth/register, /login, /logout, /me, /google
│   │   └── deps.py                  #   get_current_user dependency
│   │
│   ├── workspaces/
│   │   └── routes.py                #   POST /workspaces, GET /workspaces/me, POST /invite
│   │
│   ├── sources/
│   │   └── routes.py                #   GET/POST /sources, POST /sources/upload, DELETE /sources/{id}
│   │
│   ├── ingest/
│   │   └── routes.py                #   POST /ingest/{id}, GET /ingest/{id}/status
│   │
│   ├── chat/
│   │   └── routes.py                #   Session CRUD + POST /sessions/{id}/messages
│   │
│   ├── agent/
│   │   ├── tools.py                 #   @tool: fetch_github, fetch_urls, parse_file, fetch_confluence
│   │   │                            #          make_search_tool() factory, search_knowledge_base @tool
│   │   ├── agent.py                 #   build_agent() — Strands Agent + model selection (bedrock/groq/ollama)
│   │   │                            #   make_session_manager() — S3SessionManager when bucket configured
│   │   └── ingest.py                #   run_ingestion() — chunk + embed + upsert ChromaDB
│   │
│   ├── db/
│   │   ├── database.py              #   get_db dep, ensure_indexes()
│   │   ├── models.py                #   serialize_* functions for all collections
│   │   └── chroma.py                #   get_chroma dep, get_workspace_collection()
│   │
│   ├── core/
│   │   └── config.py                #   Settings (MONGODB_URI, GROQ_API_KEY, etc.)
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Routing (ProtectedRoute, OnboardingRoute)
│   │   ├── components/
│   │   │   ├── ProtectedRoute.tsx   # Auth + workspace guard
│   │   │   ├── OnboardingRoute.tsx  # Prevents mid-wizard redirect
│   │   │   └── AppShell.tsx         # Sidebar nav + dynamic title
│   │   ├── pages/
│   │   │   ├── Login.tsx / Register.tsx
│   │   │   ├── Onboarding.tsx       # 4-step wizard
│   │   │   ├── onboarding/          # StepWorkspace, StepSources, StepReview, StepInvite
│   │   │   ├── Sources.tsx          # Source list, add, delete, re-ingest
│   │   │   ├── Chat.tsx             # Session sidebar + conversation panel
│   │   │   └── Dashboard.tsx
│   │   └── services/
│   │       ├── api.ts               # RTK Query base (tag types)
│   │       └── onboardingApi.ts     # All endpoint hooks
│   ├── vite.config.ts               # /api proxy → localhost:8000
│   └── package.json
│
├── docs/
│   ├── ARCHTECTRUE.md               # This file
│   ├── PRD.md
│   ├── HACKATHON.md
│   └── AUTH_PLAN.md
├── Agents.md                        # Tool functions, AI layer, pipelines (detailed)
├── Dockerfile                       # python:3.12-slim — AgentCore Runtime deployment
├── docker-compose.yml               # local container test
├── LICENSE                          # MIT
└── README.md
```

---

## Core Concepts (Strands SDK)

### Agent Loop

The agent reasons automatically — no manual RAG pipeline:

1. Receives user input
2. Decides which tools to call
3. Executes tools, accumulates context
4. Repeats until it has enough to answer
5. Produces a cited response

### Custom Tools

```python
from strands import tool

@tool
def search_project_docs(query: str) -> list:
    """Search indexed project docs. Returns chunks with file paths."""
    results = vector_store.search(query)
    return [{"content": r.text, "source": r.metadata["file_path"]} for r in results]
```

The agent decides *when* to call each tool based on the question.

### Memory

The `MemoryManager` persists knowledge across sessions:

- **Project Store** — indexed docs, code, decisions per workspace
- **Injection** — relevant context auto-injected into prompts
- **Extraction** — new facts captured from conversations

### Streaming

```python
async def chat_stream(message: str):
    async for event in agent.stream_async(message):
        if "text" in event:
            yield event["text"]
```

---

## API Endpoints

All routes served at `http://localhost:8000`. Frontend accesses them via Vite proxy `/api` → `http://localhost:8000`.

**Auth**

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Email + password registration |
| POST | `/auth/login` | — | Sets httpOnly cookie `sensei_token` (JWT) |
| POST | `/auth/logout` | — | Clears cookie |
| GET | `/auth/me` | JWT | Returns current user |
| GET | `/auth/google` | — | Redirect to Google OAuth |
| GET | `/auth/google/callback` | — | Handles callback, sets cookie |

**Workspaces**

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/workspaces` | JWT | Create workspace (1 per user, 409 if exists) |
| GET | `/workspaces/me` | JWT | Get workspace (404 → redirect to onboarding) |
| POST | `/workspaces/{id}/invite` | JWT + owner | Generate 7-day invite link |

**Sources**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/sources` | JWT | List workspace sources |
| POST | `/sources` | JWT | Add GitHub / URL / Confluence source |
| POST | `/sources/upload` | JWT | Upload file (pdf/md/txt/docx) |
| DELETE | `/sources/{id}` | JWT + owner | Remove from MongoDB + delete ChromaDB chunks |

**Ingest**

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/ingest/{source_id}` | JWT | Trigger ingestion as BackgroundTask (202); 409 if already indexing |
| GET | `/ingest/{source_id}/status` | JWT | Poll status: pending / indexing / ready / error |

**Chat Sessions**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/chat/sessions` | JWT | List non-archived sessions (newest first, max 50) |
| POST | `/chat/sessions` | JWT | Create empty session |
| GET | `/chat/sessions/{id}` | JWT + owner | Full session with messages array |
| POST | `/chat/sessions/{id}/messages` | JWT + owner | Send message → ChromaDB → Groq → persist → return answer + citations |
| DELETE | `/chat/sessions/{id}` | JWT + owner | Archive session (soft delete), 204 |

---

## Database Schema

MongoDB collections (Motor async driver):

```
users
├── _id             (UUID)
├── email           (unique index)
├── password_hash
├── name
├── google_sub      (unique index, partial — only for Google OAuth users)
├── picture
└── created_at

workspaces
├── _id             (UUID)
├── owner_id        (unique index — 1 workspace per user)
├── name
├── description
└── created_at

sources
├── _id             (UUID)
├── workspace_id    (index)
├── type            (github | file | url | confluence)
├── label           (display name)
├── config          (repo name, URLs, etc. — no secrets)
├── config_secret   (PAT, API tokens — never serialized to frontend)
├── status          (pending | indexing | ready | error)
├── stats           {chunks_count, pages_crawled}
├── error_message
├── created_at
└── updated_at

invites
├── _id             (UUID)
├── workspace_id    (index)
├── token           (unique index)
├── invite_url
├── created_at
└── expires_at      (7 days)

chat_sessions
├── _id             (UUID)
├── workspace_id    (compound index with archived + updated_at)
├── owner_id
├── title           (auto-set from first user message, 60 chars)
├── messages[]
│   ├── role        (user | assistant)
│   ├── content
│   ├── citations[] (assistant messages only)
│   └── created_at
├── created_at
├── updated_at      (used for sidebar sort order)
└── archived        (bool — soft delete)
```

Vector store (ChromaDB, local PersistentClient at `./chroma_data`):

```
Collection: ws_{workspace_id}   (one per workspace)
  ids:       {source_id}_{chunk_index}
  documents: chunk text (2000 chars, 200-char overlap)
  metadatas:
    ├── source_id
    ├── source_label
    ├── chunk         (index)
    ├── data_type     (file | commits | collaborators | org_members | ...)
    ├── repo          (GitHub sources)
    ├── path          (file sources)
    └── url
```

---

## Hackathon Build Plan

```
DAY 1 — Foundation
  ├── Auth (signup / login / JWT)
  ├── Workspace creation
  └── GitHub PAT connection + ingest one repo

DAY 2 — Agent Core
  ├── Strands Agent + system prompt
  ├── Search tool (vector similarity)
  ├── File upload ingestion
  └── URL crawl ingestion

DAY 3 — UI + Polish
  ├── Onboarding wizard (3 steps)
  ├── Chat UI with streaming + citations
  ├── Review indexed content screen
  └── Invite flow (basic link)

DAY 4 — Demo
  ├── End-to-end flow test
  ├── Teams bot adapter (if time)
  └── Fallback: web chat demo
```

---

## What's Built

### ✅ Complete
- Auth — email/password + JWT (httpOnly cookie) + Google OAuth
- Workspace CRUD (1 per user) + 7-day invite links
- Source management — GitHub (PAT), File Upload, URL, Confluence
- GitHub ingestion — 19 data types including collaborators, org members, PAT owner profile, PR reviews, branches, releases, workflows
- URL pre-validation before source is stored (HEAD request)
- ChromaDB ingestion pipeline with per-source cleanup on re-ingest
- Groq chat Q&A with two-mode system prompt and inline citations
- Chat sessions — persistent history in MongoDB, auto-title, archive
- 4-step onboarding wizard (workspace → sources → review → invite)
- Sources page — live status, delete (MongoDB + ChromaDB), re-ingest
- Chat page — session sidebar, session list, archive button

### Future (Post-Hackathon)
- Teams / Slack channel adapters
- Real-time source sync via webhooks
- Per-user permission filtering
- Jira, SharePoint connectors
- Multi-agent orchestration

---

## Environment Variables

Set these in `backend/.env` (copy from `backend/.env.example`):

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `JWT_SECRET` | Yes | Secret for signing JWTs |
| `GROQ_API_KEY` | Yes | Groq API key (`openai/gpt-oss-120b`) |
| `CHROMA_PERSIST_DIR` | Yes | Path for ChromaDB data (default: `./chroma_data`) |
| `FRONTEND_ORIGIN` | Yes | Frontend URL for CORS (default: `http://localhost:5173`) |
| `GOOGLE_CLIENT_ID` | OAuth | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth | Google OAuth client secret |

---

## Model Provider Options

Swap model providers without changing application code:

```python
# OpenAI (default)
from strands.models.openai import OpenAIModel
model = OpenAIModel(model_id="gpt-4o")

# Amazon Bedrock
from strands.models import BedrockModel
model = BedrockModel(model_id="global.anthropic.claude-sonnet-4-6")

# Anthropic
from strands.models.anthropic import AnthropicModel
model = AnthropicModel(model_id="claude-sonnet-4-20250514")

# Ollama (local, free)
from strands.models.ollama import OllamaModel
model = OllamaModel(host="http://localhost:11434", model_id="llama3")
```

---

## License

Internal hackathon project.
