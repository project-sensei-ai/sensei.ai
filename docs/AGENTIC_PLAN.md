# Making Sensei an agent, not a chat box

Written for: the Sensei team, as the design for the next build phase.

---

## Why it currently reads as chat

Not because the code is bad — the Strands agent loop is real, it picks tools and
synthesises cited answers. It reads as chat because of the *shape of the system
around it*:

| | Today | What an agent does |
|---|---|---|
| **What starts work** | A human types | An event in the world |
| **What it can do** | One verb: search | Several verbs, chained toward a goal |
| **What it produces** | Prose that scrolls away | An artifact that persists and gets used |
| **When it involves a human** | Every single time | Only at a decision |
| **What it learns** | Nothing | Each gap closed makes it permanently better |

Every row is fixable without rewriting the agent. The agent is fine. It has no
job.

---

## Four capabilities

Each one fixes one row above. They compose into a single story, and each is
independently shippable.

### 1. The Onboarding Brief — work that starts without being asked

**Trigger:** the owner adds someone to the project.

Nobody prompts anything. The agent researches the project *for that specific
person* and writes them a brief: what this project is, who owns what, the four
documents they should read first, which services they'll touch, who to ask about
what, and what's in flight right now. Every claim cited. It is waiting for them
when they first log in.

Why this one first: it is the product thesis made literal. "New joiners lose
weeks to scattered context" stops being a slide and becomes a thing that
happened while nobody was watching. It also gives the allowlist work a payoff —
adding a person *does something*.

**Strands shape.** A `Graph`: a Researcher node that runs several searches and
returns findings, feeding a Writer node with `structured_output_model` so the
brief is a typed object — sections, reading list, people, open questions — not a
blob of prose. Typed output is what makes it renderable as a page rather than a
chat bubble.

**Effort:** 3–4h.

---

### 2. The Change Watch — autonomy with a silence condition

A background loop re-reads connected sources on a schedule, diffs against the
last snapshot, and **decides whether anything material changed**. A README typo:
silence. An architecture doc rewritten, a new service added, an owner changed:
it writes a short digest and marks affected briefs stale.

The decision is the point. Anything can post an update on a timer; the rule is
*"surfaces only when there's a real decision to make."* So the agent returns
`{materially_changed: bool, why, who_should_know}` and most runs end in nothing.

Demo value: say "this ran overnight, nobody asked it to, and it noticed the
deployment doc Priya was told to read is now out of date." That single sentence
is the difference between a chatbot and a teammate.

**Effort:** 4–5h, most of it snapshotting and the scheduler.

---

### 3. The Gap Hunter — finding work instead of waiting for it

The agent audits *its own knowledge* and reports what is missing:

> - No document describes how this is deployed.
> - `payments-service` and `notify-worker` have no named owner anywhere.
> - The PRD references a "decision log" that is not in any connected source.
> - 3 of 7 repos have no README.

Then it offers to close the gap: *"I can draft the deployment doc from the CI
config and the Dockerfile — want me to?"* Owner says yes, it drafts, owner edits
and publishes.

This is the most non-obvious of the four, and the one judges are least likely to
have seen. Every knowledge product tells you what it knows. This one tells you
what nobody wrote down — which is the actual problem in every project that ever
onboarded anyone.

**Effort:** 3–4h.

---

### 4. The Answer Ledger — getting better through use

Every question the agent could not answer is recorded, not discarded. The owner
sees a list: *"5 things your team asked that I couldn't answer."* They answer one
in a sentence; it is indexed and attributed; the agent can answer it forever.

This turns "continuous learning" from a claim into a mechanic you can point at.
It also produces the metric that sells the product: **answered-without-a-human,
week over week.**

**Effort:** 2–3h.

---

## The demo this makes possible

The current demo is: *ask a question, get a cited answer.* That is a good RAG
demo and a forgettable agent demo. This is the replacement:

1. Owner connects GitHub and Confluence, adds Priya to the project.
2. **Nobody asks for anything.** The agent researches and writes Priya's brief.
3. Priya logs in for the first time. The work is already done — her brief, her
   reading list, the two people she should meet, all cited. She asks one
   follow-up and gets a cited answer.
4. *"Overnight, a commit landed."* The agent noticed, judged it material, wrote a
   two-line digest and flagged that Priya's reading list is now stale.
5. The agent reports something nobody asked about: no deployment doc exists.
   It offers to draft one from the CI config. The owner accepts. It drafts.

Five beats, and in four of them the agent acts on its own. The human appears
twice: once to grant access, once to make a decision.

---

## Sequencing

| | Capability | Effort | Buy |
|---|---|---|---|
| 1 | Onboarding Brief | 3–4h | Event-triggered work, a real artifact, the product thesis |
| 2 | Gap Hunter | 3–4h | The genuinely novel one; a decision put to a human |
| 3 | Change Watch | 4–5h | Background autonomy with a silence condition |
| 4 | Answer Ledger | 2–3h | Compounding memory; the metric |

If only one gets built: **the Onboarding Brief.** It is the only one that changes
what the product *is* rather than what it *does*.

If two: add the **Gap Hunter**, because it is the one nobody else will have.

---

## Two things to fix alongside

Cheap, and they cost credibility every day they stand.

- **`docs/ARCHTECTRUE.md` describes a `MemoryManager` and streaming.** Neither
  exists in the code. Either build them or cut the sections — a reader who greps
  for `MemoryManager`, finds nothing, and then stops believing the rest of the
  document is a worse outcome than never having claimed it.
- **Four `@tool` functions never reach the agent.** `fetch_github`,
  `fetch_urls`, `parse_file` and `fetch_confluence` are decorated but called
  directly by the ingestion runner. Either make them genuinely agent-callable —
  so the agent can decide to go refresh a source mid-answer, which is itself
  agentic — or drop the decorator and stop implying a tool surface that is not
  wired up.

The first option on that second point is the better one, and it is nearly free:
an agent that can say *"that source looks stale, let me re-read it"* and then do
so is doing something no chat box does.
