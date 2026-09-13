# How the agent gets access to each tool

Written for: whoever reviews what Sensei can reach — a project owner, or the
person who has to sign off on it.

One rule runs through all of it: **say what the credential actually authorises,
not what we intend to use it for.** Those are different, and the gap is where
trust is won or lost.

---

## The distinction that matters

Every connector has two limits, and they are not the same thing:

| | What it means | Who enforces it |
|---|---|---|
| **Ceiling** | The most the credential *could* reach | The source system |
| **Floor** | What Sensei actually fetches and indexes | Sensei's own policy |

A product that shows you only the floor is telling you a comfortable half-truth.
An owner deciding whether to paste in a token needs the ceiling.

Where the two differ, the fix is always the same shape: **give the agent its own
account in the source system, with access to only what the project needs.** That
converts a policy limit into a technical one, and it is the recommendation we
surface in the UI for every connector where it applies.

---

## Confluence

**What we ask for:** site URL, account email, API token, space key.

**How it authenticates:** HTTP Basic, email + API token, against
`/rest/api/content`.

**The ceiling.** An Atlassian API token authorises **as the person who created
it**. Authorization is based on that account's own permissions — there is no
scope parameter, and no way to restrict a token to one space. If that person can
read the HR space, the token can read the HR space.

**The floor.** Sensei fetches pages in the one space key the owner names.
Nothing else is requested, chunked, or indexed.

**Operational catch.** Since January 2025 Atlassian API tokens **hard-expire at
one year** and must be rotated by hand. A connector that silently stops working
in twelve months is a support problem; the UI says so at the point of entry.

**What we tell the owner, in the form itself:**

> - Sensei reads: pages in the `ENG` space only.
> - The token could reach: everything that account can see in Confluence.
>   A token authorises as its owner — Atlassian has no way to narrow it to one space.
> - So: use a dedicated Atlassian account invited only to the spaces this project
>   needs. Then the limit is enforced by Confluence, not just by us.

**Where this should go next.** OAuth 2.0 (3LO) with `read:content:confluence`.
Under 3LO the effective access is the **intersection of the requested scopes and
the user's own permissions**, so the ceiling drops to something we can state
precisely. It is also centrally revocable from Atlassian admin and carries no
annual rotation chore. It needs an app registered in the Atlassian developer
console and a callback URL, which is why it is not in this build.

---

## Jira

Jira shares Atlassian's identity system with Confluence, so a project already
supplying Confluence credentials has supplied Jira's too — the same site, email
and API token, pointed at `/rest/api/3/search` instead.

**What we ask for:** site URL, account email, API token, project key.

**Ceiling and floor:** identical to Confluence. The token authorises as its
owner; Sensei fetches issues in the named project. Same recommendation: a
dedicated account, added to only the relevant projects.

**Why it earns its place.** "What's the status of PROJ-412?" and "what's blocked
in this sprint?" are the questions teams actually ask, and they cannot be
answered from documents. This is also the first connector where **freshness**
becomes visible: a ticket's status changes hourly, so an answer from a
day-old index is worse than no answer. The indexed copy is for *finding* issues;
anything stated as current status should be read live.

---

## GitHub

**What we ask for:** a personal access token with `repo`, `user`, `project`.

**Ceiling.** A classic PAT carries the scopes granted to it across **every
repository the account can see**. It is the least contained credential in the
product.

**Floor.** One repository, chosen from a list, per source.

**Where this should go next, and it is the biggest single improvement
available.** A **GitHub App** installed on named repositories: access is granted
per repo by an org admin, tokens are short-lived and minted per installation,
webhooks arrive for free, and collaborator/team lists come with it so
per-item permissions become possible. It closes the gap between ceiling and
floor almost entirely.

---

## Files and URLs

**Files** carry no credential. The owner uploads what they choose; there is
nothing else the agent could reach.

