# Sensei — Agent & AI Layer

How the AI and ingestion tools work. This covers the four Strands `@tool` functions, the AI configuration, retrieval behaviour, chat sessions, and an important note on GitHub data semantics.

---

## Strands @tool Functions

All tools live in `backend/agent/tools.py` and are decorated with `@tool` from the Strands Agents SDK. Each returns `list[{"content": str, "metadata": dict}]` — raw documents that the ingestion runner chunks and upserts into ChromaDB.

### `fetch_github(repo, pat)` — async

The most comprehensive tool. Makes up to 20 GitHub API calls per invocation and produces up to 19 distinct document types. Errors on any single endpoint are caught silently — partial data is preferred over a full failure.

**PAT scopes required:** `repo`, `user`, `project`

**Data types fetched:**

| Data type | GitHub endpoint | Notes |
|---|---|---|
| `authenticated_user` | `GET /user` | Profile of the PAT owner — ensures the token holder always appears in queries about people |
| `repo_metadata` | `GET /repos/{r}` | Owner, language, visibility, stars, default branch |
| `collaborators` | `GET /repos/{r}/collaborators?affiliation=all` | Everyone with any access level (owner/admin/write/read) — see note below |
| `org_metadata` | `GET /orgs/{owner}` | Org name, description, public repos |
| `org_members` | `GET /orgs/{owner}/members` | All org members |
| `org_teams` | `GET /orgs/{owner}/teams` + members | Teams and their member lists |
| `file` (×N) | `GET /repos/{r}/contents/{path}` | Up to 200 files; extensions: `.md .py .ts .tsx .js .txt .yaml .yml .json .toml` |
| `commits` | `GET /repos/{r}/commits?per_page=100` | Last 100 commits with author login, date, message, URL |
| `commits_by_author` | derived from commits | Commits grouped by author login — useful for per-person work summaries |
| `contributors` | `GET /repos/{r}/contributors` | Commit count per person (only people who made commits) |
| `pull_requests_open` | `GET /repos/{r}/pulls?state=open` | Last 30 open PRs |
| `pull_requests_closed` | `GET /repos/{r}/pulls?state=closed` | Last 30 closed PRs |
| PR reviews | `GET /repos/{r}/pulls/{n}/reviews` | Per-PR reviewer and verdict (fetched for each PR) |
| `issues_open` | `GET /repos/{r}/issues?state=open` | Last 30 open issues (PRs excluded) |
| `issues_closed` | `GET /repos/{r}/issues?state=closed` | Last 30 closed issues (PRs excluded) |
| `branches` | `GET /repos/{r}/branches` | Name, SHA, protection status |
| `releases` | `GET /repos/{r}/releases` | Tags, authors, release notes |
| `milestones` | `GET /repos/{r}/milestones?state=all` | Open/closed issue counts per milestone |
| `workflows` | `GET /repos/{r}/actions/workflows` | CI/CD pipeline names and state |

#### Contributors vs Collaborators — important distinction

These are two different things and produce different answers from the AI:

| Concept | GitHub endpoint | Who appears |
|---|---|---|
| **Contributors** | `/contributors` | Only people who made git commits |
| **Collaborators** | `/collaborators?affiliation=all` | Everyone with any repo access (org owners included) |

A user who is an org owner or admin but has made zero commits will **appear in collaborators** but **not in contributors**. The AI correctly reflects this — asking "who worked on the code?" routes to commits/contributors data, while "who has access to the repo?" routes to the collaborators data.

Example: `bsaisuryacharan` is an org owner with admin access — appears in collaborators and org_members. `AaadityaG` made the only commit — appears in contributors and commits. Both facts are accurate and both are indexed.

---

### `fetch_urls(urls)` — async

Crawls a list of URLs with `httpx`. Strips HTML via BeautifulSoup `.get_text()`. Returns one document per URL.

URL sources are pre-validated at `POST /sources` time: a HEAD request is sent (fallback to GET on 405); 4xx responses return a 422 before the source is even stored.

---

### `parse_file(file_path, filename)` — sync (thread pool)

