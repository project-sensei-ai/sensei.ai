# Sensei — Market Research & Build Plan

Written for: the Sensei project owner (solo founder/builder), as the decision document for the next 48 hours and the 6 months after.

Status: research complete, plan proposed, **not yet implemented**. Research done 2026-09-12.

---

## 0. Timeline reality check (read this first)

| Fact | Source |
|---|---|
| Hackathon submission deadline | **Sep 14, 2026, 5:00 PM PDT** (`docs/HACKATHON.md`) |
| Today | Sep 12, 2026 |
| Planned feature freeze | Sep 10 — **already passed** |
| Last code commit | **Aug 26, 2026** — 17 days ago |
| AWS $50 credits form | Closed Sep 11, 12:00 PM PT — **missed** |
| Still missing from the required checklist | Architecture diagram (image), ≤5-min demo video, live demo URL, judge test credentials, builder.aws.com bonus posts |

**Consequence:** the architecture in sections 1–3 and 5 of this document is a 6-month business build. It is *not* what gets implemented in the next 48 hours. Section 5 is therefore split into three horizons, and **Horizon 0 is deliberately tiny**: close the broken demo path, produce the submission assets, ship nothing new. Judging criteria weight Presentation and Design at 40% combined; a video of a working narrow demo scores far above a half-built broad one that breaks on camera.

---

## 1. Does this already exist?

Short answer: **every individual capability exists and is well funded. The specific combination does not — but the gap is narrower than it looks, and the two biggest platform vendors are walking into it.**

### 1.1 The four categories that overlap with Sensei

**A. Permission-aware enterprise search + agents** — the closest match to Sensei's retrieval layer.

| Product | What it is | Relevance |
|---|---|---|
| **Glean** | 100+ connectors, document-level ACL sync, agents tier. ~$300M ARR at a $7.2B valuation (May 2026), ~$40–50/user/mo, ~100-seat minimum, $60k+ annual floor | The category king. Does permission-aware retrieval properly. Does **not** join meetings as a participant. |
| **Onyx** (ex-Danswer) | MIT-licensed, self-hostable, agentic RAG, syncs permissions from Confluence, Jira, Drive, Slack, Salesforce, GitHub, SharePoint. ~$20/user/mo cloud | The open-source Glean. **This is your reference implementation for ACL sync** — read their connector code rather than inventing it. |
| **Dust** | MIT-licensed, agent-builder-first rather than search-first, ~€29/user/mo | Closest philosophical match: "agents that act, not just retrieve". |
| **GoSearch / Akooda / Sentra / Coveo / Sinequa** | Enterprise search with agent actions | Crowded mid-tier. |
| **Dashworks** | AI knowledge assistant, raised $5M seed | **Acquired by HubSpot (Apr 2025)** — signal that this layer gets absorbed by platform owners. |

**B. Platform-native project context graphs** — the existential threat.

- **Atlassian Rovo + Teamwork Graph.** Agents in Jira launched **Feb 24, 2026**: assignable like teammates, governed by existing Jira permissions, with audit trails. Teamwork Graph connectors now cover **Slack, Teams, Gmail, Outlook, GitHub, GitLab, Azure DevOps, ServiceNow, Sentry, PagerDuty, Notion, Salesforce, Figma** — 75+ tools. **Rovo is bundled free into Jira/Confluence/JSM Standard+**, with pooled monthly credits (25/70/150 per user by tier) and **search costing zero credits**. There is also a Teamwork Graph MCP server for external agents.
- **Microsoft 365 Copilot + Graph connectors.** Copilot connectors index external content (Jira, ServiceNow, file shares) into the same semantic graph as Teams/SharePoint/mail, **carrying each item's ACL so permission trimming is preserved**. Federated Copilot Connectors went GA May 2026 for real-time SAP/Salesforce/ServiceNow reads without copying data.
- **Slack / Agentforce.** Slackbot relaunched Jan 2026 as "the ultimate AI teammate" for Business+/Enterprise+.

**Read this carefully: Atlassian gives away, for free, inside the tool your customer already pays for, a large part of what Sensei charges for.** Any pitch that is "we answer questions across Jira + Confluence + GitHub" is dead on arrival in an Atlassian shop.

**C. Meeting agents** — the channel Sensei wants.

- **Otter Meeting Agent** — voice-activated ("Hey Otter"), answers spoken questions live in the meeting, draws on prior company meetings, schedules follow-ups, assigns action items. Zoom today, Teams and Meet rolling out. **This is the single closest product to Sensei's meeting feature.** Its weakness: its knowledge is *meetings*, not Jira/ServiceNow/repos.
- **Recall.ai** — the infrastructure layer. One API to put a bot into Zoom, Meet, Teams, Webex, Slack Huddles, GoTo; real-time transcript via webhook with sub-second latency; can output audio/video back into the meeting. SOC 2, ISO 27001, GDPR, HIPAA. **Do not build meeting joining yourself — buy this.**
- Fireflies, Granola, Circleback, Spinach, Read.ai, Zoom AI Companion, Teams Facilitator — all notes-and-summary, mostly not live-answering.

