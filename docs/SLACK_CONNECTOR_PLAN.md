# Slack Connector — Implementation Plan

A new source type that indexes messages from a Slack channel. Two things make it
different from the Atlassian connectors:

- **It is the first OAuth-bot connector, not a shared human credential.** The
  grant is a bot token from a Slack App the owner creates. The consent story is
  the cleanest of any connector: *the invite is the grant, and removing the bot
  is the revocation* (this is exactly how `docs/FEATURE_BACKLOG.md:66` frames it
  — keep that framing).
- **One source = one channel** (mirroring one space / one project). A whole
  workspace is a deliberately-skipped later step, because the bot token can see
  every channel the app is in, and bounding the *floor* to one channel keeps the
  trust statement identical to Confluence/Jira.

Also updates when built: `docs/CONNECTOR_ACCESS.md`, `docs/ARCHTECTRUE.md:109`
(Slack row "Future" → current), `docs/FEATURE_BACKLOG.md:66`.

---

## What gets indexed

One source = one channel. For the recent history of that channel we fetch the
text a person would actually ask about:

- **Top-level messages** — text, sender display name, timestamp
- **Threaded replies** — each reply is its own document, linked to the parent
  (`conversations.replies`), so "what were we saying on that thread" is
  searchable independently
- **Identity** — user IDs resolve to display names via one `users.list` call per
  ingest, so `@aditya` shows up as `@Aditya K` in the same way Jira resolves
  displayName

**Not indexed:** files and attachments, reactions, DMs, channel topics/descriptions,
Slack's own semantic search, anything outside the one named channel.

**Auth:** Slack App → bot token (`xoxb-…`), installed to the workspace and added
to the channel. Token never expires (unlike the 1-year Atlassian ones). Scope:
`channels:history`, `channels:read`, `groups:history`, `groups:read`,
`users:read`, `team:read`.

**Read API:** `conversations.history` (cursor-paginated, newest → oldest),
`conversations.replies` per threaded parent, `conversations.list` / `users.list`
for resolution. Permalinks are the universal Slack form
`https://{team_domain}.slack.com/archives/{channel_id}/{ts}` — the team domain
comes from `auth.test` at connect time, so no per-message permalink calls.

**Snapshots, not live tails.** Same shape as Jira's "last 100 commits": the most
recent ~300 messages, re-fetched at ingest time. Alt-text copy stays honest —
the agent answers from the index, not from Slack's live stream.

---

## Backend changes (4 pieces, all additive)

### 1. `backend/agent/tools.py` — `fetch_slack(bot_token, channel_id, channel_name, team_domain)`

Mirror `fetch_jira` (tools.py:467). Returns `list[{content, metadata}]`:

- `conversations.history` paged with `cursor`; cap ~300 docs (reuse the
  Confluence/Jira cap). Users resolved once via `users.list` into a
  `{user_id → display_name}` map.
- Slack message text is **mrkdwn**, not HTML or ADF. A small `_strip_mrkdwn`
  helper parallels `_adf_text`: `<@U123|Name>` → `Name`, `<@U123>` → the
  resolved name, `<url|label>` → `label`, `<url>` → `url`. Leave `*bold*` /
  `` `code` `` markers alone — the embedder handles them fine.
- Thread replies come back as parent + each reply as its own document
  (`data_type: "reply"`), the way Jira comments do.
- Errors on a single endpoint are caught so partial data beats a failed run
  (same rule as `fetch_github`).

Metadata per document: `source: "slack"`, `title` (`@User in #channel`),
`channel`, `channel_id`, `author`, `data_type` (`message` | `reply`), and the
thread/ts permalink for citations.

### 2. `backend/sources/routes.py` — `SlackSourceIn` + branch in `add_source`

Add a `Literal["slack"]` variant to the discriminated union, plus:

- `_verify_slack(body)` mirroring `_verify_jira` (routes.py:161): `auth.test`
  confirms the token and yields the team domain; the channel field is resolved
  `#general` → channel id via `conversations.list`, and `conversations.info`
  confirms the bot can read it. A wrong channel lists the ones the bot can see —
  same UX as the Confluence space check. A `not_in_channel` error says exactly
  that: *"Open the channel → Details → Add apps → add this app."*
- `add_source` branch: store `channel_id` / `channel_name` / `team_domain` in
  `config`, the bot token in `config_secret` (encrypted by `_source_doc`).
- Channel-field normaliser: strip `#`, reject empty / non-channel garbage with a
  usable message (`SlackSourceIn` validator), mirroring the Jira URL validator.

### 3. `backend/agent/ingest.py` — dispatch branch

`elif source["type"] == "slack":` (ingest.py:83 pattern), decrypting
`config_secret` and calling `fetch_slack`. Chunking, delete-then-upsert, stats,
research-cache eviction, gap audit — all shared, no changes.

