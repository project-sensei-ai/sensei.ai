# Sensei

Permission-aware platform that learns approved project context and participates through chat and Microsoft Teams meetings.

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- Git

---

## Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Edit `.env` with your API keys (Teams, GitHub, Jira, OpenAI, etc.).

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
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Frontend: [http://localhost:5173](http://localhost:5173)
Backend API: [http://localhost:8000](http://localhost:8000)
API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Project Structure

```
hack-agents-for-human/
├── backend/          # FastAPI server
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # React + TypeScript + Tailwind + RTK
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── store/
│   │   └── services/
│   ├── package.json
│   └── vite.config.ts
├── PRD.md            # Product requirements
├── AUTH_PLAN.md      # Auth design & build plan
└── HACKATHON.md      # Hackathon rules & submission checklist
```
