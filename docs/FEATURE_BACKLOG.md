# Feature backlog — what would make this outstanding

Written for: the Sensei team, as the master list to pick from.

Effort is build time for one person who knows the codebase. "Criterion" maps to
the five equally-weighted judging criteria in `docs/HACKATHON.md` §5.

---

## Tier 1 — Makes it an agent instead of a chat box

Without these the product is a retrieval chatbot, however good the retrieval is.

| # | Feature | What it does | Why it lifts the submission | Criterion | Effort |
|---|---|---|---|---|---|
| 1.1 | **Onboarding Brief** | Owner adds a person → agent researches the project *for that person* and writes a cited brief: what this is, who owns what, first four docs, services they'll touch, who to ask. Waiting when they log in. | The only feature that changes what the product **is**. Work that starts from an event, not a prompt, and leaves an artifact. Makes the allowlist mean something. | Impact, Creativity | 3–4h |
| 1.2 | **Gap Hunter** | Agent audits its own knowledge and reports what's *missing* — no deployment doc, two services with no owner, a referenced decision log that isn't indexed — then offers to draft it. | Every knowledge tool says what it knows. This one says what nobody wrote down. Judges will not have seen it. Also puts a real decision to a human. | Creativity, Impact | 3–4h |
| 1.3 | **Change Watch** | Background loop diffs sources on a schedule and **decides** whether anything material changed. Typo → silence. Architecture rewritten → digest + mark affected briefs stale. | Literally implements "runs autonomously in the background and surfaces only when there's a real decision to make." The silence condition is the hard part and the whole point. | Technical, Creativity | 4–5h |
| 1.4 | **Answer Ledger** | Unanswered questions are recorded. Owner sees "5 things your team asked that I couldn't answer", answers one in a sentence, it's indexed and attributed. | Turns "continuous learning" from a claim into a mechanic. Produces the metric that sells the product. | Impact, Creativity | 2–3h |
| 1.5 | **Self-refreshing sources** | Make `fetch_github` / `fetch_confluence` / `fetch_urls` genuinely agent-callable so the agent can decide mid-answer that a source looks stale and go re-read it. | Four `@tool` functions are decorated today but called directly by the ingestion runner — the agent never sees them. Wiring them up is nearly free and is itself agentic. | Technical | 1–2h |
| 1.6 | **Freshness in every answer** | Each answer states how current its evidence is: "per PROJ-412, synced 4 minutes ago". Stale sources are flagged rather than quietly used. | The credibility difference between "the status is X" and "the status was X yesterday". Prerequisite for anyone trusting a status answer. | Impact | 2h |

---

## Tier 2 — Makes it trustworthy, which is the differentiator

Nobody else in this category productises access. This is the moat.

| # | Feature | What it does | Why it lifts the submission | Criterion | Effort |
|---|---|---|---|---|---|
| 2.1 | **Trust & Access page** | One screen: every connected source, its exact scope, who granted it, when, and a one-click revoke. | The "show, don't assert" answer to *is this safe?* Most of the data already exists. Demos in 30 seconds. | Design, Creativity | 4–5h |
| 2.2 | **Coverage report** | "I can see 4 repos, 312 pages, 14 people. I **cannot** see your private channels, your email, or anything outside these spaces." | The negative half is what earns trust. Also doubles as the agent's own self-knowledge for the Gap Hunter. | Creativity, Design | 2h |
| 2.3 | **Scope preview before granting** | Before the owner confirms a connector, show what it would expose — item counts, sample titles, who on the team would see them. | Consent that isn't informed isn't consent. Turns a settings page into a decision. | Design | 2–3h |
| 2.4 | **Access ledger + audit log** | Append-only record of every grant and revocation, and of which sources answered which question for whom. | The artifact an auditor asks for. Maps onto SOC 2 / ISO 42001 evidence requirements. | Creativity | 3h |
| 2.5 | **Expiring grants** | Every access grant defaults to 90 days and must be re-attested or it lapses. | One feature that makes a security review trivial to pass, and that no competitor with a permanent PAT in a database can claim. | Creativity | 1–2h |
| 2.6 | **Encrypt stored credentials** | Envelope-encrypt `config_secret` with a KMS data key instead of plaintext MongoDB. | Currently PATs and API tokens sit in the clear. The docs used to claim otherwise. Nothing else in Tier 2 is honest until this is true. | Technical | 2–3h |
| 2.7 | **Per-asker permission filtering** | ACL principals on every chunk; retrieval filtered by who is asking, so two members get different answers from the same index. | PRD FR-7, currently 0% implemented. The invariant: if the asker can't open the citation, they shouldn't have got the answer. | Technical | 5–6h |

---

## Tier 3 — Makes the Strands usage deep

