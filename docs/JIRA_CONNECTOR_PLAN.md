# Jira Connector — Implementation Plan

A new source type that indexes issues from an Atlassian Jira Cloud site. Follows
the existing Confluence connector almost line for line — same Atlassian
identity, same auth, a different endpoint.

Also updates `docs/CONNECTOR_ACCESS.md` (already stubbed) and
`docs/FEATURE_BACKLOG.md` (line 65 marks Jira as "Currently a colleague's").

---

## What gets indexed

One source = one project key. For each issue in the project we fetch the text a
person would actually ask about:

- **Issue fields** — summary, description, status, priority, labels, assignee
- **Comments** — each comment is its own document
- **Changelog** (optional stretch) — resolved/blocked/unblocked transitions

**Not indexed:** board/backlog layout, sprints, permissions, attachments.

**Auth:** same as Confluence — site URL, account email, API token (Basic auth).
The owner who already connected Confluence has everything this connector needs.

**Read API:** `GET /rest/api/3/search` with JQL `project = <KEY>`, fields filter,
paginated. Issue permalinks are `{base}/browse/{key}` for citations.

**Fresh-site caveat (implemented):** brand-new free Jira Cloud sites can answer
`410 Gone` on `/rest/api/3/search` (and `/rest/api/2/search`) until their JQL
search index is built — everything else (auth, project, individual issues,
agile boards) works. When search 410s or 404s, `fetch_jira` transparently falls
back to listing issues through the agile board endpoint
(`/rest/agile/1.0/board/{id}/issue`, boards filtered by `projectKeyOrId=<KEY>`),
deduplicated by issue key since an issue can sit on several boards.

---

## Backend changes (4 pieces, all additive)

### 1. `backend/agent/tools.py` — `fetch_jira(base_url, email, api_token, project_key)`

Mirror `fetch_confluence` (tools.py:389). Returns `list[{content, metadata}]`:

- Paginate `search` with `maxResults=50`, `startAt`, cap ~300 issues (match the
  Confluence cap). Body text comes back as Jira's **ADF** (Atlassian Document
  Format), not HTML — flatten with `BeautifulSoup` after converting, or walk the
  `content` nodes directly.
- Errors on a single issue are caught silently, like `fetch_github` — partial
  data beats a failed run.
- ADF has no 256-token problem: the shared `_chunk_text` in `ingest.py` stays.

Metadata per document: `source: "jira"`, `title` (e.g. `PROJ-42: Fix login`),
`issue_key`, `status`, `data_type` (`issue` | `comment`), and the issue permalink
for citations.

### 2. `backend/sources/routes.py` — `JiraSourceIn` + branch in `add_source`

Add a `Literal["jira"]` variant to the discriminated union (routes.py:163), plus:

- `_verify_jira(body)` mirroring `_verify_confluence` (routes.py:70): Basic auth
  against `/rest/api/3/myself`, then `search?jql=project=<KEY>&maxResults=1`.
  A wrong project key lists the visible ones — same UX as the Confluence space
  check.
- `add_source` branch (routes.py:198): store `base_url`/`email`/`project_key` in
  `config`, the `api_token` in `config_secret` (Encrypted by `_source_doc`).
- Reuse the Confluence URL-normaliser logic for the site field
  (`…/jira/…` → site root).

### 3. `backend/agent/ingest.py` — dispatch branch

`elif source["type"] == "jira":` (ingest.py:83 pattern), decrypting
`config_secret` and calling `fetch_jira`. Chunking, delete-then-upsert, stats,
research-cache eviction, gap audit — all shared, no changes.

### 4. `backend/agent/watch.py` — change-watch branch

Add to the dispatch at watch.py:76 so "Check for changes" re-reads Jira too.
Same three lines the other connectors use.

---

## Frontend changes (3 spots, all additive)

1. **`frontend/src/services/onboardingApi.ts`** — add `'jira'` to the `SourceType`
   union (line 22) and to `AddSourceInput` (line 251).
2. **`frontend/src/pages/Sources.tsx`** — new `Tab = 'jira'`, a form (site URL,
   email, API token, project key), `TYPE_ICON` entry (Sources.tsx:43), and the
   submit handler calling `addSource({ type: 'jira', … })` then `triggerIngest`.
3. **`frontend/src/pages/onboarding/StepSources.tsx`** — surface Jira the same way
   Confluence is surfaced, so a new owner can pick it in the wizard.
   `StepReview.tsx` shows `TYPE_LABELS[source.type]` — add the label there.

---

## User flow (already handled by the pipeline)

```
POST /sources {type:"jira", …}   → _verify_jira → stored, encrypted, pending
POST /ingest/{id}                → 202 → BackgroundTask
  run_ingestion → fetch_jira     → list[{content, metadata}]
  _chunk_text (800/150)          → collection.delete + upsert
  status = ready · stats = {chunks_count, pages_crawled}
  → research_cache evicted · gap scan triggered
Chat → search_project_docs       → citations [PROJ-42: Fix login] with permalink
```

Nothing in the agent loop, citations, or chat changes — Jira-content chunks flow
through the same search tool as every other source.

---

## Trust statement (reuse Confluence copy)

docs/CONNECTOR_ACCESS.md's Jira section already exists (line 67). Only change is
flipping "Future" → current in `docs/ARCHTECTRUE.md:107` and un-stubbing the
backlog line. The form should repeat the existing copy: reads only the named
project, the token could reach everything the account sees.

---

## Testing

Coverage targets the two things that can actually break: the **ADF flattening**
and the **JQL verification path** (both hit real HTTP, neither can be trusted by
eye). No framework additions — the repo already has pytest unit tests and
browser journeys.

### Unit — `backend/tests/test_jira.py`

- **ADF → text**: a fixture ADF JSON (paragraphs, headings, inline code)
  flattens to the expected string. This is the `test_parsing.py` analogue.
- **Dispatch**: `run_ingestion` with a fake `app.state` routes a `jira` source
  through `fetch_jira` — but swappable, so the assertion is "the right tool was
  called with the right config", not a live API.
- **Route schema**: `JiraSourceIn` validates; a wrong project key produces a
  422 with the "no issue found" message (use `asgi-lifespan`/`TestClient` like
  the other route tests).
- **Envelope**: `serialize_source` never leaks `config_secret` for a jira source
  (the existing secrets test pattern).

### E2E — `backend/tests/e2e/test_journeys.py`

Only if there is a real Jira to hit (a free Cloud instance). One journey:
connect a Jira source → index → ask "status of PROJ-1" → assert a citation
labelled from the issuer arrives. Skip-guarded so the suite stays green without
credentials — same pattern the existing `E2E_OWNER_PASSWORD` journeys use.

### Manual smoke (no account needed)

Point the connector at a public-ish instance or a throwaway Cloud trial: verify
the form rejects a wrong project key, that a real key reaches `status = ready`,
and that the Sources card shows `N chunks · M pages`.

---

## Deliberately skipped (say when they earn their keep)

- **Live "current status" reads.** CONNECTOR_ACCESS.md argues a ticket's status
  changes hourly and should be read live, not from a stale index. That is a
  second, separate tool (`get_jira_issue(issue_key)`), meaningful only after the
  connector exists — this plan ships the index-only half.
- **Per-issue changelog fetch.** An extra API call per issue; skip unless
  "when did this get blocked?" questions show up.
- **JQL/board selection UI.** One project per source keeps the form and the
  trust statement identical to Confluence.