# Sensei — Requirements v2

Written for: the Sensei builder, as the working spec for the final push.

Source: owner's brief, 2026-09-13. Restated here as numbered requirements with
acceptance criteria. Section 10 is my triage against the deadline — the owner's
intent in 1–9 is recorded as given and not edited.

**Deadline: Sep 14 2026, 17:00 PDT = Sep 15, 05:30 IST. ~43 hours from writing.**

---

## 1. Two participant types

**R1.1** The product has exactly two roles: **Project Owner** and **Team Member**.

**R1.2** Only an Owner can onboard an agent for a project — create the workspace,
connect sources, and configure scope.

**R1.3** A Team Member can join a project **only if the Owner has already added
them**. Someone who has not been added cannot join, cannot reach a dashboard, and
cannot chat. An invite link alone is not sufficient authorisation.

*Acceptance:* a person who was never added by an Owner, holding a valid invite
link, is refused with a clear message. A person who was added joins successfully.

## 2. Role choice at sign-up

**R2.1** The sign-up screen offers two choices: "I'm setting up a project" (Owner)
and "I'm joining a project" (Member).

**R2.2** The chosen role is stored on the user and drives every subsequent screen.

*Acceptance:* the choice is visible, required, and persisted.

## 3. Member gating

**R3.1** A user who signed up as a Member never sees any agent-onboarding UI —
no wizard, no "connect a source", no workspace creation.

**R3.2** On login, a Member reaches a project dashboard **only** if an Owner has
added them to that project. Otherwise they see a holding state explaining they
are waiting to be added.

**R3.3** Unauthenticated visitors cannot reach any dashboard.

**R3.4** The Owner can add members in **two places**:
- during agent onboarding, in the same flow as connectors and tools
- from the dashboard at any time afterwards

*Acceptance:* both entry points exist and write to the same member list.

## 4. Confluence on the Sources page

**R4.1** Confluence appears as an addable source type on the Sources page, not
only in the onboarding wizard.

*Current state:* the backend accepts `type: "confluence"` and the onboarding
wizard has the form, but `Sources.tsx` has only the Confluence **icon** — there
is no way to add one after onboarding. This is a real gap.

## 5. Confluence access — what the agent needs, and what to ask for

**R5.1** Document precisely what credentials and scopes an AI agent needs to read
Confluence, and the trade-offs between the available methods.

**R5.2** Ask the Owner for exactly those things — no more — at both the
onboarding stage and the Sources stage, with each field explained in plain
language ("what this lets the agent see", "what it cannot see").

## 6. Two more commonly-used work tools

**R6.1** Add two further connectors that working teams actually use day to day.

**R6.2** For each, define how the agent obtains access, what scope the Owner
grants, and what the agent is prevented from reading.

## 7. Showing that access is handled securely

**R7.1** Find the best way to *demonstrate* to a user — not merely assert — that
every access the agent holds is scoped, visible, and revocable.

**R7.2** Implement it in the product.

**R7.3** Produce a detailed diagram of the security and access model.

## 8. UI enhancement

**R8.1** Raise the visual and interaction quality across the product.

## 9. Anything else worth doing

**R9.1** Identify further additions or adjustments that improve the product or
the submission.

## 10. Hackathon outcome

**R10.1** Measure the submission against `docs/HACKATHON.md` and maximise the
chance of winning. Where the current state falls short, identify what closes the
gap.

---

# Triage against 43 hours

The requirements above total roughly 40–50 hours of work. The submission also
needs assets that do not exist yet. Both cannot happen. This section is my
recommendation, not the owner's instruction.

## What is currently a guaranteed loss

| Gap | Consequence |
|---|---|
| No demo video | **Presentation is 20% of the score.** With no video that is a zero — and the video is a *hard submission requirement*, so its absence risks disqualification, not just a low score. |
| Repo still private | **Pass/fail gate.** A private repo fails submission outright. |
| No live demo URL | Foregoes the Technical Implementation boost, and judges must run it themselves. |
| No Devpost text / Builder ID | Required fields. |

