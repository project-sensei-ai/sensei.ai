# Agents for Humans Hackathon — Rules & Build Considerations

Source: [hackathon page](https://agentsforhumans.devpost.com/) · [official rules](https://agentsforhumans.devpost.com/rules)

> **TL;DR:** New agent built with **Strands Agents SDK**, handles repetitive tasks **end to end**, submitted with a public repo (MIT/Apache), README, architecture diagram, ≤5-min demo video, and an optional live demo link. Judged equally on Technical Implementation, Design, Impact, Creativity, Presentation (+0.6 bonus points possible).

---

## 1. Key Dates

| Event | Date |
|---|---|
| Submission period opened | Aug 10, 2026 |
| **AWS credits request deadline** ($50 form) | **Sep 11, 2026, 12:00 PM PT** |
| **Submission deadline** | **Sep 14, 2026, 5:00 PM PDT** |
| Judging period | Sep 15 – Oct 8, 2026 |
| Winners announced | ~Oct 14, 2026 |

After the deadline the submission is **locked** — no edits allowed. Save drafts on Devpost before submitting.

---

## 2. The Core Requirement (pass/fail gate)

Build a **new AI agent with Strands Agents SDK** that does real work for real people — handling tasks **end to end, not just chatting about them**. It should run autonomously in the background and surface only when there's a real decision to make.

**Stage One judging is pass/fail:** the project must reasonably fit the theme AND genuinely use Strands Agents. Fail this and nothing else matters.

### Tracks — pick ONE

| Track | For | Our fit |
|---|---|---|
| Everyday Agents | Daily life busywork: home, money, health, errands, family | |
| **Professional Agents** | Makes someone dramatically better at the work they already do | ✅ **our pick** — Sensei kills repetitive context-gathering for dev teams |
| Good Neighbor Agents | Groups/orgs: neighborhoods, nonprofits, schools, libraries | |

Deploying on **Amazon Bedrock AgentCore** strengthens the Technical Implementation score (not mandatory). A **live demo link** also boosts it.

---

## 3. Hard Submission Checklist

Every item below is required — missing any risks disqualification:

- [ ] Text description (what it does, who it's for, how it works)
- [ ] **PUBLIC** code repo (GitHub/GitLab/Bitbucket) with all source + setup instructions to run it
- [ ] **MIT or Apache license file at repo root**, detectable in the GitHub About section
- [ ] README
- [ ] **Architecture diagram**
- [ ] Demo video, **max 5 minutes**, public on YouTube/Vimeo, containing:
  - Working-project demonstration
  - Pitch covering all three: **(1) problem, (2) who it's for, (3) why it matters**
  - Slides/screen recording/voiceover fine — camera not needed
- [ ] AWS Builder ID
- [ ] (Optional, recommended) Live demo URL — scores higher on Technical Implementation
- [ ] All materials in **English**

### Bonus points (up to +0.6 total)

Publish build-journey posts on **builder.aws.com** with "**Agents for Humans**" in the title.
- 0.2 points each, max 3 posts (+0.6). Final scores range 1–5.6.
- Must be **publicly published before the submission deadline**.
- Plan: publish 2–3 short posts across the final two weeks (setup journey, Strands tool design, deployment story).

---

## 4. Compliance Rules That Can Disqualify Us

1. **New projects only.** Work must be created during the submission period. AI coding assistants and starter templates ARE allowed, but any pre-existing code incorporated must be **disclosed**. Our repo started Aug 2026 → clean.
2. **Third-party integrations.** Every external SDK/API/data source (Google OAuth, OpenAI, GitHub API…) must be used per its terms of service. Fine at hackathon scale; document keys come from our own accounts.
3. **Working & consistent.** The app must install/run reliably and function **as depicted in the video**. Don't demo anything that isn't reproducible by judges.
4. **Judges must be able to test it.** Provide a working link or test build, free of charge, available until judging ends Oct 8. If auth exists → include **test login credentials in testing instructions** (our Google OAuth needs a demo account path!).
5. **Original work / IP.** Solely owned by us, no third-party rights violated. Open source deps allowed if licenses complied with.
6. **One prize per project.** Multiple submissions allowed but must be substantially different.
7. **No sponsor support.** Project must not be developed under contract/funding from AWS.
8. **Eligibility.** Team members must be legal age of majority; excluded territories include Argentina, Australia, Brazil, Hong Kong, Indonesia, Italy, Malaysia, Philippines, Quebec, Singapore, Thailand, Vietnam, UAE, Russia, Belarus, Iran, Cuba, North Korea, Syria, Crimea, DNR/LNR.
9. **Public repo discipline.** Since the repo goes public: **no committed secrets** (`.env` stays gitignored, `.env.example` holds placeholders only), no personal data, no proprietary client code.

---

## 5. Judging Criteria → What We Actually Do

All five criteria are **equally weighted** (20% each):

| # | Criterion | Judge asks | Our action |
|---|---|---|---|
| 1 | **Technical Implementation** | Deep, skillful use of *Strands Agents*? Non-trivial working code? | Real agent loop with multiple custom `@tool`s (search, github, upload, url crawl), MemoryManager, streaming. Deploy on **AgentCore** + ship **live demo URL**. Show Strands usage prominently in README + diagram. |
| 2 | **Design** | Complete coherent product, not just a proof of concept? | Polished UI: landing → Google login → onboarding wizard → cited chat. Handle empty/error/loading states. No dead buttons in the demo path. |
| 3 | **Potential Impact** | Credible, specific problem for a real audience — demonstrated? | Frame tightly: "new joiners lose weeks to scattered context." Demo the time saved concretely (before/after). |
| 4 | **Creativity & Originality** | Non-obvious use of Strands? Genuine problem-space insight? | Emphasize the permission-aware memory + continuous refresh angle, not "another RAG chatbot." |
| 5 | **Presentation** | Video shows it working end to end? Problem/who/why clear? | Scripted ≤5-min video: 30s problem → 60s architecture → 2.5min live demo → 30s impact. Rehearse; captions on. |

Tie-breaker order starts with criterion 1 — another reason to maximize Technical Implementation.

---

## 6. Build Considerations Derived From the Rules

1. **Strands-first architecture.** Don't hand-roll RAG pipelines around the LLM — let Strands' agent loop + tools do the orchestration. Judges read the code for genuine Strands usage (`@tool`, `Agent`, memory, streaming).
2. **LICENSE file day one.** MIT at repo root, so it shows in the About badge when judges visit.
3. **Architecture diagram early.** Needed for submission anyway; draw it once the ingestion flow stabilizes.
4. **Demo account strategy.** Auth is Google-only — provide either a seeded demo login (email-link style bypass flagged as demo-only) or clear testing instructions with a dedicated demo Google account.
5. **Deployment target:** aim for AgentCore (score boost); fallback = public EC2/App Runner URL behind HTTPS. Either way, the live link must stay up through Oct 8.
6. **Video assets:** record screen takes as features land — don't leave recording to the last day.
7. **Blog cadence:** draft builder.aws.com post outlines now; publish first one ≥1 week before Sep 14 so moderation delays don't cost bonus points.
8. **Costs:** request the $50 AWS credits (form closes Sep 11, 12pm PT); credits expire Oct 31. Monitor spend — overages are ours.
9. **Freeze plan:** feature freeze ~Sep 10; last days reserved for video, diagrams, Devpost form, and a full clean-machine setup test (`git clone` → run instructions → works).