**D. "AI coworker" platforms** — Viktor, Teammates.ai, CloneForce, Arlo, Lindy. Mostly task-execution bots in Slack/Teams with thin knowledge layers and no permission model. Loud category, weak substance.

### 1.2 Verdict

| Sensei capability | Already owned by | Can you win it? |
|---|---|---|
| Permission-aware retrieval across tools | Glean, Onyx, Copilot, Rovo | **No.** Table stakes. Copy Onyx's approach; do not differentiate here. |
| Live ticket/PR status answers | Rovo, Copilot, Jira Delivery Agent | **No.** Table stakes. |
| Joins meetings and answers live | Otter (voice), Recall.ai (infra) | **Partially** — nobody answers live *from Jira/ServiceNow/repo state with citations*. Otter answers from meetings; Rovo/Copilot don't reliably attend meetings and speak. |
| Structured onboarding of an agent, with an auditable access ledger | **Nobody productizes this** | **Yes. This is the gap.** |
| Cross-vendor (Atlassian *and* ServiceNow *and* Azure DevOps *and* Teams) in one agent | Glean, Onyx | Only matters where the customer is genuinely multi-vendor — which is exactly the IT-services / GCC world. |

### 1.3 The defensible wedge

Three things to say no to and one thing to own.

Say no to: "enterprise search" (Glean owns it), "AI notetaker" (Otter owns it), "Jira assistant" (Atlassian gives it away).

Own this: **the agent is onboarded, scoped, verified and audited like an employee.** Every competitor treats connector setup as a settings page. Nobody treats it as *hiring*: a role definition, an access grant ledger, a probation period where answers are reviewed before going live, a "what do you actually know?" verification report, a quarterly access review, and a revocation button with a provable audit trail.

This matters commercially because the blocker on agent adoption is not capability, it is the security review. Industry data: **80% of organisations report their AI agents have already acted beyond intended scope** — 39% accessed unauthorised systems, 31% inappropriately shared sensitive data, 23% revealed credentials. The buyer who signs your contract is not the dev lead who wants answers; it is the person who has to defend the access grant to an auditor.

So the product is: **a permission-aware project teammate whose entire access surface is a reviewable, revocable, auditable artifact** — and whose differentiated channel is live meeting participation grounded in work-system state, not just transcripts.

Sharp positioning line: *"Every other AI tool asks you to connect an integration. Sensei asks you to onboard a colleague — and hands you the paperwork."*

---

## 2. What companies actually run (connector priority)

### 2.1 Large enterprise / MNC

Characterised by: Microsoft-centred, multi-vendor by acquisition, SSO-mandatory, procurement-gated, 3–9 month sales cycles.

| Function | What they run |
|---|---|
| Identity | **Microsoft Entra ID** (dominant), Okta, Ping, SailPoint for governance |
| Comms | **Microsoft Teams** (default where M365 is licensed), Outlook |
| Docs / wiki | **SharePoint + Confluence** (usually both), OneDrive, Word/Excel/PowerPoint |
| Work tracking | **Jira** (eng) + **ServiceNow** (IT/HR/ITSM — 44.4% ITSM market share) + Azure DevOps Boards |
| Code | **GitHub Enterprise**, **Azure DevOps Repos**, GitLab Self-Managed, legacy Bitbucket/SVN |
| CI/CD | Jenkins, Azure Pipelines, GitHub Actions, Harness |
| Observability | Splunk, Datadog, Dynatrace, AppDynamics |
| Design | Figma |
| ERP/HR | SAP S/4HANA, Oracle Fusion, Workday, SuccessFactors |
| Meetings | **Teams**, Zoom (sales orgs), Webex (telco/regulated) |

### 2.2 Startup / scaleup

Characterised by: Google- or Slack-centred, single-vendor-per-function, self-serve purchase, 1–14 day sales cycles, credit card.

| Function | What they run |
|---|---|
| Identity | **Google Workspace**, Okta/WorkOS at Series B+ |
| Comms | **Slack** |
| Docs / wiki | **Notion** (dominant), Google Docs, Linear Docs, Coda |
| Work tracking | **Linear** (taking ~30% share from Jira at team level, $8 vs $17.65/user), Jira, Asana, ClickUp, Shortcut, GitHub Issues |
| Code | **GitHub** (near-universal) |
| CI/CD | GitHub Actions, Vercel, Railway, Fly.io |
| Support/ITSM | Zendesk, Intercom, Freshservice, Linear for bugs |
| Observability | Sentry, PostHog, Datadog |
| Meetings | **Google Meet**, Zoom, Slack Huddles |
| Stack | Next.js + TypeScript + Tailwind + Postgres/Supabase + Vercel + Stripe |

