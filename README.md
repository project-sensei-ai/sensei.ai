# Sensei

Permission-aware AI platform that ingests your project sources (GitHub, files, URLs, Confluence) into a knowledge base and answers questions with cited sources. Built with Strands Agents SDK for the AWS hackathon.

## Prerequisites

- Python 3.12+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Groq API key (free at [console.groq.com](https://console.groq.com))

---

## Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env`:

```
MONGODB_URI=mongodb+srv://...
JWT_SECRET=your-secret-here
GROQ_API_KEY=gsk_...
CHROMA_PERSIST_DIR=./chroma_data
FRONTEND_ORIGIN=http://localhost:5173
```

### Frontend

```bash
cd frontend
npm install
```

---

## Run

Open two terminals:

**Terminal 1 — Backend**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

---

## How It Works

1. **Sign up** → create a workspace (one per user)
2. **Add sources** — GitHub repo (PAT), file upload, URL, or Confluence
3. **Ingest** — sources are chunked and embedded into ChromaDB (runs in background)
4. **Chat** — ask questions, get answers with inline citations linking back to the source

GitHub ingestion extracts 19 data types: file contents, commits, contributors, collaborators (including org owners), org members, teams, PRs with reviews, issues, branches, releases, milestones, and CI/CD workflows. See `Agents.md` for details.

---

## Project Structure

```
agents-for-humans/
├── backend/
│   ├── main.py              # FastAPI app + lifespan (MongoDB + ChromaDB)
│   ├── auth/                # JWT auth + Google OAuth
│   ├── workspaces/          # Workspace CRUD + invite links
│   ├── sources/             # Source management + file upload
│   ├── ingest/              # Background ingestion trigger + status
│   ├── chat/                # Chat sessions + Groq Q&A
│   ├── agent/
│   │   ├── tools.py         # Strands @tool functions (fetch_github, fetch_urls, etc.)
│   │   └── ingest.py        # Chunking + ChromaDB upsert pipeline
│   ├── db/                  # MongoDB + ChromaDB helpers
│   └── core/config.py       # Settings
├── frontend/
│   ├── src/
│   │   ├── pages/           # Login, Register, Onboarding, Sources, Chat, Dashboard
│   │   ├── components/      # AppShell, ProtectedRoute, OnboardingRoute
│   │   └── services/        # RTK Query API hooks
│   └── vite.config.ts       # /api proxy → localhost:8000
├── docs/
│   ├── ARCHTECTRUE.md       # Full architecture, API map, DB schema
│   └── PRD.md
└── Agents.md                # Tool functions, AI layer, pipeline details
```