### 4. `backend/agent/watch.py` — change-watch branch

Add to the dispatch at watch.py:76 so "Check for changes" re-reads Slack too.
Fetch passes `oldest` (last indexed message ts) for a cheap incremental read;
same three lines the other connectors use.

---

## Frontend changes (3 spots, all additive)

1. **`frontend/src/services/onboardingApi.ts`** — add `'slack'` to `SourceType`
   and to `AddSourceInput`.
2. **`frontend/src/pages/Sources.tsx`** — new `Tab = 'slack'`, a form (bot token,
   channel name), `TYPE_ICON` entry, and the submit handler calling
   `addSource({ type: 'slack', … })` then `triggerIngest`. Both fields carry the
   `FieldHelp` ⓘ-button: the token one walks through
   `api.slack.com/apps → Create App → scopes → Install to workspace → Copy the
   OAuth token`; the channel one says to pick the `#` name and that the bot must
   be added to it.
3. **`frontend/src/pages/onboarding/StepSources.tsx`** — surface Slack like the
   other connectors so a new owner can pick it in the wizard.
   `StepReview.tsx` gets the `TYPE_LABELS` entry.

---

## User flow (already handled by the pipeline)

```
POST /sources {type:"slack", …}  → _verify_slack → stored, encrypted, pending
POST /ingest/{id}                → 202 → BackgroundTask
  run_ingestion → fetch_slack     → list[{content, metadata}]
  users.list (names) → conversations.history → replies
  _chunk_text (800/150)          → collection.delete + upsert
  status = ready · stats = {chunks_count, pages_crawled}
  → research_cache evicted · gap scan triggered
Chat → search_project_docs       → citations [@User in #channel] with permalink
```

Nothing in the agent loop, citations, or chat changes.

---

## Trust statement (reuse the Confluence/Jira copy, adjusted)

The form's "What this grants" box says the same three things, with Slack's
edits:

- **Sensei reads:** `#general` only. Nothing else is fetched or indexed.
- **The token could reach:** every channel the app has been added to — and a
  bot token cannot be narrowed to one channel by Slack.
- **So:** use a dedicated "Sensei" app and add it to *only* the channels this
  work involves. The invite is the grant; removing the app is the revocation.

This is the same ceiling/floor framing as Jira, playing out as "the invite is
the ACL" instead of "a project key narrows a token".

---

## Testing

The two things that can actually break are the **mrkdwn stripping** and the
**channel / token verification path** (both hit real HTTP). Same shape as the
implemented `backend/tests/test_jira.py` — plain pytest, fake clients, no
framework additions.

### Unit — `backend/tests/test_slack.py`

- **mrkdwn → text**: `<@U123|Name>` strips to `Name`, `<@U123>` resolves through
  the user map (falling back to the id), `<url|label>` and `<url>` collapse, and
  `*bold*`/`` `code` `` survive. This is the `_adf_text` analogue.
- **Channel normalisation**: `SlackSourceIn` accepts `general` and `#general`,
  rejects empty/garbage with a usable message (Jira validator analogue).
- **Verify**: fake client asserting `auth.test` + `conversations.info` are called
  with the right token; a bad channel produces the "channel not visible" message
  listing what the bot can see; a `not_in_channel` error maps to the
  "add the app to the channel" copy.
- **`fetch_slack` paginates**: fake history client across two cursor pages with a
  threaded parent; asserts replies became their own documents, authors resolved,
  permalink shaped `…/archives/C123/1234567890.000000`.
- **Envelope**: `serialize_source` never leaks the bot token for a slack source
  (existing secrets test pattern).

### E2E — `backend/tests/e2e/test_journeys.py`

Only if there is a real workspace to hit. One skip-guarded journey: connect a
channel → index → ask "what did we say in #general last week" → assert a
citation labelled from the channel arrives. Same pattern as the existing
`E2E_OWNER_PASSWORD` journeys.

### Manual smoke (no account needed)

Create a throwaway Slack workspace + app: verify the form rejects a channel the
bot cannot see, that a real channel reaches `status = ready`, and that the
Sources card shows `N chunks · M pages`.

---

## Deliberately skipped (say when they earn their keep)

- **Whole-workspace sources.** One channel per source keeps the form and trust
  statement identical to Confluence/Jira. A "workspace" source is a real product
  decision (and a big index) — not a Friday change.
- **Slack's own search (`search:read`).** History already gives us everything;
  Slack's index adds nothing we don't have.
- **Files / attachments.** Thread text answers most questions. Add file-parsing
  only when "what's in that PDF we shared" shows up.
- **Reactions and emoji.** Signal, but not what people ask about.
- **DMs and Slack Connect.** Scope creep; the trust story gets murkier.
- **Realtime events / WebSockets.** The watch poll at ingest-time is enough;
  a socket is a bigger surface for the same five questions.