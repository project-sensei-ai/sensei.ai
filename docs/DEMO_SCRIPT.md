# Sensei, five-minute demo script

Live site: https://54-80-119-54.sslip.io. Before recording: two Chrome windows signed in, Maya (maya@apollo.demo) and Priya (priya@apollo.demo), plus Slack open on #all-sensei. Answers take 2 to 10 seconds; let each finish before the next line. Never show the Meet bot. If a step fails, redo it; never narrate an error.

Spoken as one continuous voiceover. Cues in brackets are what is on screen.

**[0:00, landing page: hold on the headline, then scroll to the four question cards]**

If you've ever worked on a software team, you know this person. The one everyone messages when they're stuck. Where's the rollback runbook? Who actually owns the notify service? Why do we never deploy on Fridays? The answers exist, they really do, but they're scattered. One's in Confluence, one's in a Jira ticket, one's buried in a Slack thread, and one was decided in a meeting nobody wrote down. So a new joiner spends weeks finding that person, and that person spends hours every week being found. And a chatbot doesn't fix this, because the knowledge was never in a chat to begin with.

**[0:35, scroll to "You onboard it like a hire"]**

That's the problem we built Sensei for. The idea is simple: instead of prompting a bot, you onboard a colleague. You give Sensei what you'd give a new hire on day one, the wiki, the repo, the tickets, the Slack channel, and accounts on the tools your team already uses. Then it gets to work for everyone.

**[0:50, Maya's window: Sources, then Tools with the GitHub tool list open, point at read, write, and the Allow writes switch]**

Let me show you what that looks like. This is Apollo Delivery, a sample project we made realistic on purpose. Maya, the owner, has connected the repo, a Confluence space, a Jira project, the team's Slack channel, a few documents and a URL. Over on Tools, she's also given Sensei a GitHub account, and notice that every tool it gets is labelled read or write. Writes stay off until Maya flips this switch herself. That's a decision she makes, not something a prompt can talk its way around.

**[1:15, Priya's window: her Brief, scroll once, stop on "What nobody wrote down"]**

Now here's the part I like. Nobody has asked Sensei a single question yet. But when Maya added Priya, Sensei went and researched the project for her and wrote this brief, and it was waiting when she logged in for the first time. What the system is, how it ships, who owns what. And down at the bottom, my favourite section: what the sources can't tell her. It's honest about the gaps.

**[1:35, Maya's window: Dashboard readiness card, open the list, then Answers]**

It's honest with itself too. Before it answers anyone, it interviews itself. It writes the eight questions a new joiner would ask about this project, answers each from the sources alone, and grades itself strictly. Here it's ready for seven of eight. And the one it couldn't answer is already sitting in this ledger. A human answers it once, in a sentence, and from then on Sensei knows it forever.

**[2:00, Priya's window: Chat. Type: Who is on call the week of 15 September, and what is the production deploy window? Expand "Thought for", then the sources]**

Okay, let's actually ask it something, the kind of thing Priya would ask in her first week. Who's on call the week of the fifteenth, and what's the deploy window? Watch the steps as it works. It searched the project's documents, and now it's writing. Daniel's primary, Ravi's secondary, Priya's the release captain, and deploys happen Tuesday to Thursday, Irish time, never on a Friday. Plain sentences, the facts in bold, and right underneath, the exact pages it read.

**[2:25, Chat: What has Daniel Okafor worked on recently? Point at "Reading the activity records"]**

Now ask about a person, and something different happens. It doesn't go looking for prose about Daniel. You can see it pick a different tool, reading the activity records, which means his actual commits, pull requests and tickets. So the answer is what he did, not what someone wrote about him.

**[2:45, Chat: Put the KAN Jira tickets in a spreadsheet with key, title and owner. Click the download chip, open the file]**

And it doesn't only answer, it does work. Ask for the Jira tickets in a spreadsheet and it reads Jira live, right now, not from an index that was accurate yesterday, then builds the file and hands it over. There it is.

**[3:05, judge account: Chat: Create a GitHub issue titled "Assign an owner to notify-service". Show the refusal]**

Here's the flip side. The same kind of request from someone whose owner hasn't allowed writes, creating a GitHub issue, and it's refused. Not deflected by a polite prompt, refused inside the agent loop. And it tells you plainly who can lift that.

**[3:20, Slack: mention @sensie bot what's the production deploy window? Then, no mention: does anyone know when the Fabrikam demo is? Then: lunch anyone? If live replies aren't configured yet, show the existing threads]**

Sensei's also in Slack, the way a colleague would be. Mention it and ask about the deploy window, and it answers right in the thread, with its source. But watch this. If I just ask the room when the Fabrikam demo is, without mentioning it at all, it still steps in, because it can cite the answer. And if I say lunch anyone, nothing. It knows that's not for it. Meanwhile every message here is indexed as it lands, so something decided at ten-oh-two is askable at ten-oh-three.

**[3:50, Maya's window: Meetings, companion mode. Type as Ravi: We deploy Apollo to us-east-1. As Priya: Sensei, who owns the routing worker? Then: Let's grab lunch after this. End the meeting]**

It even sits in meetings. Say Ravi claims we deploy to us-east-1. That contradicts the architecture doc, so Sensei corrects him, with the source, and it only does that above eighty percent confidence. Priya asks it directly who owns the routing worker, and it answers. Then someone suggests lunch, and it stays quiet, and tells you why. When the meeting ends, it writes up the notes and indexes them, so next week's "what did we decide" has an actual source.

**[4:20, Trust page: a credential's ceiling and floor, the tools by class, the never list]**

All of that access lives on one page. For every credential, what it could reach and what Sensei actually reads, which tools may write, and the list of things it will never do. We think trust should be something you can read, not something you're promised.

**[4:35, architecture diagram, then a quick code flash: build_colleague, the WriteGate hook, the Slack service]**

Under the hood it's a single Strands agent loop, equipped fresh for every question: our own tools, the MCP tools from the owner's accounts, a hook that enforces the write gate, a three-agent graph that writes the briefs, typed outputs everywhere, all streamed to the UI. Claude Haiku does the answering, and the whole thing runs in one container on AWS.

**[4:50, landing page, "Try it now", then the URL]**

It's live right now, with a real project already onboarded and accounts you can log in with. Sensei. Onboard it like a colleague.

About 760 spoken words: a relaxed 150 a minute lands at five minutes, with the pauses landing while answers stream.