Criterion 1 is 20% **and** the tie-breaker. Today: one `Agent`, two tools.

| # | Feature | What it does | Why it lifts the submission | Criterion | Effort |
|---|---|---|---|---|---|
| 3.1 | **Multi-agent Graph** | `Researcher → Writer` graph for the Brief and the Gap Hunter, using `strands.multiagent.GraphBuilder`. | Moves from "called an LLM in a loop" to orchestration. Ships as part of 1.1, so the marginal cost is small. | Technical | 2h |
| 3.2 | **Typed artifacts** | `structured_output_model` so a Brief is a typed object — sections, reading list, people, open questions — not prose. | Typed output is what lets an artifact render as a page and be diffed when things change. | Technical, Design | 1h |
| 3.3 | **Streaming answers** | `agent.stream_async()` through to the UI instead of a spinner for up to 45 seconds. | The single biggest perceived-quality change in the product. Also: `ARCHTECTRUE.md` already claims this exists. | Design, Technical | 2h |
| 3.4 | **Show your work** | Surface the agent's tool calls live — "searching docs… reading Confluence… checking commits" — via Strands hooks. | Makes the agent loop visible instead of hidden behind a spinner. Judges reading for genuine Strands use can *see* it working. | Technical, Design | 3h |
| 3.5 | **Bedrock AgentCore deployment** | Run the agent on AgentCore rather than a container. | Explicitly named in the rules as strengthening Technical Implementation. | Technical | 3–4h |
| 3.6 | **Session memory, proven** | Make `S3SessionManager` actually exercised so follow-up questions use prior turns. | Wired but unproven. "What about the second one?" working is a visible capability. | Technical | 1–2h |

---

## Tier 4 — Makes the impact provable

Judges are told to look for demonstrated impact, not claimed impact.

| # | Feature | What it does | Why it lifts the submission | Criterion | Effort |
|---|---|---|---|---|---|
| 4.1 | **Impact metrics** | Time-to-first-useful-answer, questions answered without a human, coverage %, week over week. | Turns "saves onboarding time" into a number on screen. | Impact | 3h |
| 4.2 | **Person graph** | Resolve *Ramesh* → GitHub login → Confluence account → email, so "what did Ramesh change in repo X" works. | An entire class of question is unanswerable without it. Currently only works if the name happens to appear in indexed text. | Technical, Impact | 4–5h |
| 4.3 | **Eval harness** | A golden question set per workspace, re-run on every retrieval or prompt change. | Without it quality rots silently — as it did with the 2000-char chunks. Also a credible engineering signal in the repo. | Technical | 3h |
| 4.4 | **First-week plan with progress** | The Brief becomes a tracked checklist: docs read, people met, first PR. | Extends an artifact into a workflow. An agent doing a manager's job end to end. | Impact, Design | 3h |

---

## Tier 5 — Polish that shows up on camera

| # | Feature | What it does | Criterion | Effort |
|---|---|---|---|---|
| 5.1 | **Activity timeline** | One feed of what the agent did and when — briefs written, changes noticed, gaps found. Makes autonomy visible. | Design | 2–3h |
| 5.2 | **Empty / loading / error states** | Every screen has a considered zero-state instead of a blank panel. | Design | 2h |
| 5.3 | **Citation links that open** | Every citation is a working link to the source page, not just a label. | Design, Impact | 1–2h |
| 5.4 | **Dark mode + mobile pass** | The six screens that appear in the demo, at phone width and in both themes. | Design | 2–3h |
| 5.5 | **Cut the false doc claims** | `ARCHTECTRUE.md` describes a `MemoryManager` and streaming that do not exist. Build or delete. | Technical | 15m |

---

## Totals

| Tier | Hours |
|---|---|
| 1 — agent | 15–21 |
| 2 — trust | 19–24 |
| 3 — Strands depth | 12–16 |
| 4 — provable impact | 13–15 |
| 5 — polish | 8–11 |
| **All of it** | **67–87** |

---

## If you are choosing

**The eight that carry the most weight**, ~22–28h:

1.1 Onboarding Brief · 1.2 Gap Hunter · 1.5 Self-refreshing sources ·
2.1 Trust & Access page · 2.2 Coverage report · 3.2 Typed artifacts ·
3.3 Streaming · 5.5 Cut the false claims

That set gives you: an agent that works unprompted, a differentiator nobody else
has, visible Strands orchestration, and a product that feels alive rather than
laggy — while staying honest about what it does.

**The single highest-value item is 1.1.** It is the only one that changes what
the product is rather than what it does.

**The cheapest real win is 5.5**, at fifteen minutes.

**The one most likely to be underestimated is 2.7** (per-asker filtering). It is
the right thing, it is what the PRD promises, and it will take longer than the
estimate.