### 2.3 The third segment you are actually closest to: IT services / GCC / offshore delivery

This is the segment where Sensei's multi-vendor breadth is a real advantage rather than a liability, and where the pain is most acute. Think TCS/Infosys/Wipro/Accenture/Capgemini delivery teams, and the captive GCCs of Western enterprises in India.

Why it fits:
- **Stack is forcibly multi-vendor.** The client dictates it. One delivery team routinely touches the client's ServiceNow, the client's Azure DevOps, their own Jira, Confluence *and* SharePoint, plus Teams. No single platform's native AI covers it — Rovo can't see the client's ServiceNow queue with the client's ACLs, Copilot can't see the vendor's Jira.
- **Onboarding pain is the business model.** Rotation is constant. A new engineer onboarding onto a client project in week 1 is a recurring, costed event. "Time to first useful contribution" is a metric these firms actually track.
- **Access governance is contractual, not cultural.** Client MSAs dictate who may see what. An auditable access ledger isn't a nice-to-have, it's a deliverable.
- Teams + Jira/ServiceNow + Azure DevOps/GitHub + Confluence/SharePoint is exactly the integration set already named in `docs/PRD.md` §6. That instinct was right.

### 2.4 Connector priority (revised)

| Rank | Connector | Why | Auth mechanism |
|---|---|---|---|
| 1 | **GitHub** | Built. Upgrade PAT → **GitHub App** (per-repo install, short-lived tokens, webhooks, team/collab ACLs) | GitHub App + installation tokens |
| 2 | **Jira + Confluence** | One OAuth, two sources, ships ACLs. Atlassian's official remote MCP server covers Jira, Confluence, JSM, Bitbucket, Compass via OAuth 2.1 | Atlassian OAuth 2.0 3LO, or official MCP server |
| 3 | **Microsoft Teams** (chat + meetings) | The differentiated channel, and the dominant MNC venue | Azure Bot Service + Entra app, delegated Graph scopes |
| 4 | **ServiceNow** | The MNC/GCC wedge nobody else does well. Table API + ACL evaluation | OAuth 2.0, scoped app |
| 5 | **SharePoint / OneDrive** | Where MNC documents actually live | Microsoft Graph, `Sites.Selected` (per-site, not tenant-wide) |
| 6 | **Slack** | Required for the startup segment | Slack OAuth, user + bot tokens |
| 7 | Azure DevOps | Repos + Boards + Pipelines for Microsoft shops | Entra OAuth |
| 8 | Linear, Notion | Startup segment | OAuth |

Rule: **never ship a connector that cannot tell you who is allowed to see each item.** A connector without ACLs poisons the permission model for every other connector.

---

## 3. How a project owner should onboard the agent

This is question 3, and it's the most important section — it's the product.

### 3.1 "Give the agent the same access as a colleague" is three different problems

| Problem | What it means | Wrong answer | Right answer |
|---|---|---|---|
| **Acquisition** | How does the agent physically obtain credentials for N systems? | Owner pastes PATs (what Sensei does today) | Owner-consented OAuth app installs, scoped to named resources |
| **Enforcement** | When Priya asks a question, how do you guarantee she only sees what *Priya* may see? | Index everything, trust the LLM not to leak | ACLs stored on every chunk; filter by the asker's principal set *before* retrieval |
| **Accountability** | Six months later, prove what the agent could see and who approved it | Nothing | Immutable access ledger + audit log + periodic re-attestation |

Most teams solve only acquisition, which is why 80% of agents overstep.

### 3.2 The four access tiers (offer all four; default to tier 2)

**Tier 0 — Owner-pasted secret.** A PAT or API token typed into a form. Acts as the owner; every member inherits the owner's sight line.
*Use for:* hackathon demos, public URLs, file uploads. *Never* for production. This is 100% of what Sensei does today.

**Tier 1 — Org-consented app install (the Glean model).**
Owner/admin installs a Sensei OAuth app (GitHub App, Atlassian 3LO, Entra enterprise app, Slack app, ServiceNow scoped app) and selects *exactly* which repos/spaces/projects/sites/channels are in scope. The agent gets a service identity with a broad-but-scoped read grant, **and separately syncs each item's ACL** so that per-asker trimming is still correct.
*Pros:* one-time setup, works for every member immediately, enables webhooks and background sync. *Cons:* requires an admin, and requires you to get ACL sync right.

