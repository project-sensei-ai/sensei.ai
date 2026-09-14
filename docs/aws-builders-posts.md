# AWS Builders — student-builders posts

Four variants of the same story (build journey + AWS usage, "Agents for Humans" in
every title). Pick one; they differ in length and angle. All grounded in the
project as actually built — README, config, and the code in this repo.

Common facts used across posts:

- Project: **Sensei** — a project teammate that does the work nobody asked it to do.
- Ingests GitHub, Confluence, Jira, Slack, files/URLs; embeds chunks into ChromaDB.
- Strands Agents SDK agent loop with citations, per-question search budget.
- Autonomy: onboarding briefs, gap hunter, answer ledger, change watcher that stays quiet.
- AWS: Amazon Bedrock AgentCore (Claude 3.5 Sonnet), S3 for chat session state,
  Bedrock Knowledge Bases sync on upload; one flag switches Groq / Ollama / Bedrock.
- Stack: FastAPI + MongoDB Atlas, single container on Fly.io, MIT licensed.

---

## Post 1 — The long build story (full journal)

### Agents for Humans: Building a Teammate That Starts Before You Ask

I spent this hackathon asking myself one uncomfortable question: why do we still
treat AI tools like search bars? You type, it answers, you type again. But the
paperwork of a software project — the onboarding doc nobody wrote, the question
everyone asks twice, the runbook that quietly rotted — was never a search
problem. It's a *not-done* problem. So instead of building another chatbot, we
built Sensei: an agent layer that starts working the moment a human joins, and
that stays silent when silence is the better answer.

#### The build journey

The core is an ingestion + retrieval pipeline. The agent pulls a team's real
sources — GitHub, Confluence, Jira, Slack, uploaded files — chunks them, embeds
them into a per-workspace ChromaDB collection, and then a Strands-agent loop
answers questions over them with inline citations. That's the boring half. The
interesting half is the autonomy:

- **Onboarding briefs that write themselves.** Adding a teammate triggers a
  multi-agent graph that researches the project *for that person* and leaves a
  cited brief waiting when they first log in — who owns what, what to read
  first, what the sources can't tell them.
- **A gap hunter.** When a source finishes indexing, the agent audits its own
  knowledge for what's *absent* — documents that should exist, components with
  no owner, dead references — and offers to draft the missing one, flagging
  every line it inferred rather than found.
- **An answer ledger.** Questions it can't ground aren't discarded. They're
  recorded. An owner answers once, it's indexed, and the whole team gets a
  permanent answer from then on.
- **A watcher that decides when silence is the product.** It re-reads sources,
  hashes and diffs them with no model involved, and only escalates when
  something *material* moved. A typo: silence. A deleted runbook: a digest, and
  every stale brief is flagged.

#### The bugs that taught us the most

The worst failure mode wasn't a crash — it was content that indexed but could
never be *found*. Our default embedder truncates at 256 tokens, so the original
2 000-character chunks were half-invisible to search. Re-chunking at 800
characters turned previously-unanswerable questions into correct, cited answers.

We also learned to budget our own agent. Unbounded, it called the search tool up
to eight times on a single question, re-reading passages it had already seen and
tripping provider rate limits. A budget of three searches and cross-call
citation dedup fixed it — a wall-clock lesson in context-window economics.

#### Where AWS came in

The backend switches model providers with a single flag, and the production path
runs on AWS:

- **Amazon Bedrock AgentCore** drives the interactive agent with
  `anthropic.claude-3-5-sonnet` — one env var flips the whole app between Groq,
  Ollama, and Bedrock.
- **Amazon S3** holds chat session state, so conversations survive restarts.
- **Amazon Bedrock Knowledge Bases** — uploaded files sync into a managed KB the
  moment they land, giving the retrieval layer a cloud-grade second home next to
  the local vector store.

Everything else is deliberately boring: FastAPI, MongoDB Atlas, credentials
encrypted at rest, one container on Fly.io.

#### Advice for next year's me

1. Check your embedder's context limit on day one — invisible data is worse than
   missing data.
2. Teach the agent when *not* to speak. An assistant that never says no is an
   assistant people learn to ignore.
3. Make "production-grade" a config flag, not a rewrite. Bedrock, S3, and managed
   KBs took us from demo to deployable in one sprint.

