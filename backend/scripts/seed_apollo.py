"""
A second project, owned by someone else, with its own team.

Sensei is judged on whether two owners can each onboard the agent into their
own project and hand it to their own people. This creates the Apollo Delivery
project owned by Maya, connects its repo, its Confluence space and a GitHub
tool grant with writes allowed, and adds Priya and Ravi as members — through
the same API a person would use, so anything that breaks here breaks for them.

    python scripts/seed_apollo.py [base_url]

Idempotent: re-running logs in instead of registering, and skips sources that
already exist.
"""
import asyncio
import subprocess
import sys

import httpx

sys.path.insert(0, ".")
from core import secrets  # noqa: E402
from core.config import settings  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PASSWORD = "Apollo-Demo-2026!"
OWNER = {"email": "maya@apollo.demo", "name": "Maya Iyer"}
MEMBERS = [{"email": "priya@apollo.demo", "name": "Priya Nair"},
           {"email": "ravi@apollo.demo", "name": "Ravi Menon"}]
REPO = "bsaisuryacharan/apollo-delivery-service"
SPACE = "SD"
JUDGE_WS = "a843fce734a34b99905b3dd6f4ece609"     # where the Confluence credential already lives


async def atlassian_credential() -> dict:
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(settings.MONGO_DB)[settings.MONGO_DB_NAME]
    src = await db.sources.find_one({"workspace_id": JUDGE_WS, "type": "confluence"})
    cfg, sec = src["config"], secrets.decrypt_dict(src.get("config_secret"))
    return {"base_url": cfg["base_url"], "email": cfg["email"], "api_token": sec["api_token"]}


async def sign_in(c: httpx.AsyncClient, email: str, name: str, role: str = "owner") -> None:
    r = await c.post("/api/auth/register", json={"email": email, "password": PASSWORD, "name": name, "role": role})
    if r.status_code == 201:
        print("registered", email)
        return
    r = await c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    print("logged in", email)


async def main() -> None:
    gh_token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    atl = await atlassian_credential()

    async with httpx.AsyncClient(base_url=BASE, timeout=120) as c:
        await sign_in(c, OWNER["email"], OWNER["name"])

        r = await c.get("/api/workspaces/me")
        if r.status_code == 404:
            r = await c.post("/api/workspaces", json={
                "name": "Apollo Delivery",
                "description": "Last-mile dispatch platform for Northwind, Fabrikam and Contoso",
            })
            r.raise_for_status()
            print("workspace created")
        ws = r.json()["workspace"]
        print("workspace", ws["id"], ws["name"])

        have = {(s["type"], s["label"]) for s in (await c.get("/api/sources")).json()["sources"]}

        if ("github", REPO) not in have:
            r = await c.post("/api/sources", json={"type": "github", "pat": gh_token, "repo": REPO, "label": REPO})
            r.raise_for_status()
            sid = r.json()["source"]["id"]
            await c.post(f"/api/ingest/{sid}")
            print("github source", sid)

        if ("confluence", f"Confluence: {SPACE}") not in have:
            r = await c.post("/api/sources", json={"type": "confluence", **atl, "space_key": SPACE,
                                                   "label": f"Confluence: {SPACE}"})
            r.raise_for_status()
            sid = r.json()["source"]["id"]
            await c.post(f"/api/ingest/{sid}")
            print("confluence source", sid)

        tools = (await c.get("/api/tools")).json()["grants"]
        if not any(t["name"] == "GitHub" for t in tools):
            r = await c.post("/api/tools", json={
                "name": "GitHub", "kind": "mcp_http", "url": "https://api.githubcopilot.com/mcp/",
                "authorization": f"Bearer {gh_token}", "allow_write": True,
            })
            r.raise_for_status()
            g = r.json()["grant"]
            print("tool grant", g["name"], g["read_count"], "read", g["write_count"], "write, writes allowed")

        members = (await c.get("/api/workspaces/members")).json()["members"]
        known = {m.get("email") for m in members}
        todo = [m for m in MEMBERS if m["email"] not in known]
        if todo:
            r = await c.post("/api/workspaces/members", json={"emails": [m["email"] for m in todo]})
            r.raise_for_status()
            for res in r.json()["results"]:
                print("added", res["email"], res["status"], res.get("detail", ""))

        # Each member accepts their own single-use invite and sets a password —
        # the same path a real teammate takes from the email.
        members = (await c.get("/api/workspaces/members")).json()["members"]
        for m in members:
            url = m.get("invite_url")
            if not url or m.get("status") == "active":
                continue
            token = url.split("token=")[-1]
            name = next((x["name"] for x in MEMBERS if x["email"] == m["email"]), m["email"])
            async with httpx.AsyncClient(base_url=BASE, timeout=60) as member_client:
                r = await member_client.post("/api/auth/accept-invite",
                                             json={"token": token, "password": PASSWORD, "name": name})
                print("accepted", m["email"], r.status_code, r.text[:120] if r.status_code >= 300 else "")

        # Wait for the sources to land so the briefs the members get are real.
        for _ in range(60):
            srcs = (await c.get("/api/sources")).json()["sources"]
            if all(s["status"] in ("ready", "error") for s in srcs):
                break
            await asyncio.sleep(5)
        for s in (await c.get("/api/sources")).json()["sources"]:
            print(f"  {s['type']:10} {s['label']:40} {s['status']:8} {s['stats'].get('chunks_count', 0)} chunks")


if __name__ == "__main__":
    asyncio.run(main())