**URLs** carry no credential either, which is precisely the limit: Sensei can
only fetch pages that are already public. A link behind a login returns the login
page, and that is what would get indexed. Each URL is reachability-checked before
it is stored so this fails loudly rather than quietly.

---

## Tool grants (MCP servers)

A source is something the agent reads. A tool grant is something it can
*use*: any server speaking the Model Context Protocol — GitHub's, Zapier's
(which fronts Gmail, Sheets, Slack, Calendar and thousands more), Sentry's, or
one an organisation runs internally — connected with a credential the owner
pastes as the Authorization header.

**What we ask for:** for servers that support MCP's OAuth profile (Atlassian,
Notion, Linear, Sentry, Asana, Intercom…), nothing but a click: Sensei
registers itself with the server dynamically, the owner logs in on the
vendor's own page, and the token that comes back is stored encrypted and
refreshed automatically. For the rest, a name, the server URL (or a local
command for stdio servers), and an Authorization value.

**Ceiling.** Whatever the token's account can do on that service. A GitHub
PAT with `repo` can open, comment on and close issues and PRs across every
repository it can see; a Zapier MCP token can do whatever the Zapier account's
enabled actions can.

**Floor, and how it is enforced.** On connection, every tool the server lists
is classified **read** or **write** — from the server's own annotations when
it provides them (`readOnlyHint`, `destructiveHint`), and from the tool's name
otherwise. Write tools are refused unless the owner switches *Allow writes* on
for that connection. The refusal is a Strands `BeforeToolCallEvent` hook that
cancels the call inside the agent loop and hands the model a message saying so;
it does not depend on the prompt being obeyed. Individual tools can also be
disabled by name. Unprompted work (briefs, audits, the watcher) never gets
granted tools at all.

**What the owner sees.** The Tools page and the Trust page list every tool by
name and class, whether writes are allowed, how many times the connection was
used and when. Revoking takes effect on the next turn.

**Recommendation, same as every connector:** give the agent its own account on
the service, scoped to the project — a fine-grained GitHub PAT limited to the
project's repositories, a Zapier account with only the needed actions enabled.
Then the ceiling is enforced by the service, not only by our gate.

---

## Meetings

**Companion mode** transcribes the microphone of the device running the page
and posts each finished sentence to the server. Nothing is recorded; the
transcript exists only as text, and only the people on the project can read
it. **Bot mode** joins a Google Meet as a named guest; the host admits it, and
it reads the meeting's own live captions.

**Ceiling:** the words said while it is in the call. **Floor:** the same. It
cannot join a meeting it was not sent to, and cannot hear anything after it
leaves. Ended meetings are summarised and indexed as a source labelled as a
meeting; claim checks exclude that source, so a remark in one meeting can
never be cited as documentation in the next.

---

## What we will not do

- **Ask for a password.** Never, for any connector. Tokens can be revoked and
  scoped; a password is the whole account, permanently.
- **Email a credential.** Invites carry a single-use link and the recipient sets
  their own password. A password sent by email lives in that inbox forever.
- **Ask for more scope than the connector needs**, or ask for write scope at all.
  Nothing in this build writes back to a source system.

---

## Summary

| Connector | Credential | Ceiling | Floor | Best next step |
|---|---|---|---|---|
| Confluence | API token (Basic) | Everything the account sees | One named space | OAuth 3LO, `read:content:confluence` |
| Jira | Same token | Everything the account sees | One named project | OAuth 3LO + live reads for status |
| GitHub | Classic PAT | Every repo the account sees | One repo per source | GitHub App, per-repo install |
| Files | none | — | What was uploaded | — |
| URLs | none | Public web only | The listed pages | — |
| MCP tool grant | Bearer token or API key | Whatever that account can do on the service | Read tools; write tools only if the owner allowed them, enforced in a hook | A service account scoped to the project |
| Meetings | none | What is said while it is in the call | The same | — |

The pattern in the right-hand column is the same every time: move from a
credential that borrows a human's whole identity to one that carries its own,
narrower, revocable grant.
