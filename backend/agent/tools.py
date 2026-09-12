"""Strands @tool functions for fetching content from each source type."""
import io
import os

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

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        params = {"spaceKey": space_key, "type": "page", "limit": 50, "expand": "body.storage"}
        resp = await client.get(f"{base_url.rstrip('/')}/rest/api/content", params=params)
        resp.raise_for_status()
        pages = resp.json().get("results", [])

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
                        "url": f"{base_url}/pages/{page.get('id', '')}",
                    },
                })
    return results


def make_search_tool(workspace_id: str, chroma_client):
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

    @tool
    def search_project_docs(query: str) -> str:
        """
        Search the indexed project knowledge base for content relevant to the query.
        Returns the most relevant passages from indexed sources (GitHub repos, files, URLs, Confluence).
        Call this for ANY question about the project, codebase, team, architecture, commits, or documentation.
        Do NOT call this for general knowledge questions unrelated to the project.
        """
        collection = get_workspace_collection(chroma_client, workspace_id)
        count = collection.count()
        if count == 0:
            return "No sources have been indexed yet. The user should add and ingest sources first."

        n = min(5, count)
        results = collection.query(
            query_texts=[query],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        if not docs:
            return "No relevant content found for this query."

        passages: list[str] = []
        for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances)):
            label = (
                meta.get("source_label") or meta.get("repo") or
                meta.get("title") or meta.get("url") or "Unknown source"
            )
            score = round(1 - float(dist), 3)
            passages.append(f"[{i + 1}] Source: {label} (relevance {score:.0%})\n{doc[:500]}")
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
