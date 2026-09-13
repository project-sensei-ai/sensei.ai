"""Strands @tool functions for fetching content from each source type."""
import io
import os
import re

import httpx
from bs4 import BeautifulSoup
from strands import tool


@tool
async def fetch_github(repo: str, pat: str) -> list[dict]:
    """
    Comprehensively fetch a GitHub repository using a PAT:
    file contents, commits, contributors, collaborators, org members,
    org teams, PRs with reviews, issues, branches, releases, milestones,
    repo metadata and authenticated user profile.
    """
    import base64

    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    target_exts = {".md", ".py", ".ts", ".tsx", ".js", ".txt", ".yaml", ".yml", ".json", ".toml"}
    results: list[dict] = []
    owner = repo.split("/")[0]

    def meta(data_type: str, url: str = "") -> dict:
        return {"source": "github", "repo": repo, "data_type": data_type,
                "url": url or f"https://github.com/{repo}"}

    async with httpx.AsyncClient(headers=headers, timeout=40) as c:

        # ── 0. Authenticated user (PAT owner) ────────────────────────────────
        try:
            r = await c.get("https://api.github.com/user")
            if r.status_code == 200:
                u = r.json()
                lines = [
                    f"# Authenticated GitHub User (PAT Owner)\n",
                    f"- Login: **{u.get('login')}**",
                    f"- Name: {u.get('name', 'N/A')}",
                    f"- Email: {u.get('email', 'N/A')}",
                    f"- Company: {u.get('company', 'N/A')}",
                    f"- Bio: {u.get('bio', 'N/A')}",
                    f"- Public repos: {u.get('public_repos', 0)}",
                    f"- Followers: {u.get('followers', 0)}  Following: {u.get('following', 0)}",
                    f"- Profile: {u.get('html_url', '')}",
                    f"- Created: {(u.get('created_at') or '')[:10]}",
                ]
                results.append({"content": "\n".join(lines), "metadata": meta("authenticated_user", u.get("html_url", ""))})
        except Exception:
            pass

        # ── 1. Repo metadata ──────────────────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}")
            if r.status_code == 200:
                d = r.json()
                owner_info = d.get("owner", {})
                lines = [
                    f"# Repository Metadata: {repo}\n",
                    f"- Full name: {d.get('full_name')}",
                    f"- Owner: **{owner_info.get('login')}** (type: {owner_info.get('type')})",
                    f"- Description: {d.get('description', 'N/A')}",
                    f"- Visibility: {d.get('visibility', 'N/A')}",
                    f"- Default branch: {d.get('default_branch')}",
                    f"- Language: {d.get('language', 'N/A')}",
                    f"- Stars: {d.get('stargazers_count', 0)}  Forks: {d.get('forks_count', 0)}  Watchers: {d.get('watchers_count', 0)}",
                    f"- Open issues: {d.get('open_issues_count', 0)}",
                    f"- Created: {(d.get('created_at') or '')[:10]}  Updated: {(d.get('updated_at') or '')[:10]}",
                    f"- Topics: {', '.join(d.get('topics', [])) or 'none'}",
                    f"- URL: {d.get('html_url')}",
                ]
                results.append({"content": "\n".join(lines), "metadata": meta("repo_metadata", d.get("html_url", ""))})
        except Exception:
            pass

        # ── 2. Collaborators (all access levels — shows owners too) ───────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/collaborators",
                            params={"affiliation": "all", "per_page": 100})
            if r.status_code == 200:
                lines = [f"# Collaborators & Access — {repo}\n",
                         "Lists everyone with any access level (owner/admin/write/read):\n"]
                for person in r.json():
                    login = person.get("login", "")
                    role = person.get("role_name", "")
                    perms = person.get("permissions", {})
                    perm_str = ", ".join(k for k, v in perms.items() if v)
                    lines.append(f"- **{login}** — role: {role} | permissions: {perm_str} | {person.get('html_url', '')}")
                results.append({"content": "\n".join(lines),
                                "metadata": meta("collaborators", f"https://github.com/{repo}/settings/access")})
        except Exception:
            pass

        # ── 3. Org members & teams (if org-owned repo) ────────────────────────
        try:
            org_r = await c.get(f"https://api.github.com/orgs/{owner}")
            if org_r.status_code == 200:
                org = org_r.json()
                lines = [
                    f"# Organization: {owner}\n",
                    f"- Name: {org.get('name', owner)}",
                    f"- Description: {org.get('description', 'N/A')}",
                    f"- Public members: {org.get('public_members_url', '')}",
                    f"- Public repos: {org.get('public_repos', 0)}",
                    f"- URL: {org.get('html_url', '')}",
                ]
                results.append({"content": "\n".join(lines), "metadata": meta("org_metadata", org.get("html_url", ""))})

                # Org members
                members_r = await c.get(f"https://api.github.com/orgs/{owner}/members", params={"per_page": 100})
                if members_r.status_code == 200:
                    lines = [f"# Organization Members — {owner}\n"]
                    for m in members_r.json():
                        lines.append(f"- **{m.get('login')}** ({m.get('type', 'User')}) — {m.get('html_url', '')}")
                    results.append({"content": "\n".join(lines),
                                    "metadata": meta("org_members", f"https://github.com/orgs/{owner}/people")})

                # Org teams
                teams_r = await c.get(f"https://api.github.com/orgs/{owner}/teams", params={"per_page": 50})
                if teams_r.status_code == 200 and teams_r.json():
                    lines = [f"# Teams in {owner}\n"]
                    for t in teams_r.json():
                        slug = t.get("slug", "")
                        # Get team members
                        tm_r = await c.get(f"https://api.github.com/orgs/{owner}/teams/{slug}/members", params={"per_page": 50})
                        members = [m.get("login", "") for m in (tm_r.json() if tm_r.status_code == 200 else [])]
                        lines.append(f"\n## Team: {t.get('name')} (slug: {slug})\n- Members: {', '.join(members) or 'none'}\n- Description: {t.get('description', 'N/A')}")
                    results.append({"content": "\n".join(lines),
                                    "metadata": meta("org_teams", f"https://github.com/orgs/{owner}/teams")})
        except Exception:
            pass

        # ── 4. File contents ──────────────────────────────────────────────────
        try:
            tree_resp = await c.get(f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1")
            if tree_resp.status_code == 200:
                tree = tree_resp.json().get("tree", [])
                files = [item for item in tree if item.get("type") == "blob"
                         and os.path.splitext(item["path"])[1].lower() in target_exts]
                for item in files[:200]:
                    try:
                        blob_resp = await c.get(f"https://api.github.com/repos/{repo}/contents/{item['path']}")
                        if blob_resp.status_code == 200:
                            data = blob_resp.json()
                            content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
                            results.append({"content": content,
                                            "metadata": {**meta("file", data.get("html_url", "")), "path": item["path"]}})
                    except Exception:
                        continue
        except Exception:
            pass

        # ── 5. Commit history (last 100) — with per-author summary ────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/commits", params={"per_page": 100})
            if r.status_code == 200:
                commits = r.json()
                author_commits: dict[str, list[str]] = {}
                lines = [f"# Commit History — {repo}\n"]
                for commit in commits:
                    sha = (commit.get("sha") or "")[:8]
                    msg = ((commit.get("commit") or {}).get("message") or "").split("\n")[0][:120]
                    author_name = ((commit.get("commit") or {}).get("author") or {}).get("name", "unknown")
                    author_login = (commit.get("author") or {}).get("login", author_name)
                    date = ((commit.get("commit") or {}).get("author") or {}).get("date", "")[:10]
                    html_url = commit.get("html_url", "")
                    lines.append(f"- [{sha}] {date} **{author_login}**: {msg}  {html_url}")
                    author_commits.setdefault(author_login, []).append(msg)
                results.append({"content": "\n".join(lines),
                                "metadata": meta("commits", f"https://github.com/{repo}/commits")})

                # Per-author commit summary
                summary_lines = [f"# Per-Author Commit Summary — {repo}\n"]
                for author, msgs in sorted(author_commits.items(), key=lambda x: -len(x[1])):
                    summary_lines.append(f"\n## {author} ({len(msgs)} commits)")
                    for m in msgs[:20]:
                        summary_lines.append(f"  - {m}")
                    if len(msgs) > 20:
                        summary_lines.append(f"  … and {len(msgs)-20} more")
                results.append({"content": "\n".join(summary_lines),
                                "metadata": meta("commits_by_author", f"https://github.com/{repo}/commits")})
        except Exception:
            pass

        # ── 6. Contributors (commit count) ────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/contributors", params={"per_page": 100})
            if r.status_code == 200:
                lines = [f"# Contributors (by commit count) — {repo}\n"]
                for person in r.json():
                    lines.append(f"- **{person.get('login')}** — {person.get('contributions', 0)} commits — {person.get('html_url', '')}")
                results.append({"content": "\n".join(lines),
                                "metadata": meta("contributors", f"https://github.com/{repo}/graphs/contributors")})
        except Exception:
            pass

        # ── 7. Pull requests (open + closed) with reviews ─────────────────────
        try:
            for state in ("open", "closed"):
                r = await c.get(f"https://api.github.com/repos/{repo}/pulls",
                                params={"state": state, "per_page": 30, "sort": "updated", "direction": "desc"})
                if r.status_code == 200 and r.json():
                    lines = [f"# Pull Requests ({state}) — {repo}\n"]
                    for pr in r.json():
                        num = pr.get("number")
                        title = pr.get("title", "")
                        author = (pr.get("user") or {}).get("login", "unknown")
                        created = (pr.get("created_at") or "")[:10]
                        merged = (pr.get("merged_at") or "")[:10] or ("not merged" if state == "closed" else "open")
                        body = (pr.get("body") or "")[:400]
                        labels = [lb["name"] for lb in (pr.get("labels") or [])]
                        reviewers = [(r2.get("login", "")) for r2 in (pr.get("requested_reviewers") or [])]

                        # Fetch reviews
                        rev_r = await c.get(f"https://api.github.com/repos/{repo}/pulls/{num}/reviews")
                        reviews = []
                        if rev_r.status_code == 200:
                            for rv in rev_r.json():
                                rv_author = (rv.get("user") or {}).get("login", "?")
                                rv_state = rv.get("state", "")
                                reviews.append(f"{rv_author} ({rv_state})")

                        lines.append(
                            f"\n## PR #{num}: {title}\n"
                            f"- Author: **{author}**  Created: {created}  Status: {merged}\n"
                            f"- Labels: {', '.join(labels) or 'none'}\n"
                            f"- Requested reviewers: {', '.join(reviewers) or 'none'}\n"
                            f"- Reviews: {', '.join(reviews) or 'none'}\n"
                            f"- Description: {body}"
                        )
                    results.append({"content": "\n".join(lines),
                                    "metadata": meta(f"pull_requests_{state}", f"https://github.com/{repo}/pulls")})
        except Exception:
            pass

        # ── 8. Issues (open + closed) ─────────────────────────────────────────
        try:
            for state in ("open", "closed"):
                r = await c.get(f"https://api.github.com/repos/{repo}/issues",
                                params={"state": state, "per_page": 30, "sort": "updated", "direction": "desc"})
                if r.status_code == 200:
                    issues = [i for i in r.json() if "pull_request" not in i]
                    if not issues:
                        continue
                    lines = [f"# Issues ({state}) — {repo}\n"]
                    for issue in issues:
                        num = issue.get("number")
                        title = issue.get("title", "")
                        author = (issue.get("user") or {}).get("login", "unknown")
                        created = (issue.get("created_at") or "")[:10]
                        closed = (issue.get("closed_at") or "")[:10] or "open"
                        body = (issue.get("body") or "")[:400]
                        labels = [lb["name"] for lb in (issue.get("labels") or [])]
                        assignees = [(a or {}).get("login", "") for a in (issue.get("assignees") or [])]
                        lines.append(
                            f"\n## Issue #{num}: {title}\n"
                            f"- Author: **{author}**  Created: {created}  Closed: {closed}\n"
                            f"- Labels: {', '.join(labels) or 'none'}  Assignees: {', '.join(assignees) or 'none'}\n"
                            f"- Description: {body}"
                        )
                    results.append({"content": "\n".join(lines),
                                    "metadata": meta(f"issues_{state}", f"https://github.com/{repo}/issues")})
        except Exception:
            pass

        # ── 9. Branches ───────────────────────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/branches", params={"per_page": 50})
            if r.status_code == 200 and r.json():
                lines = [f"# Branches — {repo}\n"]
                for b in r.json():
                    name = b.get("name", "")
                    sha = (b.get("commit") or {}).get("sha", "")[:8]
                    protected = "🔒 protected" if b.get("protected") else "unprotected"
                    lines.append(f"- **{name}** [{sha}] — {protected}")
                results.append({"content": "\n".join(lines),
                                "metadata": meta("branches", f"https://github.com/{repo}/branches")})
        except Exception:
            pass

        # ── 10. Releases & tags ───────────────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/releases", params={"per_page": 20})
            if r.status_code == 200 and r.json():
                lines = [f"# Releases — {repo}\n"]
                for rel in r.json():
                    tag = rel.get("tag_name", "")
                    name = rel.get("name", "")
                    author = (rel.get("author") or {}).get("login", "unknown")
                    published = (rel.get("published_at") or "")[:10]
                    body = (rel.get("body") or "")[:400]
                    lines.append(f"\n## {tag}: {name}\n- Author: {author}  Published: {published}\n- Notes: {body}")
                results.append({"content": "\n".join(lines),
                                "metadata": meta("releases", f"https://github.com/{repo}/releases")})
        except Exception:
            pass

        # ── 11. Milestones ────────────────────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/milestones", params={"state": "all", "per_page": 20})
            if r.status_code == 200 and r.json():
                lines = [f"# Milestones — {repo}\n"]
                for ms in r.json():
                    lines.append(
                        f"- **{ms.get('title')}** ({ms.get('state')}) — "
                        f"open: {ms.get('open_issues', 0)}, closed: {ms.get('closed_issues', 0)} — "
                        f"due: {(ms.get('due_on') or 'none')[:10]}"
                    )
                results.append({"content": "\n".join(lines),
                                "metadata": meta("milestones", f"https://github.com/{repo}/milestones")})
        except Exception:
            pass

        # ── 12. GitHub Actions workflows ──────────────────────────────────────
        try:
            r = await c.get(f"https://api.github.com/repos/{repo}/actions/workflows")
            if r.status_code == 200:
                workflows = r.json().get("workflows", [])
                if workflows:
                    lines = [f"# CI/CD Workflows — {repo}\n"]
                    for wf in workflows:
                        lines.append(f"- **{wf.get('name')}** ({wf.get('state')}) — {wf.get('path', '')} — {wf.get('html_url', '')}")
                    results.append({"content": "\n".join(lines),
                                    "metadata": meta("workflows", f"https://github.com/{repo}/actions")})
        except Exception:
            pass

    return results


@tool
async def fetch_urls(urls: list[str]) -> list[dict]:
    """Crawl public URLs and extract readable text content."""
    results = []
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers={"User-Agent": "Sensei/1.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                title = soup.title.string.strip() if soup.title else url
                results.append({
                    "content": text,
                    "metadata": {"source": "url", "url": url, "title": title},
                })
            except Exception as exc:
                results.append({
                    "content": "",
                    "metadata": {"source": "url", "url": url, "error": str(exc)},
                })
    return results


@tool
def parse_file(file_path: str, filename: str) -> list[dict]:
    """Parse an uploaded file (PDF, DOCX, MD, TXT) into text chunks."""
    ext = os.path.splitext(filename)[1].lower()
    results = []

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                results.append({
                    "content": text,
                    "metadata": {"source": "file", "filename": filename, "page": i + 1},
                })

    elif ext == ".docx":
        from docx import Document
        doc = Document(file_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        results.append({"content": text, "metadata": {"source": "file", "filename": filename, "page": 1}})

    else:  # .md, .txt
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        results.append({"content": text, "metadata": {"source": "file", "filename": filename, "page": 1}})

    return results


@tool
async def fetch_confluence(base_url: str, email: str, api_token: str, space_key: str) -> list[dict]:
    """Fetch pages from a Confluence space using basic auth."""
    import base64
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    results = []

    base = base_url.rstrip("/")

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        pages: list[dict] = []
        start = 0
        # One page of 50 silently truncated bigger spaces.
        while len(pages) < 300:
            resp = await client.get(f"{base}/rest/api/content", params={
                "spaceKey": space_key, "type": "page", "limit": 50,
                "start": start, "expand": "body.storage",
            })
            resp.raise_for_status()
            batch = resp.json().get("results", [])
            pages.extend(batch)
            if len(batch) < 50:
                break
            start += 50

        for page in pages:
            html = page.get("body", {}).get("storage", {}).get("value", "")
            text = BeautifulSoup(html, "html.parser").get_text(separator="\n", strip=True)
            if text:
                results.append({
                    "content": text,
                    "metadata": {
                        "source": "confluence",
                        "title": page.get("title", ""),
                        "page_id": page.get("id", ""),
                        "space_key": space_key,
                        # webui is the link a person can actually open; the
                        # hand-built /pages/{id} form 404s.
                        "url": (page.get("_links", {}) or {}).get("webui")
                        and f"{base}{page['_links']['webui']}"
                        or f"{base}/spaces/{space_key}/pages/{page.get('id', '')}",
                    },
                })
    return results


# Jira issue fields arrive as ADF (Atlassian Document Format) JSON — a tree of
# text/mark/block nodes — which is not searchable text on its own. Flatten only
# the nodes that carry words; block nodes end their snippet with a newline so
# consecutive paragraphs survive as separate lines.
_BLOCK_NODES = {
    "paragraph", "heading", "listItem", "codeBlock", "blockquote", "rule",
    "panel", "bulletList", "orderedList", "doc", "tableRow", "tableHeader",
    "tableCell",
}


def _adf_text(node) -> str:
    if isinstance(node, list):
        return "".join(_adf_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    kind = node.get("type")
    if kind == "text":
        return node.get("text", "")
    if kind == "hardBreak":
        return "\n"
    if kind in ("mention", "emoji", "status", "date"):
        # Jira puts display text on the node itself, not in a nested text node.
        return node.get("text") or (node.get("attrs") or {}).get("text") or ""
    if kind == "rule":
        return "\n"
    body = _adf_text(node.get("content"))
    if kind in _BLOCK_NODES:
        return body.rstrip("\n") + "\n"
    return body


async def _issues_via_board(client, base: str, project_key: str, fields: str) -> list[dict]:
    """
    Confluence boards read issues without the JQL search index. Some brand-new
    cloud sites serve 410 Gone on /rest/api/3/search until the index is built;
    the agile board endpoint is the one other source that still lists issues.
    """
    boards = await client.get(
        f"{base}/rest/agile/1.0/board",
        params={"projectKeyOrId": project_key},
    )
    boards.raise_for_status()

    issues: list[dict] = []
    for board in boards.json().get("values", []):
        start_at = 0
        while len(issues) < 300:
            resp = await client.get(
                f"{base}/rest/agile/1.0/board/{board['id']}/issue",
                params={"fields": fields, "maxResults": 50, "startAt": start_at},
            )
            resp.raise_for_status()
            payload = resp.json()
            batch = payload.get("issues", [])
            issues.extend(batch)
            if not batch or start_at + len(batch) >= (payload.get("total") or len(batch)):
                break
            start_at += len(batch)

    # An issue can sit on several boards; keep the first copy per key.
    seen: set[str] = set()
    deduped: list[dict] = []
    for issue in issues:
        if issue.get("key", "") not in seen:
            seen.add(issue.get("key", ""))
            deduped.append(issue)
    return deduped


async def fetch_jira(base_url: str, email: str, api_token: str, project_key: str) -> list[dict]:
    """
    Fetch issues from a Jira Cloud project. Same Atlassian identity as
    Confluence, pointed at /rest/api/3 instead.

    Each issue becomes one document (summary, status, description); comments
    become their own documents so "what were people saying on PROJ-42" is
    searchable independently of the ticket body.
    """
    import base64
    import re as _re

    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    base = base_url.rstrip("/")
    key = project_key.strip().upper()
    fields = "summary,description,status,priority,labels,assignee,comment,created,updated"

    issues: list[dict] = []
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        try:
            start_at = 0
            # One page of 50 silently truncated bigger projects, same cap as Confluence.
            while len(issues) < 300:
                resp = await client.get(f"{base}/rest/api/3/search", params={
                    "jql": f"project = {key}",
                    "fields": fields,
                    "maxResults": 50,
                    "startAt": start_at,
                })
                resp.raise_for_status()
                payload = resp.json()
                batch = payload.get("issues", [])
                issues.extend(batch)
                if not batch or start_at + len(batch) >= (payload.get("total") or len(batch)):
                    break
                start_at += len(batch)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (410, 404):
                raise
            # New sites can serve 410 Gone on /search until the index builds;
            # the agile board API lists issues without it.
            issues = await _issues_via_board(client, base, key, fields)

    results: list[dict] = []
    for issue in issues:
        ikey = issue.get("key", "")
        f = issue.get("fields") or {}
        summary = f.get("summary", "")
        status = (f.get("status") or {}).get("name", "")
        priority = (f.get("priority") or {}).get("name", "")
        assignee = (f.get("assignee") or {}).get("displayName", "")
        labels = ", ".join(f.get("labels") or [])
        permalink = f"{base}/browse/{ikey}"
        if summary:
            title = f"{ikey}: {summary}"
        else:
            title = ikey

        parts = [title, f"Status: {status}"]
        if priority:
            parts.append(f"Priority: {priority}")
        if assignee:
            parts.append(f"Assignee: {assignee}")
        if labels:
            parts.append(f"Labels: {labels}")
        desc = _re.sub(r"\n{3,}", "\n\n", _adf_text(f.get("description"))).strip()
        if desc:
            parts.append(f"Description:\n{desc}")

        results.append({
            "content": "\n".join(parts),
            "metadata": {
                "source": "jira",
                "title": title,
                "issue_key": ikey,
                "status": status,
                "data_type": "issue",
                "url": permalink,
            },
        })

        for comment in (f.get("comment") or {}).get("comments", []):
            body = _re.sub(r"\n{3,}", "\n\n", _adf_text(comment.get("body"))).strip()
            if not body:
                continue
            author = (comment.get("author") or {}).get("displayName", "")
            results.append({
                "content": f"{author}: {body}" if author else body,
                "metadata": {
                    "source": "jira",
                    "title": f"{ikey} comment",
                    "issue_key": ikey,
                    "status": status,
                    "data_type": "comment",
                    "url": permalink,
                },
            })

    return results


_SLACK_MENTION = re.compile(r"<@([UW][A-Z0-9]+)>")
_SLACK_LINK = re.compile(r"<([^|>]+)\|([^>]+)>")


def _strip_mrkdwn(text: str, users: dict[str, str]) -> str:
    """
    Collapse Slack mrkdwn back into plain, searchable text:
        <@U123|Name>   ->  Name            (label already on the link)
        <@U123>        ->  resolved name   (or the raw id when unknown)
        <url|label>    ->  label           (link UI text, not the URL)
        <url>          ->  url
    Bold / italics / code markers are left alone — they survive embedding fine.
    """
    if not text:
        return text
    text = re.sub(r"<@([UW][A-Z0-9]+)\|([^>]+)>", r"\2", text)
    text = _SLACK_MENTION.sub(lambda m: users.get(m.group(1), m.group(1)), text)
    text = _SLACK_LINK.sub(r"\2", text)
    text = re.sub(r"<[^>]+>", lambda m: m.group(0)[1:-1], text)
    return text


async def fetch_slack(bot_token: str, channel_id: str, channel_name: str, team_domain: str) -> list[dict]:
    """
    Fetch recent messages and threaded replies from one Slack channel.

    Names are resolved once per run (users.list) so `@U123` becomes a display
    name; messages and replies each become their own document, the way Jira
    comments do. Permalinks are the universal Slack form
    https://{team_domain}.slack.com/archives/{channel}/{ts}.
    """
    headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"}
    base = "https://slack.com/api"

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        users: dict[str, str] = {}
        cursor = None
        while True:
            params: dict = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(f"{base}/users.list", params=params)
            payload = resp.json()
            if not payload.get("ok"):
                raise RuntimeError(f"Slack users.list failed: {payload.get('error')}")
            for u in payload.get("members", []):
                if u.get("deleted"):
                    continue
                profile = u.get("profile") or {}
                users[u["id"]] = profile.get("display_name") or u.get("name") or u["id"]
            cursor = (payload.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break

        results: list[dict] = []
        cursor = None
        while len(results) < 300:
            params = {"channel": channel_id, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(f"{base}/conversations.history", params=params)
            payload = resp.json()
            if not payload.get("ok"):
                raise RuntimeError(f"Slack conversations.history failed: {payload.get('error')}")
            messages = payload.get("messages", [])

            for msg in messages:
                if msg.get("thread_ts"):
                    continue  # replies live under their parent, fetched once
                results.append(_slack_message_doc(msg, channel_name, team_domain, channel_id, users, "message"))
                if msg.get("reply_count"):
                    rresp = await client.get(
                        f"{base}/conversations.replies",
                        params={"channel": channel_id, "ts": msg["ts"]},
                    )
                    rpayload = rresp.json()
                    if not rpayload.get("ok"):
                        continue  # partial data beats a failed run
                    for reply in rpayload.get("messages", []):
                        if reply["ts"] == msg.get("ts"):
                            continue  # the parent is already indexed
                        results.append(_slack_message_doc(reply, channel_name, team_domain, channel_id, users, "reply"))

            cursor = (payload.get("response_metadata") or {}).get("next_cursor")
            if not messages or not cursor:
                break

    return results[:300]


def _slack_message_doc(msg: dict, channel_name: str, team_domain: str, channel_id: str,
                       users: dict[str, str], data_type: str) -> dict:
    from datetime import datetime as _dt

    ts = msg.get("ts", "")
    author = msg.get("user", "")
    author = users.get(author, author) or msg.get("username", "bot")
    text = _strip_mrkdwn(msg.get("text", ""), users)
    permalink = f"https://{team_domain}.slack.com/archives/{channel_id}/{ts}"

    parts = []
    if text:
        parts.append(text)
    ts_human = _dt.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M UTC") if ts else ""
    if ts_human:
        parts.append(ts_human)

    return {
        "content": "\n".join(parts),
        "metadata": {
            "source": "slack",
            "title": f"{author} in #{channel_name}",
            "author": author,
            "channel": channel_name,
            "channel_id": channel_id,
            "data_type": data_type,
            "ts": ts,
            "url": permalink,
        },
    }


def make_inventory_tool(workspace_id: str, chroma_client, allowed_sources: list[str] | None = None):
    """
    Factory for `list_project_knowledge`.

    Semantic search answers "what does the architecture say?". It is the wrong
    instrument for "is there a doc about architecture?" — that is a question
    about the shelf, not the books, and similarity over body text will happily
    return five passages from whatever else discusses the topic. This tool reads
    the index's own catalogue instead.
    """
    from db.chroma import get_workspace_collection

    @tool
    def list_project_knowledge() -> str:
        """
        List every source indexed for this project and the documents inside each.

        Call this for questions about WHAT EXISTS rather than what something says:
        "is there a doc about X", "what do you know about this project",
        "which sources do you have", "where would I find Y".
        """
        collection = get_workspace_collection(chroma_client, workspace_id)
        if collection.count() == 0:
            return "Nothing is indexed for this project yet."
        if allowed_sources is not None and not allowed_sources:
            return "You have not been given access to any of this project's sources."

        got = (
            collection.get(include=["metadatas"], where={"source_id": {"$in": allowed_sources}})
            if allowed_sources is not None
            else collection.get(include=["metadatas"])
        )
        by_source: dict[str, dict[str, int]] = {}
        for meta in got["metadatas"]:
            label = meta.get("source_label") or "Unknown source"
            item = (
                meta.get("title")
                or meta.get("path")
                or (meta.get("data_type") or "").replace("_", " ")
                or "content"
            )
            by_source.setdefault(label, {})
            by_source[label][item] = by_source[label].get(item, 0) + 1

        lines = [f"{len(by_source)} source(s) indexed for this project:\n"]
        for label, items in sorted(by_source.items()):
            total = sum(items.values())
            lines.append(f"\n## {label}  ({total} chunks)")
            for item, n in sorted(items.items(), key=lambda kv: -kv[1])[:30]:
                lines.append(f"- {item}")
            if len(items) > 30:
                lines.append(f"- …and {len(items) - 30} more")

        lines.append(
            "\nThese are the only things indexed. Anything not listed here has not "
            "been shared with the agent."
        )
        return "\n".join(lines)

    return list_project_knowledge


def make_search_tool(
    workspace_id: str,
    chroma_client,
    *,
    n_results: int = 8,
    passage_chars: int = 800,
    budget: int = 3,
    allowed_sources: list[str] | None = None,
):
    """
    Factory that returns a (search_tool, captured_results) pair.
    The search_tool is a Strands @tool that queries the workspace ChromaDB collection.
    captured_results accumulates citation data from each tool call for the caller to read.
    """
    from db.chroma import get_workspace_collection

    captured: list[dict] = []
    # Dedup lives in the factory closure, not the call: the agent loop calls this
    # tool several times per question, and per-call dedup let the same document
    # come back once per call.
    seen_labels: set[str] = set()
    seen_chunks: set[str] = set()
    calls = {"n": 0}

    # Left unbounded, the model will re-search a half-dozen times with reworded
    # queries, re-sending the same passages each time. That burns the context
    # window, trips provider rate limits, and each throttled retry sleeps with
    # exponential backoff — a question can hang for minutes.
    #
    # The three knobs are tuned per caller. Interactive chat can afford eight
    # 800-character passages; a background agent in a three-node graph cannot —
    # every passage it pulls is re-sent on each subsequent turn, and the totals
    # compound into daily token caps.
    MAX_SEARCHES = budget

    @tool
    def search_project_docs(query: str) -> str:
        """
        Search the indexed project knowledge base for content relevant to the query.
        Returns the most relevant passages from indexed sources (GitHub repos, files, URLs, Confluence).
        Call this for ANY question about the project, codebase, team, architecture, commits, or documentation.
        Do NOT call this for general knowledge questions unrelated to the project.
        """
        calls["n"] += 1
        if calls["n"] > MAX_SEARCHES:
            return (
                f"Search budget reached ({MAX_SEARCHES} searches). Do not search again. "
                "Answer the user now from the passages you have already been given. "
                "If they do not cover the question, say plainly that the workspace "
                "does not contain that information."
            )

        collection = get_workspace_collection(chroma_client, workspace_id)
        count = collection.count()
        if count == 0:
            return "No sources have been indexed yet. The user should add and ingest sources first."

        # Chunks are small enough to fit the embedder's window, so ask for more of
        # them — a section's answer is often split across two neighbouring chunks.
        n = min(n_results, count)
        # Filtering happens in the query, not after it. Retrieving everything and
        # then discarding what the asker may not see would mean a restricted
        # person gets fewer results rather than different ones — and would leak
        # the existence of the rest through the gaps.
        query_args = {
            "query_texts": [query],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if allowed_sources is not None:
            if not allowed_sources:
                return (
                    "You have not been given access to any of this project's sources. "
                    "Ask the project owner."
                )
            query_args["where"] = {"source_id": {"$in": allowed_sources}}

        results = collection.query(**query_args)

        ids = results["ids"][0]
        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        if not docs:
            return "No relevant content found for this query."

        # Only send passages the model has not already seen this turn. Re-sending
        # them wastes the context window and makes the model think it is making
        # progress when it is not.
        fresh = [(i, d, m, dist) for i, d, m, dist in zip(ids, docs, metadatas, distances)
                 if i not in seen_chunks]
        if not fresh:
            return (
                "This search returned only passages you have already seen. "
                "No new information is available for this query — answer from what you have."
            )

        passages: list[str] = []
        for i, (chunk_id, doc, meta, dist) in enumerate(fresh):
            seen_chunks.add(chunk_id)
            label = (
                meta.get("source_label") or meta.get("repo") or
                meta.get("title") or meta.get("url") or "Unknown source"
            )
            score = round(1 - float(dist), 3)
            passages.append(f"[{i + 1}] Source: {label} (relevance {score:.0%})\n{doc[:passage_chars]}")
            if label not in seen_labels:
                seen_labels.add(label)
                captured.append({
                    "index": len(captured) + 1,
                    "source_label": label,
                    "excerpt": doc[:250] + ("…" if len(doc) > 250 else ""),
                    "score": score,
                })

        return "\n\n---\n\n".join(passages)

    return search_project_docs, captured


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Bedrock Knowledge Base for uploaded documents (PDFs, text files, Word docs).
    Use this when the question is about uploaded file content rather than GitHub repos or URLs.
    Call alongside search_project_docs when the answer might be in uploaded documents.
    """
    from core.config import settings
    if not settings.BEDROCK_KB_ID:
        return "Bedrock Knowledge Base is not configured for this deployment."
    try:
        import boto3
        client = boto3.client("bedrock-agent-runtime", region_name=settings.AWS_REGION)
        resp = client.retrieve(
            knowledgeBaseId=settings.BEDROCK_KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
        )
    except Exception as exc:
        return f"Knowledge base search failed: {exc}"

    results = resp.get("retrievalResults", [])
    if not results:
        return "No relevant content found in the knowledge base."

    passages: list[str] = []
    for i, r in enumerate(results):
        content = r.get("content", {}).get("text", "")
        score = round(float(r.get("score", 0)), 3)
        uri = r.get("location", {}).get("s3Location", {}).get("uri", f"document-{i + 1}")
        label = uri.split("/")[-1] if "/" in uri else uri
        passages.append(f"[{i + 1}] Source: {label} (score {score:.2f})\n{content[:500]}")

    return "\n\n---\n\n".join(passages)
