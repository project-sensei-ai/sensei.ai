"""
Jira, live.

A Confluence connection is also a Jira connection: same Atlassian site, same
account, same API token, a different path. So the moment an owner connects a
Confluence space, the agent can answer "what is the status of PROJ-412" — and
answer it *now*, from Jira itself, rather than from whatever was indexed last
night. Ticket status is the one kind of fact where a day-old copy is worse
than no answer, so these tools never go through the index.

Read-only by construction: search and get. Creating or transitioning issues
is a write, and writes go through a tool grant the owner switched on.
"""
import base64
from datetime import datetime, timezone

import httpx
from strands import tool

from core import secrets


def _jira_base(confluence_base_url: str) -> str:
    base = confluence_base_url.rstrip("/")
    return base[:-5] if base.endswith("/wiki") else base


def atlassian_credentials(sources: list[dict]) -> list[dict]:
    """Every distinct Atlassian site the workspace has a credential for."""
    seen: dict[str, dict] = {}
    for s in sources:
        if s.get("type") not in ("confluence", "jira"):
            continue
        cfg = s.get("config") or {}
        base = _jira_base(cfg.get("base_url", ""))
        if not base or base in seen:
            continue
        try:
            token = secrets.decrypt_dict(s.get("config_secret")).get("api_token", "")
        except Exception:
            continue
        if token:
            seen[base] = {"base": base, "email": cfg.get("email", ""), "token": token,
                          "label": s.get("label", "Atlassian")}
    return list(seen.values())


def _fmt_issue(i: dict) -> str:
    f = i.get("fields") or {}
    assignee = (f.get("assignee") or {}).get("displayName") or "unassigned"
    status_ = (f.get("status") or {}).get("name") or "?"
    updated = (f.get("updated") or "")[:16].replace("T", " ")
    prio = (f.get("priority") or {}).get("name")
    line = f"{i.get('key')}: {f.get('summary', '')} — {status_}, {assignee}"
    if prio:
        line += f", {prio}"
    if updated:
        line += f" (updated {updated} UTC)"
    return line


def make_jira_tools(sources: list[dict]) -> list:
    creds = atlassian_credentials(sources)
    if not creds:
        return []

    def _client(c: dict) -> httpx.Client:
        auth = base64.b64encode(f"{c['email']}:{c['token']}".encode()).decode()
        return httpx.Client(
            base_url=c["base"],
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            timeout=20,
        )

    @tool
    def jira_search(jql: str, max_results: int = 10) -> str:
        """
        Search Jira issues LIVE with a JQL query and return their current status.

        Use for anything about tickets, sprints, bugs, blockers or who is working
        on what right now — "what is open in PROJ", "what is blocked", "what is
        Priya working on". Examples of JQL: 'project = PROJ AND status != Done
        ORDER BY updated DESC', 'assignee = "Priya" AND sprint in openSprints()'.
        Results are current as of this moment, not the last index.
        """
        out = []
        for c in creds:
            try:
                with _client(c) as h:
                    r = h.get("/rest/api/3/search/jql", params={
                        "jql": jql, "maxResults": max(1, min(int(max_results), 25)),
                        "fields": "summary,status,assignee,updated,priority",
                    })
                    if r.status_code == 410 or r.status_code == 404:
                        r = h.get("/rest/api/3/search", params={
                            "jql": jql, "maxResults": max(1, min(int(max_results), 25)),
                            "fields": "summary,status,assignee,updated,priority",
                        })
                if r.status_code == 400:
                    msg = "; ".join((r.json().get("errorMessages") or [])[:2]) or "bad JQL"
                    out.append(f"[{c['label']}] Jira rejected the query: {msg}")
                    continue
                if r.status_code in (401, 403):
                    out.append(f"[{c['label']}] Jira refused the credential (HTTP {r.status_code}).")
                    continue
                r.raise_for_status()
                issues = r.json().get("issues", [])
                stamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
                if not issues:
                    out.append(f"[{c['label']}] No issues match `{jql}` (checked live at {stamp}).")
                    continue
                out.append(f"[{c['label']}] {len(issues)} issue(s), live at {stamp}:\n" +
                           "\n".join(_fmt_issue(i) for i in issues))
            except Exception as exc:
                out.append(f"[{c['label']}] Jira lookup failed: {exc.__class__.__name__}")
        return "\n\n".join(out)

    @tool
    def jira_issue(key: str) -> str:
        """
        Get one Jira issue LIVE by key (e.g. PROJ-412): status, assignee, priority,
        description and the last three comments. Use when someone names a ticket.
        """
        key = key.strip().upper()
        for c in creds:
            try:
                with _client(c) as h:
                    r = h.get(f"/rest/api/3/issue/{key}", params={
                        "fields": "summary,status,assignee,reporter,updated,created,priority,description,comment,labels",
                    })
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                i = r.json()
                f = i.get("fields") or {}

                def text(adf) -> str:
                    # Atlassian Document Format → plain text, shallowly.
                    if not isinstance(adf, dict):
                        return str(adf or "")
                    parts = []
                    for node in adf.get("content", []):
                        if node.get("type") == "text":
                            parts.append(node.get("text", ""))
                        else:
                            parts.append(text(node))
                    return " ".join(p for p in parts if p).strip()

                lines = [
                    f"{key}: {f.get('summary', '')}",
                    f"Status: {(f.get('status') or {}).get('name')}",
                    f"Assignee: {(f.get('assignee') or {}).get('displayName') or 'unassigned'}",
                    f"Reporter: {(f.get('reporter') or {}).get('displayName')}",
                    f"Priority: {(f.get('priority') or {}).get('name')}",
                    f"Labels: {', '.join(f.get('labels') or []) or '—'}",
                    f"Updated: {(f.get('updated') or '')[:16].replace('T', ' ')} UTC",
                    f"Link: {c['base']}/browse/{key}",
                ]
                desc = text(f.get("description"))
                if desc:
                    lines.append(f"Description: {desc[:900]}")
                comments = ((f.get("comment") or {}).get("comments") or [])[-3:]
                for cm in comments:
                    who = (cm.get("author") or {}).get("displayName", "?")
                    lines.append(f"Comment by {who} ({(cm.get('created') or '')[:10]}): {text(cm.get('body'))[:300]}")
                return "\n".join(lines) + f"\n(live from {c['label']} just now)"
            except Exception as exc:
                return f"Jira lookup for {key} failed: {exc.__class__.__name__}"
        return f"No issue {key} is visible to the connected Atlassian account(s)."

    return [jira_search, jira_issue]