**Tier 2 — Per-user delegated OAuth / on-behalf-of (the correct answer to "what a colleague has access to").**
Each member connects their own account once. For **live** lookups ("what's the status of INC0042317?") the agent calls the source API **with that member's own token**, so the source system itself enforces permission — you cannot leak, because the API returns 403. Combine with Tier 1 for the indexed corpus.
The standards landscape converged on this during 2026 and you should build to it rather than invent:
- **Microsoft Entra Agent ID** (GA Apr 2026) — an agent identity is a service principal with no credentials of its own, acquiring short-lived tokens via its blueprint after user or admin consent; supports OAuth 2.0 **On-Behalf-Of** for acting as a signed-in user.
- **Okta Cross App Access (XAA) / Agent SSO** (GA Aug 24, 2026) — registers the agent as a first-class identity in Universal Directory and issues short-lived governed tokens.
- **MCP + OAuth 2.1** — remote MCP servers with embedded scopes; Atlassian's official server already works this way, "so every action respects the user's existing access controls". MCP was donated to the Agentic AI Foundation (Linux Foundation) in Dec 2025; 28% of the Fortune 500 have MCP in production.

**Tier 3 — The agent has its own employee account.**
The agent gets `sensei@customer.com`, an Entra/Okta identity, its own Jira and ServiceNow licence, membership in specific AD/Okta groups. Access is then granted and revoked by the customer's *existing* IAM processes — no special path, no bespoke ACL logic, fully covered by their existing audit.
*This is the most enterprise-legible model and the strongest sales story: "put Sensei in the group, remove it from the group."* Cost: a licence seat per tool. Offer it for regulated buyers.

### 3.3 The onboarding flow — "hiring" rather than "integrating"

This is the UX that should replace the current 4-step wizard. Eight stages, each producing a durable artifact.

```
1. ROLE          Owner writes the agent's job: which project, which squad,
                 who it serves, what it must never answer.
                 → artifact: Role Charter

2. IDENTITY      Agent gets a name, avatar, and an identity:
                 tier 2 (delegated) or tier 3 (own account).
                 → artifact: Agent Identity record

3. ACCESS        Per source: connect → pick exact scope (repos, spaces,
   REQUEST       projects, sites, channels) → pick history window →
                 see a plain-English preview of what that grant exposes,
                 BEFORE granting.
                 → artifact: Access Ledger entry (who granted, what, when,
                   which scopes, expiry)

4. DISCOVERY     Agent indexes, resolves identities, and reports back:
                 "I can see 4 repos, 312 Confluence pages, 1,847 Jira
                 issues, 2 ServiceNow queues, 14 people. I cannot see
                 the #finance channel or the HR space."
                 → artifact: Coverage Report

5. PROBATION     Read-only, answers visible to the owner only. Owner
                 reviews a sample, marks answers correct/wrong/leaked.
                 Retrieval and prompt tuned against real failures.
                 → artifact: Probation Scorecard

6. VERIFICATION  Agent is quizzed on 20 generated project questions with
                 known answers. Owner grades. Below threshold → more
                 sources or narrower scope.
                 → artifact: Readiness Report

7. GO LIVE       Published to channels: web, Teams/Slack, meetings.
                 Each channel enabled separately.
                 → artifact: Channel Roster

8. REVIEW        Quarterly: every grant re-attested or auto-expires.
   & REVOKE      One button kills all access and purges the index.
                 → artifact: Access Review + immutable Audit Log
```

Two design principles that make this more than a wizard:

- **Nothing is granted without a preview.** Before the owner confirms a scope, show what it exposes: item counts, sample titles, the sensitive-looking ones, and who among the team will be able to see them. Consent that isn't informed isn't defensible.
- **Every grant expires.** Default 90 days, re-attestation required. This single feature makes a security review trivially easy to pass and is why an auditor prefers you over a competitor with a permanent PAT in a database.

### 3.4 Permission-aware retrieval: the mechanism

Two standard approaches; use the hybrid.

- **Early binding** — resolve ACLs at index time, store the allowed-principal set in chunk metadata, filter by the asker's principal set at query time. Fast, paginates correctly, but ACLs go stale between syncs.
- **Late binding** — at query time ask each source "may this person see this item?". Always correct, but slow and breaks pagination.

Hybrid (what Glean, Onyx and Copilot connectors all converge on):

```
query
  → resolve asker → principal set {user_id, group ids, team ids, email}
  → ChromaDB/vector query WITH metadata filter: acl_principals ∩ asker_principals ≠ ∅
  → for any top-k hit whose ACL sync is older than T, re-verify live against the source
  → drop anything that fails
  → for live/structured questions, skip the index entirely: call the source API with
    the asker's own delegated token (tier 2) — the source enforces permission for you
  → answer with citations; every citation must be a link the asker can actually open
```

