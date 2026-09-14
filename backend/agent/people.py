"""
Who did what.

"What has Ramesh been working on" is the question a colleague answers by
memory and a search engine cannot answer at all: the name is in the metadata
(commit author, PR author, ticket assignee), not in the prose. Semantic search
over body text finds passages *about* someone only if they happen to be
discussed. This tool reads the activity records — commits, pull requests,
issues, reviews — and filters by the person, so it answers from what they
actually did.
"""
import re

from strands import tool

ACTIVITY_TYPES = {
    "commits", "pull_requests", "prs", "issues", "pr_reviews", "reviews",
    "releases", "issue", "contributors", "collaborators",
}


def make_people_tool(workspace_id: str, chroma_client, allowed_sources: list[str] | None = None):
    from db.chroma import get_workspace_collection

    @tool
    def who_did_what(person: str, topic: str = "") -> str:
        """
        What a specific person (or bot, e.g. Copilot, dependabot) has done on
        this project — their commits, pull requests, issues, reviews and tickets.

        ALWAYS use this, not search_project_docs, when a question names a person
        and asks about their work: "what did X work on", "what has Priya changed
        recently", "who touched the payments service", "what is Ramesh assigned",
        "what did Copilot do". `person` is a name, handle or email fragment;
        matching is case-insensitive and partial. Optional `topic` narrows it.
        """
        collection = get_workspace_collection(chroma_client, workspace_id)
        if collection.count() == 0:
            return "Nothing is indexed for this project yet."
        if allowed_sources is not None and not allowed_sources:
            return "You have not been given access to any of this project's sources."

        where = {"source_id": {"$in": allowed_sources}} if allowed_sources is not None else None
        # Activity records are a small slice of the index; pull them all and
        # filter in Python — the name we need is inside the text and metadata.
        got = collection.get(include=["documents", "metadatas"], where=where) if where else \
              collection.get(include=["documents", "metadatas"])

        needle = person.strip().lower()
        if len(needle) < 2:
            return "Give me a name, handle or email to look for."
        parts = [p for p in re.split(r"[\s@.]+", needle) if len(p) > 1]
        topic_l = topic.strip().lower()

        hits: list[tuple[str, str, str]] = []
        for doc, meta in zip(got["documents"], got["metadatas"]):
            dt = (meta.get("data_type") or "").lower()
            is_activity = dt in ACTIVITY_TYPES or "commit" in dt or "pull" in dt or "issue" in dt or "review" in dt
            assignee = (meta.get("assignee") or "").lower()
            if not (is_activity or assignee):
                continue
            hay = (doc + " " + assignee).lower()
            if not any(p in hay for p in parts):
                continue
            if topic_l and topic_l not in hay:
                continue
            # Keep only the lines that mention the person, plus a little context.
            lines = [ln.strip() for ln in doc.splitlines() if ln.strip()]
            keep = [ln for ln in lines if any(p in ln.lower() for p in parts)]
            if not keep:
                keep = lines[:3]
            label = meta.get("source_label") or meta.get("repo") or "source"
            hits.append((dt or "activity", label, " · ".join(keep[:6])[:600]))

        if not hits:
            return (f"No activity records mention '{person}'. Either they have not appeared in "
                    "the indexed commits, PRs, issues or tickets, or they go by a different handle.")

        by_type: dict[str, list[str]] = {}
        for dt, label, text in hits[:80]:
            by_type.setdefault(dt, []).append(f"- {label}: {text}")
        out = [f"Activity involving '{person}' across {len(hits)} record(s):"]
        for dt, lines in by_type.items():
            out.append(f"\n## {dt.replace('_', ' ')} ({len(lines)})")
            out.extend(lines[:20])
        out.append("\nName the source in words when it matters. Report dates, days and "
                   "frequencies exactly as these records state them.")
        return "\n".join(out)

    return who_did_what