async def fetch_jira(base_url: str, email: str, api_token: str, project_key: str, max_issues: int = 200) -> list[dict]:
    """Index a Jira project's issues so they are searchable by topic. Status
    questions still go live — the index is for *finding* the ticket."""
    base = _jira_base(base_url)
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
    docs: list[dict] = []
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as c:
        start, page = 0, 50
        token = None
        while len(docs) < max_issues:
            params = {"jql": f"project = {project_key} ORDER BY updated DESC", "maxResults": page,
                      "fields": "summary,status,assignee,reporter,updated,created,priority,description,labels,issuetype"}
            if token:
                params["nextPageToken"] = token
            r = await c.get("/rest/api/3/search/jql", params=params)
            if r.status_code in (404, 410):
                params.pop("nextPageToken", None)
                params["startAt"] = start
                r = await c.get("/rest/api/3/search", params=params)
            r.raise_for_status()
            data = r.json()
            issues = data.get("issues", [])
            if not issues:
                break
            for i in issues:
                f = i.get("fields") or {}
                body = [
                    f"# {i['key']}: {f.get('summary', '')}",
                    f"Type: {(f.get('issuetype') or {}).get('name')} · Status: {(f.get('status') or {}).get('name')} · "
                    f"Priority: {(f.get('priority') or {}).get('name')}",
                    f"Assignee: {(f.get('assignee') or {}).get('displayName') or 'unassigned'} · "
                    f"Reporter: {(f.get('reporter') or {}).get('displayName')}",
                    f"Created: {(f.get('created') or '')[:10]} · Updated: {(f.get('updated') or '')[:10]}",
                    f"Labels: {', '.join(f.get('labels') or []) or '—'}",
                ]
                desc = f.get("description")
                if isinstance(desc, dict):
                    def text(adf):
                        parts = []
                        for node in adf.get("content", []):
                            parts.append(node.get("text", "") if node.get("type") == "text" else text(node))
                        return " ".join(p for p in parts if p)
                    desc = text(desc)
                if desc:
                    body.append(f"\n{str(desc)[:3000]}")
                docs.append({
                    "content": "\n".join(body),
                    "metadata": {"source": "jira", "data_type": "issue", "title": f"{i['key']} {f.get('summary', '')}"[:120],
                                 "url": f"{base}/browse/{i['key']}", "key": i["key"],
                                 "status": (f.get("status") or {}).get("name") or "",
                                 "assignee": (f.get("assignee") or {}).get("displayName") or ""},
                })
            token = data.get("nextPageToken")
            start += len(issues)
            if not token and (data.get("isLast", True) or len(issues) < page) and "startAt" not in params:
                break
            if "startAt" in params and (start >= data.get("total", 0)):
                break
    return docs