The last line is a cheap and powerful invariant: **if the asker cannot open the citation link, the answer should not have been given.**

### 3.5 Identity resolution — the "what did Ramesh change?" problem

"What did Ramesh change in repo xyz" requires knowing that *Ramesh Kumar* = GitHub `rkumar-dev` = Jira `accountId:5f8a…` = Teams `ramesh.kumar@acme.com` = ServiceNow `sys_user:a1b2…`. Today Sensei has none of this, so the question can only be answered if the string "Ramesh" happens to appear in an indexed commit blob.

Needs a first-class `people` collection: canonical person, display names and aliases, and a list of linked platform accounts with confidence scores. Resolution strategy, in order: exact email match → commit-email match → org directory match (Entra/Okta/Google) → name fuzzy match flagged for owner confirmation. Expose it as a tool, `resolve_person(name) -> Person`, and as a UI screen where the owner merges and confirms matches during onboarding stage 4.

### 3.6 What governance buys you commercially

The artifacts from §3.3 are the enterprise sales asset: Role Charter, Access Ledger, Coverage Report, Probation Scorecard, Readiness Report, Access Review, Audit Log. They map directly onto what a SOC 2 / ISO 42001 / EU AI Act reviewer asks for. No competitor in category A or C ships them. They are also the thing an Atlassian or Microsoft bundle will be slowest to copy, because their model is "the platform already has the permissions" — true inside one vendor, false across four.

---

## 4. Gaps in the current build

Verified against the code on branch `feat/agent-onboarding` at `cb3b6a9`.

### Blocking — breaks the demo path

