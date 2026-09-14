# Devpost submission — Sensei

Written for: whoever fills in the Devpost form and records the video. Copy
from here; do not improvise on camera.

Track: **Professional Agents**. Built with **Strands Agents SDK**.

---

## Title

**Sensei — a colleague you onboard, not a chatbot you prompt**

## Tagline (≤ 140 chars)

Project owners onboard Sensei like a new hire: sources, tools, a seat in
meetings. It works on its own and stays quiet when it should.

## Text description

**The problem.** Every project team has one person everyone interrupts: the
one who knows where the runbook is, who owns the notify service, what was
decided about Friday deploys, and what Priya changed last week. New joiners
lose weeks finding that person; that person loses hours being found. Chat
assistants do not fix this, because the knowledge is not in a chat — it is in
Confluence, GitHub, Jira, and in meetings nobody wrote down.

**What Sensei is.** A colleague a project owner *onboards*. The owner hands
it what they would hand a new hire: the wiki space, the repo, the ticket
project, and accounts on the tools the team uses — connected as MCP servers
with the owner's own credential. Then the owner adds their team, and Sensei
goes to work for them.

**What it does on its own.** Once the sources settle it interviews itself:
it writes the eight questions a new joiner would ask this project, answers
each from the sources alone, and grades itself — "ready for 5 of 8", with the
three it failed already in the ledger for a human to close once. When a
teammate is added, Sensei researches the project and writes them a cited
onboarding brief before they first log in.
When a source lands, it audits what the project *failed* to document and
offers to draft the missing pages. It re-reads sources on a schedule and
speaks only when something material changed. Questions it cannot answer go
in a ledger; one human reply becomes permanent knowledge.

**What it does when asked.** Cited answers, streamed, with every tool call
narrated. "What did Ravi change last week" reads his commits and PRs, not
prose about him. "What's the status of APOLLO-42" is read live from Jira, never
from a stale index. "Put the open issues in a spreadsheet" produces an .xlsx.
"Create the issue" goes through the connected GitHub tools — or is refused,
inside the agent loop, if the owner has not allowed writes on that connection.

**In meetings.** Sensei sits in the call. It answers when addressed. It
corrects a wrong claim only when a typed verdict says the project's own
documentation contradicts it, with confidence above 0.8 and a citation — all
three, or it stays quiet, and records why. Afterwards it writes the notes and
indexes them, so "what did we decide about the rollout" is answerable next
week with a citation to the meeting.

**Trust.** Every credential is encrypted at rest and listed with its ceiling
(what it *could* reach) beside its floor (what Sensei reads). Every granted
tool is listed by name and class. Two members of one project can be answered
from different sources, enforced inside the vector query. Nobody reaches a
project unless the owner added their email.

**How it is built.** Strands `Agent` with custom `@tool`s and MCP tools
loaded through `MCPClient`; a `BeforeToolCallEvent` hook enforces the write
gate; a Strands `Graph` of three agents researches each onboarding brief;
`structured_output` produces typed briefs, gap reports, change verdicts,
claim verdicts and meeting notes; `stream_async` narrates tool calls to the
UI. FastAPI, React, MongoDB, ChromaDB. One container, HTTPS via Caddy, on
AWS EC2. Model backends: Bedrock, Groq or Ollama behind one flag.

## Built with

Strands Agents SDK · Model Context Protocol · Amazon Bedrock · Amazon EC2 ·
FastAPI · React · MongoDB Atlas · ChromaDB · Playwright · Caddy

---

## Video script (≤ 5:00)

Record at 1440×900, captions on, cursor visible. Two browser windows ready:
Maya (owner) and Priya (member). Rehearse; do not narrate errors.

