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

| Source | Auth | What It Ingests | MVP Status |
|---|---|---|---|
| **GitHub** | Personal Access Token | README, code files, docs | Yes — MVP |
| **File Upload** | None (platform auth) | PDF, MD, TXT, DOCX | Yes — MVP |
| **URLs** | None | Any public web page | Yes — MVP |
| Confluence | API token | Wiki spaces, pages | Stretch |
| Jira | API token | Tickets, epics, boards | Stretch |
| SharePoint | MS Graph OAuth | Documents, folders | Future |
| Slack | OAuth | Channel messages | Future |
| Meeting transcripts | MS Graph | Audio + captions | Future |

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
| Agent Framework | [Strands Agents SDK](https://strandsagents.com/) | Agent loop, tool orchestration, streaming |
| Model Provider | OpenAI (or Bedrock, Anthropic, Ollama) | LLM inference |
| Memory | Strands MemoryManager + custom store | Persistent project knowledge |
| Auth | JWT + bcrypt | Platform authentication |
| Database | SQLite (MVP) → PostgreSQL | Users, workspaces, sources |
| Vector Store | ChromaDB (MVP) | Document embeddings |
| Channels | See table below | Platform adapters |
| Backend | Python 3.12+, FastAPI, Uvicorn | HTTP API + streaming |
| Frontend | React 19, TypeScript, Tailwind CSS 4, Redux Toolkit | Chat UI |
| Build | Vite 8, OxLint | Dev server + linting |

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
hack-agents-for-human/
├── backend/
│   ├── main.py                  # FastAPI app, lifespan
│   ├── agent.py                 # Strands Agent + system prompt
│   │
│   ├── auth/                    # Authentication
│   │   ├── routes.py            #   POST /auth/signup, /auth/login
│   │   └── middleware.py        #   JWT verification
│   │
│   ├── onboarding/              # Workspace + source setup
│   │   └── routes.py            #   POST /workspaces, /sources, /ingest
│   │
│   ├── tools/                   # Strands custom tools
│   │   ├── github.py            #   @tool — fetch repos, files
│   │   ├── search.py            #   @tool — vector search
│   │   ├── upload.py            #   @tool — process uploaded files
│   │   └── url_crawl.py         #   @tool — crawl & ingest URLs
│   │
│   ├── memory/                  # Persistent knowledge
│   │   └── project_store.py     #   Custom MemoryStore
│   │
│   ├── channels/                # Platform adapters
│   │   ├── web.py               #   FastAPI routes for web chat
│   │   ├── teams.py             #   Bot Framework (future)
│   │   └── slack.py             #   Slack Bolt (future)
│   │
│   ├── db/                      # Data layer
│   │   ├── models.py            #   SQLAlchemy models
│   │   └── connection.py        #   DB engine + session
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main app + routing
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── pages/
│   │   │   ├── Login.tsx        # Auth page
│   │   │   ├── Onboard.tsx      # 3-step wizard
│   │   │   └── Chat.tsx         # Chat interface
│   │   ├── store/               # Redux store
│   │   └── services/            # RTK Query APIs
│   ├── vite.config.ts
│   └── package.json
│
├── PRD.md
├── README.md
└── README_PROJECT.md
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

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create account |
| POST | `/auth/login` | — | Get JWT token |
| GET | `/health` | — | Backend status |
| POST | `/api/workspaces` | JWT | Create workspace |
| POST | `/api/sources` | JWT | Connect a source |
| POST | `/api/ingest/{source_id}` | JWT | Trigger ingestion |
| GET | `/api/sources` | JWT | List indexed sources |
| POST | `/api/chat` | JWT | Chat with agent (streaming) |
| POST | `/webhook/teams` | — | Teams bot (future) |
| POST | `/webhook/slack` | — | Slack events (future) |

---

## Database Schema

```
users                 workspaces            workspace_members
├── id                ├── id                ├── workspace_id
├── email             ├── name              ├── user_id
├── password_hash     ├── description       └── role (owner/member)
├── name              └── created_at
└── created_at

sources               documents
├── id                ├── id
├── workspace_id      ├── source_id
├── type              ├── path
│   (github/file/     ├── content
│    url/confluence)  ├── embedding
├── config            └── metadata
│   (encrypted)           (author, modified_at, url)
├── status
│   (pending/ready/error)
└── last_synced_at
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

## What's Built vs What's Planned

### Done
- FastAPI backend scaffold with health endpoint
- React frontend with RTK Query integration
- Tailwind dark UI with backend status indicator
- Vite proxy config for local dev
- Environment config for all planned integrations

### Hackathon MVP (Building Now)
- Auth — email/password signup + JWT
- Workspace + source management
- GitHub repo ingestion (PAT)
- File upload ingestion (drag & drop)
- URL crawl ingestion (paste link)
- Strands Agent with project Q&A system prompt
- `search_docs` tool — vector search over indexed content
- Streaming chat with cited sources
- Onboarding wizard in UI
- Web Chat channel

### Hackathon Demo Stretch
- Teams Bot channel — Bot Framework adapter
- Confluence ingestion (API token)

### Future (Post-Hackathon)
- OAuth login (Google, GitHub, Microsoft)
- Confluence, SharePoint, Jira, Slack connectors
- Real-time source sync via webhooks
- Per-user permission filtering
- Voice I/O via Strands bidirectional streaming
- Multi-agent orchestration

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `GITHUB_TOKEN` | For GitHub | GitHub PAT (repo scope) |
| `DATABASE_URL` | Yes | SQLite path or Postgres URL |
| `JWT_SECRET` | Yes | Secret for signing JWTs |
| `TEAMS_TENANT_ID` | Future | Microsoft Teams tenant |
| `TEAMS_CLIENT_ID` | Future | Teams app client ID |
| `TEAMS_CLIENT_SECRET` | Future | Teams app secret |
| `JIRA_BASE_URL` | Future | Jira instance URL |
| `JIRA_API_TOKEN` | Future | Jira API token |
| `CONFLUENCE_BASE_URL` | Future | Confluence URL |
| `CONFLUENCE_API_TOKEN` | Future | Confluence API token |

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