These four cost about 8 hours total and are worth more than every feature in
sections 1–8 combined. They are not negotiable and they should not be left last.

## The risk nobody has named

`docs/HACKATHON.md` §2 sets a **pass/fail** theme gate:

> handles tasks **end to end, not just chatting about them** … runs autonomously
> in the background and surfaces only when there's a real decision to make

Sensei today is a chat box. A judge applying that sentence strictly could fail it
at Stage One, and nothing else would matter. This is the highest-severity issue
in the project and it is not on the owner's list.

**Proposed fix — the Auto Onboarding Brief (R11).** When an Owner adds a member,
the agent *without being asked* researches the project and writes that person a
cited onboarding brief: what the project is, who owns what, where the code and
docs live, what is in flight. It is waiting for them when they first log in.

Why this is the right fix:
- It is work done **end to end**, not a conversation about work.
- It is **autonomous** — triggered by an event, not a prompt.
- It **surfaces when there is something worth surfacing** — a new joiner arriving.
- It is the literal product thesis: "new joiners lose weeks to scattered context."
- It reuses the agent, the tools and the citation path that already exist. ~2–3h.
- It makes the demo far stronger: a member logs in and the work is already done.

It also folds requirements 1, 2 and 3 into the story instead of leaving them as
plumbing: the Owner adds a person, and the agent immediately does something for
that person.

## Recommended plan

Ordered by score impact per hour. Times are build estimates, not elapsed.

| # | Work | Est. | Why it earns its place |
|---|---|---|---|
| A | Repo public + rotate AWS keys | 15 m | Pass/fail gate |
| B | Deploy the live URL | 2–3 h | Do this **early** — deploys always fight back |
| C | **R11 Auto Onboarding Brief** | 2–3 h | Removes the theme-gate risk; best demo moment |
| D | **R7** Trust & Access page + diagram | 4–5 h | The differentiator: Creativity + Impact. Most data already exists |
| E | **R1–R3** roles, owner-managed allowlist, gating | 4–5 h | Reframed as an allowlist, it *is* part of the security story |
| F | **R4 + R5** Confluence on Sources, explained | 1.5 h | Closes a visible gap cheaply |
| G | **R6** Jira connector | 2 h | Shares Atlassian credentials with Confluence — nearly free, and it makes "what's the status of ticket X" a real demo |
| H | **R8** UI pass, demo path only | 3–4 h | Design is 20%, but scope it to screens that appear on camera |
| I | Demo video + Devpost + description | 4–5 h | 20% of the score |

Total ≈ 24–29 h of build inside a 43 h window. That leaves room to sleep once and
for one thing to go wrong.

**Hard rule: all feature work stops at T-10h.** Whatever is done is what ships.
The video is recorded against a frozen build, not a moving one.

## What I recommend cutting

- **The second new tool in R6.** One well-built Jira connector beats two
  half-built ones, and Jira comes nearly free off the Confluence credentials.
- **R8 as a general UI overhaul.** Unbounded. Restrict to the six screens that
  appear in the video.
- **R3.4's second entry point**, if time runs short. Adding members from the
  dashboard is the one to keep; adding them mid-onboarding is the one to drop.
- **builder.aws.com bonus posts** (+0.6) unless everything else is done. They are
  worth real points but only after the required items exist.

## On "99% chance of winning"

That number is not available to anyone. The field is unknown, three of the five
criteria are subjective, and a single judge's taste can move a placing. What can
be said honestly:

- Right now the submission would **fail the pass/fail gate** (private repo) and
  **score zero on Presentation** (no video). Those are certainties, not risks.
- The theme gate ("end to end, not just chatting") is a genuine second failure
  mode, and R11 is the cheapest credible answer to it.
- After A, B, C, D and I, this is a *competitive* submission: a working product,
  a real differentiator, an honest architecture, and a clear story.
- Beyond that, more features do not reliably buy more placing. A tight five
  minutes showing a real person getting real work done beats a longer feature list
  shown badly.

The single highest-leverage hour left is the one spent on the video.
