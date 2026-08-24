# PRODUCT REQUIREMENTS DOCUMENT
## Sensei
An independent platform that learns approved project context and participates through chat and meetings.

| Field | Value |
|---|---|
| Product stage | Hackathon MVP |
| Initial integration landscape | Platform website; Microsoft Teams; Confluence; SharePoint; Jira or ServiceNow; GitHub or Azure DevOps |
| Document status | Consolidated product requirements |

## 1. Product Summary
Sensei is a permission-aware platform that joins a project like a new team member. Through its own website, it onboards approved sources, builds a continuously updated project memory, and provides grounded answers through chat, voice, and Microsoft Teams meetings.

Microsoft Teams is an integration channel—not the product itself. The platform owns onboarding, access configuration, project context, verification, and administration.

## 2. Problem
Project knowledge is fragmented across documentation, work-management systems, repositories, chats, files, and meetings. New joiners can take weeks to understand the project, while experienced members lose time searching for basic context, status, ownership, procedures, and decisions.

## 3. Product Goals
- Reduce time-to-context for a new project team member.
- Provide a single, trustworthy way to retrieve project information during day-to-day work and live meetings.
- Keep the project context current as approved sources, tickets, code, documents, chats, and meeting records change.
- Prevent unsupported or misleading answers through evidence, citations, and explicit uncertainty.

## 4. Users and Roles

| User | Primary need |
|---|---|
| New joiner | Learn project purpose, architecture, responsibilities, procedures, and key resources quickly. |
| Developer / tester | Find current ownership, ticket context, technical decisions, and delivery information. |
| Lead / manager | Answer project, status, process, and decision questions during planning and meetings. |
| Project owner / administrator | Connect sources, define access boundaries, review coverage, and revoke access. |

## 5. MVP Scope

**Included**
- Independent platform website for project onboarding and administration.
- Configurable connections to approved sources and permission-aware indexing.
- Cited chat answers through the platform and Microsoft Teams.
- Microsoft Teams meeting participation as a named agent participant.
- Voice and text responses for verified project questions.
- Automatic updates from approved source changes.
- A complete demo: onboarding → project Q&A → change update → live meeting answer.

**Out of scope for the hackathon MVP**
- Autonomous ticket updates, code changes, or workflow execution.
- Unrestricted reading of private or personal communications.
- Full connector coverage for every enterprise platform.
- WhatsApp group ingestion before separate feasibility, consent, and policy validation.

## 6. Information Sources and Integration Priority

| Purpose | MVP sources | Future / optional |
|---|---|---|
| Documentation and procedures | Confluence, SharePoint, Word documents, shared folders | Additional document systems |
| Team communication | Selected Teams chats and channels; approved meeting transcripts or voice notes | Slack; WhatsApp subject to validation |
| Work and ticket status | Jira or ServiceNow | Other ITSM / work-management systems |
| Code and delivery activity | GitHub or Azure DevOps | Other repositories and CI/CD tools |

Source selection is explicit: an authorized project owner chooses the precise workspaces, folders, repositories, channels, chats, and historical range the agent may use. Access can be changed or revoked at any time.

## 7. Functional Requirements

| ID | Capability | Requirement |
|---|---|---|
| FR-1 | Platform onboarding | Create a project workspace, connect approved tools, select access scope, and show initial source coverage. |
| FR-2 | Project memory | Build a source-linked, time-aware map of project overview, architecture, roles, ownership, procedures, decisions, work items, and key links. |
| FR-3 | Continuous updates | Detect and ingest approved changes to documents, chats, tickets, code, and meeting records without manual re-teaching. |
| FR-4 | Grounded answers | Answer text or voice questions only from approved accessible sources and attach supporting citations. |
| FR-5 | Teams integration | Make the agent available in selected Teams chats, channels, and meetings as a visible named participant. |
| FR-6 | Meeting support | Answer direct questions in chat or voice; proactively correct information only when high-confidence evidence is available. |
| FR-7 | Permission controls | Respect source and requester permissions; prevent users from receiving content they cannot access. |
| FR-8 | Administration | Allow owners to review configured sources, adjust scope, and revoke agent access. |

## 8. Accuracy, Safety, and Trust Requirements
- Every substantive answer must be grounded in approved project content and cite the supporting source.
- When evidence is missing, incomplete, conflicting, or outdated, the agent must state that it cannot verify the answer.
- The agent must not invent ticket status, project facts, procedures, ownership, decisions, or commitments.
- Proactive corrections in meetings require high-confidence evidence and should identify the supporting source.
- Continuous learning means evidence-linked updates from approved systems—not unverified fact creation.
- The agent may summarize observable work context, such as documented responsibilities, assignments, and decisions; it must not infer sensitive personal traits or private thinking processes.

## 9. End-to-End MVP Demo

| Step | Moment | Demonstration |
|---|---|---|
| 1 | Onboard | A project owner creates a workspace on the platform website and connects selected sources. |
| 2 | Build context | The platform indexes the approved content and shows a project map with architecture, roles, active work, and key procedures. |
| 3 | Support a new joiner | A new team member asks what the project does, where to find the architecture, and what their role involves; the agent returns cited answers. |
| 4 | Refresh automatically | A ticket update or repository commit occurs; the agent refreshes the relevant project context. |
| 5 | Join a Teams meeting | The agent enters as a named participant in an integrated Teams meeting. |
| 6 | Answer live | A participant asks for status, process guidance, ownership, or a prior decision. The agent answers with evidence—or clearly declines to guess. |

## 10. Solution Architecture

| Layer | Responsibility |
|---|---|
| Platform website | Project setup, source selection, administration, coverage review, and project chat. |
| Integration layer | Authorized connectors for documents, work items, repositories, chats, meeting records, and Teams. |
| Continuous project memory | Permission-aware, source-linked, timestamped knowledge of project information and relationships. |
| Grounded answer engine | Retrieves relevant sources, verifies support, composes cited answers, and refuses unsupported claims. |
| Experience channels | Platform chat and voice, plus Microsoft Teams chat and meeting participation. |

## 11. Success Metrics
- A new joiner receives a cited project overview and role guidance in minutes.
- A Teams participant receives a cited answer to a live project question.
- The agent declines unsupported questions rather than hallucinating.
- A project owner can demonstrate scoped source selection and access revocation.
- The demo communicates meaningful project value with a simple, realistic workflow.

## 12. Future Direction
After the hackathon, expand source coverage, add richer organization and project graphs, introduce notification and change-summary workflows, and validate additional collaboration channels. WhatsApp should only be considered after a dedicated review of technical capability, consent, retention, and organizational policy.

## 13. External Platform Notes
Microsoft Teams is a suitable first integration because it supports teams, channels, chats, meetings, and apps, with channel files tied closely to SharePoint. Confluence supports collaboration with Teams, and ServiceNow supports Microsoft Teams and Microsoft 365 integration. These facts inform connector prioritization; actual availability depends on each customer tenant, licensing, and administrator approval.

Sources: Microsoft Teams documentation; Atlassian Confluence integration guidance; ServiceNow integration documentation.
