# Feature backlog

Written for: the Sensei team.

**Status as of 2026-09-13, evening.** The product is a colleague you onboard:
it reads sources, uses tools the owner granted, does work that comes back as
files, and sits in meetings. What remains is listed honestly below, including
what only the owner of the AWS account can unblock.

## Done

| | Feature | Where it lives |
|---|---|---|
| 1.1 | Onboarding brief (Strands `Graph`, typed) | `agent/brief.py`, `/brief` |
| 1.2 | Gap hunter + drafting | `agent/gaps.py`, `/gaps` |
| 1.3 | Change watch, with a silence condition | `agent/watch.py`, dashboard |
| 1.4 | Answer ledger | `answers/`, `/answers` |
| 1.5 | Sources re-read on a schedule | `agent/watch.py` |
| 1.6 | Freshness in answers — "live from Jira just now" vs "synced" | system prompt, `agent/jira.py` |
| 2.1 | Trust & access page, now with tools by class | `trust/`, `/trust` |
| 2.6 | Credentials and tool tokens encrypted at rest | `core/secrets.py` |
| 2.7a | Per-source visibility per member, enforced in the vector query | `db/membership.py`, `agent/tools.py` |
| 3.1 | Multi-agent `Graph` | brief and gap research |
| 3.2 | Typed artifacts via `structured_output` | briefs, gaps, verdicts, claim verdicts, meeting notes |
| 3.3 | Streaming answers, tool calls narrated | `POST /api/chat/.../stream` |
| **6.1** | **Tool grants — any MCP server, read/write classified, `WriteGate` hook** | `toolgrants/` |
| **6.2** | **Per-turn tool selection and pooled MCP sessions** | `toolgrants/registry.py`, `pool.py` |
| **6.3** | **Work tools: spreadsheets and documents as downloads** | `agent/work.py`, `artifacts/` |
| **6.4** | **`who_did_what` — person graph over activity records** | `agent/people.py` |
| **6.5** | **Jira: live status tools + indexable project** | `agent/jira.py` |
| **7.1** | **Meeting companion — answer / correct / silent, with reasons** | `meetings/listener.py`, `/meetings` |
| **7.2** | **Google Meet bot — captions in, chat replies out** | `meetings/meet_bot.py` |
| **7.3** | **Meeting notes, typed and indexed; transcripts excluded from claim checks** | `meetings/routes.py`, `agent/tools.py` |
| — | Model fallback chain on daily quota | `agent/agent.py` |
| — | Two demo projects built through the API | `scripts/seed_confluence.py`, `scripts/seed_apollo.py` |
| — | 48 unit tests + 7 browser journeys | `backend/tests/` |

## Blocked on someone other than the code

| | What | Who |
|---|---|---|
| Deployment | `deploy/launch-ec2.sh` is one command to a public HTTPS URL. It has not been run from this machine: creating AWS resources was refused by the environment's policy. | run it from a laptop with AWS credentials |
| Bedrock | The account's root credentials cannot call Bedrock at all (AWS refuses root for model invocation). An IAM user or instance role with `bedrock:InvokeModel` is needed; the code path and model ids are ready. | the AWS console, five minutes |
| Groq quotas | The free tier's daily caps were hit twice during testing. The fallback chain routes around a capped model, but a paid key or Bedrock is the safe choice for judging week. | a Groq plan, or the Bedrock IAM user |
| Meet bot verification | Written against Meet's current markup and the caption-pane selectors seen in 2025 builds; the join flow needs a real Meet with a host to admit it. Every step reports to the page so a failure is visible. | a test call with two people |
| Jira on the demo site | The Atlassian site behind the demo has Confluence only. The live tools say so. | enable Jira on the site (free) |
| Teams | Channel abstraction and speak-or-stay-quiet rule exist; no transport. | an M365 tenant |

---

## Still worth building

Ordered by what each buys.

| # | Feature | Why | Effort |
|---|---|---|---|
| 7.4 | **Voice in Google Meet** | The bot replies in chat. Speaking needs a virtual audio device (PulseAudio null sink in the container) and TTS. The judgement is the hard part and it exists. | 4–5h |
| 6.6 | **Confirm-before-write** | A write tool call could pause for a one-tap approval in the UI (Strands interrupts on `BeforeToolCallEvent`) instead of relying on the per-connection switch. Finer than on/off. | 3h |
| 2.7b | **Per-item ACLs from the source** | Sync collaborator lists from GitHub and space permissions from Confluence so the member filter follows the source's own permissions. Needs the GitHub App. | 5–6h |
| 6.7 | **Gmail / Calendar as first-class sources** | Today they come through a Zapier or Google MCP grant. A native OAuth connector with per-label scope would make "what did the client say last week" indexable, not just live. | 5h |
| 4.3 | **Eval harness** | A golden question set per workspace, re-run on every retrieval or prompt change. Quality rots silently otherwise. | 3h |
| 2.5 | **Expiring grants** | 90-day re-attestation for sources and tool grants. | 1–2h |
| 3.5 | **Bedrock AgentCore** | Named in the rules as strengthening Technical Implementation. Runtime needs the IAM user first. | 3–4h |

## Connectors, and which are actually worth it

The rule stands: **never ship a connector that cannot tell you who is allowed
to see each item.** Tool grants change the calculus slightly — a grant is
scoped by the credential the owner chose and gated by class, so it can be
shipped generically — but *indexing* a system still needs ACLs.

| Connector | Verdict |
|---|---|
| **Any MCP server** | Shipped, generically. The owner's credential is the scope; the write gate is the floor. |
| **Jira** | Shipped. Index for finding, read live for status. |
| **Teams** | Highest value, most setup. Built except the transport. |
| **Slack** | A bot reads only channels it was invited to — the cleanest consent story. Transport not built. |
| **GitHub App** (replacing the PAT) | The biggest security improvement available; makes per-item ACLs possible. |
| **Google Drive / SharePoint** | Where documents live; expensive to do properly. After 2.7b. |