| # | Issue | Status |
|---|---|---|
| 1 | **Invited members could not use the product at all.** `POST /workspaces/{id}/invite` minted a link to `/join?token=…`, but no `/join` route existed in the backend and no `/join` page in the frontend. There was no `members` collection. | ✅ **Fixed** — `backend/db/membership.py`, `POST /workspaces/join`, `frontend/src/pages/Join.tsx`, `?next=` carried through login/register |
| 2 | **Chat and sources were owner-only.** Both resolved the workspace by `{"owner_id": user["id"]}`, so even a joined member got 404. | ✅ **Fixed** — every route now resolves through `require_workspace` / `require_owner`; members read, owners write |
| 3 | **README documented the wrong env var** (`MONGODB_URI` vs the code's `MONGO_DB`) — a judge following it got a 503. | ✅ **Fixed** |
| 4 | **The backend did not start at all.** `backend/.env` carried `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — documented in `.env.example` but not declared on `Settings`, and pydantic-settings forbids extras. Hard crash on import. | ✅ **Fixed** — both declared, plus `extra = "ignore"` so no stray env var can ever block boot |
| 5 | **`npm run build` failed.** `tsc -b` errored on an unused `sourceIds` state in `Onboarding.tsx`, which would have blocked any deploy of the live demo URL. | ✅ **Fixed** |
| 6 | Repo is private (`project-sensei-ai/sensei.ai`); rules require a **public** repo with a detectable MIT licence. | ⬜ Yours to flip |
| 7 | AWS keys in `backend/.env` were surfaced in a local stack trace. `.env` is gitignored and was never committed (history is clean), but rotate them before the repo goes public. | ⬜ Recommended |

### Architectural — matters for the business, not for Friday

| # | Issue | Note |
|---|---|---|
| 5 | **Secrets stored in plaintext.** `config_secret` holds PATs and API tokens as cleartext in MongoDB. `ARCHTECTRUE.md` claims "encrypted at rest in DB" — it isn't; `core/security.py` has no encryption helper. | Needs envelope encryption (KMS data key) or a secrets manager. |
| 6 | **No permission model.** PRD FR-7 ("prevent users from receiving content they cannot access") is 0% implemented. Chunks carry no ACL metadata; retrieval has no filter. | §3.4 |
| 7 | **Snapshot-only ingestion.** Everything is a point-in-time embed. "What's the status of INC0042317?" will be answered from a stale blob, confidently and wrongly — the exact failure PRD §8 forbids. Needs live read-through tools. | §5 H1 |
| 8 | **No identity graph.** "What did Ramesh change?" cannot work. | §3.5 |
| 9 | **Retrieval is a flat top-5 cosine search** over 2000-char chunks with no metadata filter, no reranking, no query routing. A "who owns X" question and a "show me the code for Y" question hit the same path. | §5 H1 |
| 10 | Chat sessions keyed on `owner_id`; not shareable, so no team memory. | `chat/routes.py` |
| 11 | Local ChromaDB `PersistentClient` on the container filesystem — lost on redeploy, not shared between replicas. | Needs hosted vector store. |
| 12 | No source deletion from the vector store on workspace delete; no tenant isolation beyond collection naming. | |
| 13 | ~~Zero tests~~ — no test suite at all. | |

---

## 5. What I will implement

### Horizon 0 — the next 48 hours (hackathon submission)

Goal: a submission that cannot break on camera. **No new features. No new connectors. No re-architecture.** Seven items, roughly in order.

| # | Task | Est. | Why |
|---|---|---|---|
| H0-1 | Make the repo public; confirm MIT shows in the GitHub About panel | 5 min | Pass/fail rule |
| H0-2 | ✅ Fix the README env var (`MONGO_DB`) — **also fixed the boot crash and the broken build**. Still to do: a clean-machine `git clone` → run test | 45 min | Rule 3: judges must be able to run it |
| H0-3 | ✅ **`/join` implemented and verified end to end** — `members` collection, `POST /workspaces/join`, all workspace lookups switched to membership, `/join` landing page, `?next=` through auth, role-gated Sources UI. Tested: owner creates → invites → teammate registers → joins → asks a question through the Strands agent. Boundaries verified: member gets 403 on writes, 200 on reads, cannot see the owner's sessions; bad token 404, expired 410, cross-workspace 409, re-click idempotent. | 2 h | Rules: "no dead buttons", "functions as depicted" |
| H0-4 | Seed a demo workspace + demo login credentials for judges; document in testing instructions | 45 min | Rule 4 |
| H0-5 | Architecture diagram as an actual image (export the ASCII from `ARCHTECTRUE.md` to PNG/SVG) | 45 min | Required artifact |
| H0-6 | Deploy a live URL (App Runner or Fly.io; AgentCore only if it works first try — do not burn hours on it). Must stay up through Oct 8. | 2–3 h | Scores Technical Implementation |
| H0-7 | Record the ≤5-min video: 30s problem → 45s architecture → 3min live demo → 30s impact. Script it, rehearse once, captions on. | 3 h | 20% of the score |
| H0-8 | If and only if time remains: 1–2 builder.aws.com posts with "Agents for Humans" in the title (+0.2 each, max +0.6) | 1 h each | Bonus |

Demo narrative to record — the one Sensei can actually deliver today, and it is a good one:

> An owner creates a workspace, connects a GitHub repo and a Confluence space, watches the agent index 19 kinds of repo data, invites a teammate, and the teammate asks "who has access to this repo, and who actually wrote the code?" — and gets the **contributors-vs-collaborators distinction** right, with citations. That distinction is a genuinely non-obvious insight and it is already built. Lead the Creativity pitch with it.

Do **not** demo: meetings, Teams, Jira, ServiceNow, permission trimming, continuous sync. They don't exist. Say they're next, on a roadmap slide.

### Horizon 1 — weeks 1–4 after the deadline (the real v1)

This is where the architecture in §3 gets built. Order is deliberate: security and correctness before breadth.

**Week 1 — multi-tenancy and secrets, properly**
- `members` collection with roles (owner/admin/member/viewer); workspace resolution by membership everywhere; workspaces become many-per-user.
- Envelope encryption for all source credentials (KMS data key + per-workspace DEK), replacing plaintext `config_secret`.
- Replace local ChromaDB with a hosted vector store (Qdrant Cloud or pgvector on Postgres) so state survives deploys. Keep a `VectorStore` interface so swapping back is cheap.
- Add the first tests: auth, membership, ACL filter. Target the retrieval path specifically.

**Week 2 — the permission model and the identity graph**
- `acl_principals: list[str]` on every chunk; `principal_set(user)` resolver; metadata filter on every query; late-binding re-verification for hits whose ACL sync is stale. Drop anything unresolvable.
- `people` collection + `resolve_person` tool + owner-facing identity-merge screen (§3.5).
- Invariant test: a member who cannot open a citation link never receives that citation.

**Week 3 — live read-through and query routing**
- Split the single `search_project_docs` tool into a small typed toolset the agent routes between:
  `search_docs(query, filters)` · `get_issue(key)` · `list_issues(jql_or_filter)` · `get_incident(number)` · `person_activity(person, repo, since)` · `repo_changes(repo, since)` · `who_owns(thing)` · `resolve_person(name)`.
  Live tools call the source API with the **asker's** delegated token (tier 2). This is what makes "status of INC0042317" and "what did Ramesh change" correct rather than plausible.
- GitHub PAT → **GitHub App**: per-repo install, short-lived tokens, webhooks for incremental sync, collaborator/team ACLs.
- Atlassian OAuth 3LO (or the official Atlassian MCP server) for Jira + Confluence in one grant, with ACLs.

**Week 4 — the onboarding product (the differentiator)**
- Rebuild the wizard as the 8-stage hiring flow (§3.3).
- `access_ledger` collection (append-only), `audit_log` collection (append-only), Coverage Report, Readiness quiz, Revoke-all.
- Scope-preview-before-grant for every connector.

### Horizon 2 — months 2–6 (business-grade)

- **Meetings.** Recall.ai for join/transcript/audio-out across Teams, Zoom, Meet. Wake-word + @mention addressing. Grounded live answers with spoken citation ("per INC0042317, updated Tuesday"). Explicit refusal when unverified. Proactive correction **off by default** — it is the highest-risk feature in the PRD and earns its way on with a confidence threshold and per-workspace opt-in.
- **Channels.** Teams bot (Azure Bot Service + Entra app) → Slack (Bolt).
- **Continuous sync.** Webhooks where available (GitHub, Jira, ServiceNow business rules), polling with cursors elsewhere, freshness SLA surfaced in the UI so an answer can say "Jira last synced 4 minutes ago".
- **ServiceNow + SharePoint** connectors — the GCC wedge.
- **Tier 3 identity** (agent gets its own employee account) for regulated buyers.
- **Compliance package:** SOC 2 Type I → II, data residency options, ISO 42001 / EU AI Act Article 12 record-keeping mapped onto the existing audit log (you already have skills for this in the toolchain).
- **Evaluation harness** — a golden question set per workspace, regression-run on every retrieval or prompt change. Without this, quality silently rots and you will not notice until a customer does.

---

## 6. Data model changes (Horizon 1)

```
members              NEW   workspace_id, user_id, role, joined_at, invited_by
                           unique (workspace_id, user_id)

people               NEW   workspace_id, display_name, aliases[], emails[],
                           accounts[{platform, platform_id, handle, confidence,
                                     confirmed_by, confirmed_at}]

access_grants        NEW   workspace_id, source_id, tier (0|1|2|3), granted_by,
                           granted_at, expires_at, scopes[], resources[],
                           preview_snapshot, revoked_at, revoked_by
                           — append-only; revocation is a new row, never an update

audit_log            NEW   workspace_id, actor (user|agent), action, target,
                           asker_principals[], citations_returned[], at
                           — append-only

sources           CHANGE   config_secret → credential_ref (KMS-encrypted blob or
                           secrets-manager ARN); + acl_sync_at, sync_cursor,
                           freshness_sla

workspaces        CHANGE   drop unique index on owner_id (many workspaces per user)

chat_sessions     CHANGE   owner_id → created_by; + visibility (private|workspace)

chunk metadata    CHANGE   + acl_principals[], acl_synced_at, entity_ids[],
                           updated_at, source_url (must be asker-openable)
```

---

## 7. Business model sketch

Reference points: Glean ~$40–50/user/mo with ~100-seat minimum and a $60k annual floor, $300M ARR at $7.2B (May 2026); Onyx ~$20/user/mo; Dust ~€29/user/mo; enterprise search ~$6.7B in 2025 → ~$14.5B by 2034. Agent tiers are pricing at a 30–50% uplift over search tiers, following Microsoft's Copilot-at-$30-on-top pattern.

The per-seat model is the wrong shape for Sensei, because Sensei's value is per *project*, and most of a project's members are occasional askers.

Proposed: **per project workspace, not per seat.**

| Tier | Price | Includes |
|---|---|---|
| Free | $0 | 1 workspace, 3 sources, web chat, 50 questions/mo — the self-serve wedge |
| Team | ~$299/project/mo | Unlimited members, 10 sources, Slack or Teams chat, continuous sync, access ledger |
| Business | ~$899/project/mo | Meeting participation, all connectors, per-user delegated OAuth, SSO, full governance pack, readiness reports |
| Enterprise | custom | Tier-3 agent identity, data residency, self-host, SOC 2 report, contractual audit support |

Why it works: a delivery manager can buy a $299 project workspace on a card without a procurement cycle, and the price anchors against the cost of one engineer's onboarding week — which in an IT-services context is a number the buyer already knows.

Beachhead: **IT-services and GCC delivery teams in India** (§2.3) — multi-vendor by necessity, onboarding-cost-obsessed, governance-mandated, and reachable without a US enterprise sales team. Expand from there into multi-vendor Western mid-market.

---

## 8. Decisions

Settled 2026-09-12:

1. **Horizon 0 scope — implement `/join`.** ✅ Done. Membership, roles, the join route and the invite landing page all ship. See §4.
2. **Beachhead segment — IT-services / GCC delivery teams** (§2.3). Connector order for weeks 3–4 follows from this: GitHub App → Jira + Confluence → Teams → ServiceNow → SharePoint. Slack and Linear slip behind ServiceNow.
3. **Access tiers — tier 1 for the indexed corpus, tier 2 for live lookups, built in parallel.** Org-consented scoped installs with ACL sync carry the index; per-user delegated OAuth carries live ticket and PR reads so the source system enforces permission itself.

Still open:

4. **Meetings: build or buy** — Recall.ai (recommended; $ per meeting-hour but removes an entire platform-engineering problem) vs native Teams/Zoom SDKs per platform.
5. **Proactive meeting corrections** — PRD FR-6 wants the agent to correct people unprompted. Recommendation: build it but ship it off by default. Getting this wrong in front of a customer's leadership is an unrecoverable trust event.

---

## Sources

Competitive landscape: [Dust — Glean alternatives](https://dust.tt/blog/glean-alternatives-ai-enterprise-search) · [Onyx — Glean alternatives](https://onyx.app/insights/glean-alternatives) · [Onyx — enterprise RAG platforms 2026](https://onyx.app/insights/enterprise-rag-platforms-2026) · [Glean valuation & ARR 2026](https://valueaddvc.com/blog/glean-valuation-revenue-2026-300m-arr-enterprise-ai-search) · [Glean pricing](https://www.exploreagentic.ai/comparisons/glean-pricing-alternatives/) · [Dashworks acquired by HubSpot / VentureBeat seed](https://venturebeat.com/ai/dashworks-launches-ai-assistant-to-streamline-internal-knowledge-for-enterprises-raises-5m)

Platform incumbents: [Jira AI agents as team members (Feb 2026)](https://byteiota.com/jira-ai-agents-as-team-members-atlassians-feb-2026-launch/) · [Atlassian — Teamwork Graph connector for GitHub](https://www.atlassian.com/blog/ai-at-work/rovo-github-software-teams) · [Rovo complete guide & credit pricing 2026](https://www.tryprotege.com/blog/atlassian-rovo-complete-guide) · [Microsoft 365 Copilot connectors (ACL sync)](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/overview) · [Graph connectors guide 2026](https://imrizwan.com/blog/microsoft-graph-connectors-copilot-search-guide-2026) · [Slack Agentforce AI employees](https://slack.com/blog/news/ai-for-employees-agentforce-slack)

Meetings: [Otter Meeting Agent](https://otter.ai/blog/otter-meeting-agent-your-new-collaborative-teammate) · [Otter live voice agent / Fast Company](https://www.fastcompany.com/91304763/otters-new-ai-agents-are-built-to-boost-sales-and-streamline-meetings) · [Recall.ai Meeting Bot API](https://www.recall.ai/product/meeting-bot-api) · [recallai/meeting-bot](https://github.com/recallai/meeting-bot)

Permissions & agent identity: [Truto — document-level RBAC for RAG pipelines](https://truto.one/blog/how-to-maintain-document-level-rbac-in-enterprise-rag-pipelines/) · [Sinequa — data access & security in enterprise search](https://www.sinequa.com/resources/blog/data-access-security-management-the-enterprise-search-challenge/) · [Early binding explained](https://www.luigisbox.com/search-glossary/early-binding/) · [Entra Agent ID — on-behalf-of flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow) · [Okta Agent SSO / Cross App Access GA](https://www.okta.com/newsroom/press-releases/okta-brings-first-class-identity-to-ai-agents-with-agent-sso/) · [AI agent identity standards 2026](https://startwithidentity.com/blog/agent-identity-gets-a-protocol/) · [MCP server permissions audit (80% overreach stat)](https://nhimg.org/community/agentic-ai-and-nhis/mcp-server-permissions-audit-is-your-agent-access-actually-scoped) · [Atlassian official MCP server](https://github.com/atlassian/atlassian-mcp-server) · [CData — 2026 enterprise-ready MCP adoption](https://www.cdata.com/blog/2026-year-enterprise-ready-mcp-adoption) · [Glean MCP security & data flow](https://docs.glean.com/administration/platform/mcp/security)

Tool landscape: [Linear vs Jira 2026](https://tech-insider.org/linear-vs-jira-2026/) · [ServiceNow ITSM share / JSM comparison](https://lovable.dev/guides/jira-vs-servicenow-itsm-comparison) · [Startup tech stacks 2026](https://webreveal.io/blog/common-tech-stacks-startups-2026.html) · [Intercom — early-stage startup stack](https://www.intercom.com/blog/early-stage-startup-tech-stack/) · [2026 tech stack guide: startups vs enterprises](https://nanobytetechnologies.com/Blog/The-2026-Tech-Stack-Guide-How-Startups-and-Enterprises-Can-Choose-Scalable-Secure-Future-Ready-Tools)