Dispatches on file extension. Runs inside `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the event loop.

| Extension | Parser |
|---|---|
| `.pdf` | pypdf `PdfReader` |
| `.docx` | python-docx |
| `.md`, `.txt` | `open()` |

---

### `fetch_confluence(base_url, email, api_token, space_key)` — async

Fetches pages from a Confluence space via REST API `/rest/api/content`. Strips HTML from page body storage format. Authenticates with Basic auth (email + API token).

---

## AI Layer

### Model

`openai/gpt-oss-120b` via Groq API. Temperature `0.1`, max tokens `1024`.

Other models available on this key: `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`, `groq/compound`, `allam-2-7b`.  
**Do not use** `llama-3.1-8b-instant` — returns 404 on this key.

### System Prompt

`SENSEI_SYSTEM_PROMPT` in `agent/agent.py`. It does two jobs: it tells the model
*when* to reach for the search tool, and it sets the honesty rule.

- **Project questions** — code, architecture, team, commits, PRs, issues, docs,
  decisions — must go through `search_project_docs`. Claims are cited inline with
  the source label, e.g. `[my-repo]`. If nothing relevant comes back, the agent
  says so rather than inventing project detail.
- **General questions** — greetings, ordinary programming help — are answered
  directly, without a tool call.

The split exists because a single-mode prompt fails in one of two ways: index-only
prompts refuse to say hello, and unconstrained prompts fabricate project facts.

### Retrieval

ChromaDB `collection.query(query_texts=[question], n_results=min(5, count))`.

- Embedder: sentence-transformers `all-MiniLM-L6-v2` (default ChromaDB embedder)
- Distance metric: cosine
- Score returned to frontend: `1 − distance` (1.0 = perfect match)
- Citations deduplicated by source label across **every tool call in a turn**, not
  just within one call. The agent loop usually calls `search_project_docs` three
  or four times per question; per-call dedup meant the same document came back
  once per call. The `seen_labels` set lives in the tool factory closure so it
  spans the whole turn, and `index` is assigned from the running total.

Collection name per workspace: `ws_{workspace_id}`.

### Re-ingest Cleanup

Before writing new chunks, `collection.delete(where={"source_id": source_id})` removes all stale chunks from the previous run. This prevents orphaned chunks when re-ingesting produces a different chunk count. ChromaDB `upsert` is used for the write itself (batches of 500).

---

## Chat Sessions

Chat is session-scoped and persisted in MongoDB `chat_sessions`.

**Session lifecycle:**
1. `POST /chat/sessions` — creates an empty session with title "New chat"
2. `POST /chat/sessions/{id}/messages` — sends a message; both the user message and AI response are appended to the session's `messages` array
3. Session title auto-set from the first user message (60 chars max)
4. `DELETE /chat/sessions/{id}` — archives the session (`archived: true`), removes it from the list
5. Archived sessions are soft-deleted — data is kept in MongoDB, just not shown

**MongoDB document shape:**
```
chat_sessions
├── _id              (UUID, no dashes)
├── workspace_id
├── owner_id
├── title            (set from first message)
├── messages[]
│   ├── role         (user | assistant)
│   ├── content
│   ├── citations[]  (assistant only)
│   └── created_at
├── created_at
├── updated_at       (used for sort order in sidebar)
└── archived         (bool)
```

---

## Ingestion Pipeline (code flow)

```
POST /ingest/{source_id}
  → set status = "indexing" (sync)
  → return 202
  → [BackgroundTask]
        ↓
  run_ingestion(db, chroma_client, source_id)    [agent/ingest.py]
        ↓
  dispatch by source.type → fetch tool
        ↓
  list[{content, metadata}]
        ↓
  _chunk_text() — 2000-char windows, 200-char overlap
  chunk IDs: {source_id}_0, {source_id}_1, ...
        ↓
  collection.delete(where={"source_id": ...})    ← clean slate
  collection.upsert(ids, docs, metadatas)         ← batches of 500
        ↓
  MongoDB: status = "ready", stats = {chunks_count, pages_crawled}
  on exception: status = "error", error_message = str(exc)
```

Frontend polls `GET /ingest/{source_id}/status` every 4 seconds until `ready` or `error`.

---

## Chat Pipeline (code flow)

The route does not run a retrieval pipeline of its own — it hands the question to
the Strands agent loop and lets the agent decide whether and how often to search.

```
POST /api/chat/sessions/{session_id}/messages  {question}
  → auth + membership + session ownership check
        ↓
  build_agent(workspace_id, chroma, session_manager)     [agent/agent.py]
    ├─ model  ← LLM_BACKEND: BedrockModel | Groq | Ollama
    ├─ tools  ← make_search_tool(workspace_id, chroma)
    │            (+ search_knowledge_base when BEDROCK_KB_ID is set)
    └─ session_manager ← S3SessionManager when S3_SESSION_BUCKET is set
        ↓
  asyncio.to_thread(agent, question)      Agent.__call__ is synchronous
        ↓
  ── the agent loop ──────────────────────────────────
     the model decides which tools to call, and may call
     search_project_docs several times with different queries
     before it has enough to answer
     each call appends deduplicated citations to `captured`
  ────────────────────────────────────────────────────
        ↓
  MongoDB $push [user_msg, ai_msg]
  $set title from first message if session was empty
        ↓
  return {answer, citations}
```