| Time | On screen | Voice |
|---|---|---|
| 0:00–0:25 | Title card, then the Confluence team-directory page with "notify-service: no named owner" | "Every team has one person everyone interrupts. Sensei is that person — onboarded like a hire, not prompted like a bot." |
| 0:25–0:55 | Register as a new owner: the **onboarding conversation** — name the project, connect the repo, then **Sign in with Atlassian** → the Atlassian consent page → back: "Atlassian is connected — 22 things I can look up and 10 I could change, which stay off until you say so" | "Onboarding is a conversation. Maya gives it what she'd give a new hire: the repo, and an account — she signs in, Sensei gets a token. Every tool is classified read or write. Writes are off until she says otherwise." |
| 0:55–1:20 | **Dashboard → Team**: add priya@apollo.demo. Cut to Priya's first login: her **brief** already written, cited, with "What nobody wrote down" | "Then she adds Priya. Nobody asks Sensei anything. It researches the project for Priya and writes her a brief — waiting when she first logs in. The last section is the honest one: what the sources cannot tell her." |
| 1:20–1:45 | **Dashboard**: the readiness card — "Ready for 5 of 8 first-week questions", open the list, the ✗ ones marked "not in the sources", then **Answers** showing them in the ledger asked by "Sensei (self-check)" | "Before it starts, it interviews itself: the questions a new hire would ask, answered from the sources alone, graded honestly. What it fails goes to the ledger — a human answers once, and it knows forever. Then **Gaps**: what nobody wrote down, drafted where the sources allow." |
| 1:45–2:35 | **Chat** as Priya: "What did Daniel change recently?" → who_did_what narration → cited answer. Then "Put the open issues and PRs in a spreadsheet" → tool trail: GitHub list issues → list PRs → building the spreadsheet → download chip; open the .xlsx | "Ask it like a colleague. Who did what comes from commits and PRs, not prose. Ask for a spreadsheet and it uses the GitHub tools, then hands you the file." |
| 2:35–3:00 | Chat: "Create an issue for the notify-service owner gap" → tool trail shows the write attempt → the refusal sentence. Cut to Maya's Tools page, flip "Allow writes", back to Priya, retry → issue created, link shown | "It tried to create the issue and was refused — inside the agent loop, not by a prompt. Maya allows writes. Now it does it, because a person asked." |
| 3:00–3:50 | **Meetings**, companion mode, mic on. Ravi (you, second voice) says "we deploy to us-east-1". Sensei stays quiet. Then "the primary database is DynamoDB" → correction bubble with 0.9 and the ADR cited. Then "Sensei, who's on call next week?" → spoken answer. End meeting → notes with decisions | "In a meeting it listens. A wrong claim that the docs contradict gets a correction — with the source, only above 0.8 confidence. Addressed by name, it answers. When the call ends, it writes the notes and indexes them." |
| 3:50–4:20 | **Trust** page: ceiling vs floor for the Confluence token, the GitHub tools by class, "what it never does". Then **Answers**: the ledger and "answered without a human" | "Everything it can reach, with the honest ceiling of each credential. And the number this product lives on: questions answered without a human." |
| 4:20–4:50 | Architecture diagram; code flash of `@tool`, `MCPClient`, `BeforeToolCallEvent`, `GraphBuilder`, `structured_output_async` | "Built on Strands: custom tools and MCP tools in one loop, a hook that enforces the write gate, a three-agent graph for research, typed outputs everywhere, streaming to the UI. One container on AWS." |
| 4:50–5:00 | Live URL + repo on screen | "Sensei. Onboard it like a colleague." |

## Judge instructions (paste into "Testing instructions")

See `TESTING.md` in the repo. Two projects, two owners:

- `judge@sensei.demo` / `Demo-miwVU8NczE6N` — owns **Sensei Demo Project**
  (this codebase's own documentation).
- `maya@apollo.demo` / `Apollo-Demo-2026!` — owns **Apollo Delivery**, a
  realistic sample project with a repo, a Confluence space and GitHub tools
  with writes allowed. Members `priya@apollo.demo` and `ravi@apollo.demo`,
  same password, see it as teammates.

No AWS account, Google account or credential of your own is needed.

## Bonus: builder.aws.com posts (0.2 each, title must contain "Agents for Humans")

1. *Agents for Humans: onboarding an agent like a hire — tool grants with MCP
   and Strands.* The write gate as a `BeforeToolCallEvent` hook; why refusing
   inside the loop beats hiding the tool.
2. *Agents for Humans: teaching an agent when to shut up.* The silence
   conditions — citations as the gate for speaking in channels, typed verdicts
   with a confidence floor for corrections in meetings.
3. *Agents for Humans: a Strands Graph that writes onboarding briefs before
   anyone logs in.* Research once, compose per person, invalidate on change.
