# Testing Sensei

Everything a reviewer needs to exercise the project, either on the hosted
instance or locally.

---

## 1. Hosted instance

**URL:** `<LIVE_URL>`  ← fill in after deploying

### Demo account

A workspace is pre-loaded with Sensei's own documentation, so you can ask real
questions the moment you log in — no tokens or API keys required.

| | |
|---|---|
| Email | `judge@sensei.demo` |
| Password | `Demo-miwVU8NczE6N` |

Sign in at `<LIVE_URL>/login`, then open **Chat**.

### Questions that show it working

Each answer carries inline citations back to the document it came from.

- *What problem does Sensei solve, and who is it for?*
- *How does the ingestion pipeline work?*
- *Which model backends are supported and how do I switch between them?*
- *What data does the GitHub connector actually fetch?*
- *What is the difference between contributors and collaborators?* — the
  interesting one: these are two different GitHub concepts with two different
  answers, and the agent keeps them apart.

Ask it something the workspace does not cover — *"what is our AWS bill?"* — and
it will say it cannot find that rather than inventing a figure.

---

## 2. The invite flow (two accounts)

This is the multi-user path, and it needs a second account.

1. Log in as `judge@sensei.demo` and open **Onboarding → step 4**, or the
   workspace settings, to generate an invite link.
2. Open that link in a private window.
3. Register a throwaway account — the invite token survives the sign-up
   redirect.
4. You land in the same workspace as a **member**: you can read the source
   list and chat, but **Sources** shows *Read-only* and the add/delete controls
   are gone. The API returns 403 for member writes.

---

## 3. Running locally

Full setup is in [README.md](README.md). Short version:

```bash
# backend
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set MONGO_DB, JWT_SECRET, GROQ_API_KEY, DEBUG=true
uvicorn main:app --reload --port 8000

# frontend, in a second terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5173.

Required in `backend/.env`:

| Variable | Notes |
|---|---|
| `MONGO_DB` | MongoDB Atlas connection string (free tier is fine) |
| `MONGO_DB_NAME` | defaults to `sensei` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `GROQ_API_KEY` | free at [console.groq.com](https://console.groq.com) |
| `DEBUG` | `true` locally — drops the `Secure` cookie flag so login works over HTTP |

No AWS account is needed: `LLM_BACKEND` defaults to `groq`. Set it to
`bedrock` (with AWS credentials) or `ollama` (fully offline) to switch.

### One container instead

```bash
docker compose up --build     # builds the SPA and serves everything on :8000
```

---

## 4. Connecting your own sources

As the workspace **owner**, on the **Sources** page:

- **GitHub** — a personal access token with `repo`, `user`, `project` scopes.
  Pulls 19 data types: files, commits, contributors, collaborators, org members
  and teams, PRs with reviews, issues, branches, releases, milestones, workflows.
- **File** — pdf, docx, md, txt, up to 20 MB.
- **URL** — any public page; each is reachability-checked before it is stored.
- **Confluence** — base URL, account email, API token, space key.

Sources index in the background; the page polls and shows live status. Deleting
a source removes its vectors too.

---

## 5. Scope

Implemented: onboarding, the four connectors above, background ingestion,
membership and roles, the invite/join flow, cited chat with persistent sessions,
and three interchangeable model backends.

Not implemented, and not claimed in the demo: Microsoft Teams and Slack
channels, meeting participation, Jira and ServiceNow connectors, per-item ACL
filtering, and continuous source sync. The plan for those is in
[docs/STRATEGY_AND_BUILD_PLAN.md](docs/STRATEGY_AND_BUILD_PLAN.md).