Sensei is MIT-licensed. Joining a project is supposed to be the fun part, not
week one of archaeology — this is the teammate that does the paperwork so humans
don't have to.

---

## Post 2 — Concise (medium length)

### Agents for Humans: The Hackathon Teammate That Works Without Being Asked

Every AI tool asks you to type first. But most project pain isn't a question
waiting to happen — it's work nobody started. So we built **Sensei**, an agent
that does the job before anyone prompts it.

It ingests a team's real sources (GitHub, Confluence, Jira, Slack, files),
embeds them into a vector store, and answers with citations. On top of that, it
runs on its own:

- Writes a cited **onboarding brief** for every new teammate automatically.
- Audits sources after indexing for what's missing — and drafts the docs itself,
  marking every inferred line.
- Records questions it can't answer so one human reply becomes permanent
  knowledge.
- Watches sources for change and stays quiet about what doesn't matter.

The journey's honest takeaways: our embedder trims at 256 tokens, so 2 000-char
chunks were half-invisible to search until we re-chunked at 800. And our own
agent had to be budgeted — three searches per question, deduplicated citations —
before it stopped drowning its own context window.

**AWS did the heavy lifting.** Bedrock AgentCore runs the chat agent (Claude 3.5
Sonnet), S3 persists sessions, and Bedrock Knowledge Bases syncs uploads
serverless-style the second they land. One flag flips the whole stack between
Groq, Ollama, and Bedrock.

If you've ever joined a project and spent the first week doing archaeology —
this is the fix.

---

## Post 3 — Technical / lessons focused

### Agents for Humans: What Building an Autonomous Agent Actually Teaches You

People assume the hard part of an agent is the model. It isn't. The hard parts
are retrieval, budgets, and restraint. Building **Sensei** — an agent teammate
for software teams that ingests GitHub, Jira, Slack, Confluence and files into a
vector store — I hit all three in one hackathon.

**Retrieval.** Our default embedder truncates at 256 tokens. Chunks of 2 000
characters looked indexed but were half-invisible to search: content existed,
citations were impossible. Re-chunking at 800 characters made previously-dead
questions answer correctly. Verify what your embedder actually sees before you
trust a chunk size.

**Budgets.** Unbounded, our agent called the search tool eight times on one
question, re-reading the same passages and tripping rate limits. The fix was a
three-search budget plus cross-call duplicate suppression. Agents need
metacognition about how much context they've already consumed.

**Restraint.** We built features whose whole job is deciding not to speak. A
change watcher hashes and diffs documents *before* any model runs, so an
unchanged project costs nothing, and only material changes escalate. Teaching an
agent when to be quiet is harder — and more valuable — than teaching it to talk.

**The platform payoff.** A single `LLM_BACKEND` flag moves the entire app between
Groq, Ollama, and AWS. On AWS: Bedrock AgentCore drives chat with Claude 3.5
Sonnet, S3 stores sessions, and Bedrock Knowledge Bases ingests uploads
automatically. "Production-grade" became a config value, not a rewrite.

Sensei is on MIT terms. If your hackathon agent feels like a toy, check whether
it can find what it indexed, whether it manages its own context, and whether
anyone actually wants it to talk this much.

---

## Post 4 — Short / hook-driven

### Agents for Humans: The Teammate That Does the Paperwork

Why do AI assistants still wait to be asked? Joining a project means reading
docs that don't exist and asking questions nobody answered — work a robot should
just do. So we built **Sensei**: an agent teammate on AWS that starts working the
moment you add someone.

- It ingests GitHub, Jira, Slack, Confluence and files into a vector store and
  answers with citations.
- It writes every new teammate a cited onboarding brief — unprompted.
- It hunts for missing docs, drafts them, and marks what it inferred.
- It records questions it can't answer so one human fix helps everyone.
- It watches for change and keeps quiet unless something actually matters.

The build taught us the classics: our embedder only sees 256 tokens, so we
re-chunked from 2 000 to 800 characters to make content findable; and our own
agent had to learn a search budget before it stopped flooding its context.

**On AWS:** Bedrock AgentCore powers the agent (Claude 3.5 Sonnet), S3 keeps chat
storage persistent, and Bedrock Knowledge Bases syncs uploads as they land — all
behind one config flag.

The next teammate for your project shouldn't need a prompt. It should just know
what to do.