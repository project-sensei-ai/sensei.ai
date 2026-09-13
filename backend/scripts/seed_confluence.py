"""
Seed a realistic project into a Confluence space, so the demo has something a
colleague would actually be asked about: an architecture with specific values,
a runbook, an on-call rota, decisions with dates, and a team directory with
owners. The specifics are the point — "what region do we deploy to" only has
a demonstrable answer if a page says eu-west-1.

Usage (uses the credential already stored on a Confluence source):
    python scripts/seed_confluence.py <workspace_id> <SPACE_KEY>
"""
import asyncio
import base64
import sys

import httpx

sys.path.insert(0, ".")
from core import secrets  # noqa: E402
from core.config import settings  # noqa: E402

PAGES = {
    "Apollo Delivery — Project overview": """
<h2>What Apollo is</h2>
<p>Apollo Delivery is the last-mile dispatch platform used by three retail clients (Northwind Grocers, Fabrikam Pharmacy, Contoso Home). It assigns orders to couriers, tracks them, and reconciles proof-of-delivery with the client's order system. It has been in production since March 2025 and handles roughly 40,000 deliveries a day at peak.</p>
<h2>Who it is for</h2>
<ul><li>Dispatch operators at the clients (web console)</li><li>Couriers (Android app, built by the mobile team)</li><li>Client integration teams (REST API + webhooks)</li></ul>
<h2>Team</h2>
<p>Product owner: <strong>Maya Iyer</strong>. Tech lead: <strong>Ravi Menon</strong>. Backend: Priya Nair, Daniel Okafor. Mobile: Chen Wei. QA: Fatima Zahra. See the Team directory page for ownership by area.</p>
<h2>Key links</h2>
<ul><li>Repo: github.com/bsaisuryacharan/apollo-delivery-service</li><li>Runbook: Apollo — Deployment runbook</li><li>On-call: Apollo — On-call and escalation</li></ul>
""",
    "Apollo — Architecture": """
<h2>Services</h2>
<table><tbody>
<tr><th>Service</th><th>Language</th><th>Owner</th><th>Purpose</th></tr>
<tr><td>dispatch-api</td><td>Python 3.12 / FastAPI</td><td>Priya Nair</td><td>Order intake, courier assignment, public REST API</td></tr>
<tr><td>routing-worker</td><td>Go 1.22</td><td>Daniel Okafor</td><td>Batch route optimisation every 90 seconds</td></tr>
<tr><td>notify-service</td><td>Node 20</td><td><em>no named owner</em></td><td>SMS and push notifications to couriers and customers</td></tr>
<tr><td>courier-app</td><td>Kotlin</td><td>Chen Wei</td><td>Android app for couriers</td></tr>
</tbody></table>
<h2>Data</h2>
<p>Primary database is <strong>PostgreSQL 15 on Amazon RDS</strong> (Multi-AZ, eu-west-1). Redis 7 (ElastiCache) holds courier locations with a 30-second TTL. Object storage for proof-of-delivery photos is S3 bucket <code>apollo-pod-prod</code>, lifecycle rule moves objects to Glacier after 180 days.</p>
<h2>Infrastructure</h2>
<p>Everything runs on <strong>AWS eu-west-1 (Ireland)</strong> in EKS cluster <code>apollo-prod</code>. Staging is a separate cluster <code>apollo-staging</code> in the same region. There is no us-east-1 footprint. Infrastructure is Terraform in the <code>apollo-infra</code> repo; changes go through Atlantis.</p>
<h2>Integrations</h2>
<ul><li>Client order systems via webhooks (HMAC-SHA256 signed, secret rotated quarterly)</li><li>Maps and ETA: Google Maps Platform (Routes API)</li><li>SMS: Twilio. Push: Firebase Cloud Messaging</li><li>Feature flags: LaunchDarkly</li></ul>
<h2>Limits worth knowing</h2>
<ul><li>Public API rate limit: 600 requests/minute per client key</li><li>Maximum stops per route: 80</li><li>Courier location updates: every 10 seconds while a route is active</li></ul>
""",
    "Apollo — Deployment runbook": """
<h2>How a change reaches production</h2>
<ol>
<li>PR against <code>main</code> in <code>apollo-delivery-service</code>. CI runs lint, unit tests and the contract tests against the mock client.</li>
<li>Merge → GitHub Actions builds the image and pushes to ECR <code>apollo/dispatch-api</code> tagged with the commit SHA.</li>
<li>Argo CD syncs <code>apollo-staging</code> automatically. Smoke tests run against staging.</li>
<li>Production is a <strong>manual promotion</strong> in Argo CD by the release captain (rotates weekly, see the on-call page). Production deploys happen <strong>Tuesday to Thursday, 10:00–16:00 Irish time only</strong>. No Friday deploys.</li>
</ol>
<h2>Rollback</h2>
<p>Argo CD → application <code>dispatch-api</code> → History → Rollback to previous. Takes about 90 seconds. Database migrations are forward-only; a rollback that needs a schema change requires a follow-up migration, never a manual edit.</p>
<h2>Secrets</h2>
<p>All secrets live in AWS Secrets Manager under <code>apollo/prod/*</code> and are mounted via External Secrets Operator. Nobody puts secrets in ConfigMaps. Twilio and Google Maps keys are rotated every 90 days by Daniel.</p>
<h2>Feature flags</h2>
<p>New behaviour ships behind a LaunchDarkly flag, defaulting off in production. Flags older than 60 days are removed in the monthly cleanup.</p>
""",
    "Apollo — On-call and escalation": """
<h2>Rota</h2>
<p>One primary and one secondary, weekly, Monday 09:00 handover. PagerDuty schedule <code>apollo-primary</code>.</p>
<table><tbody>
<tr><th>Week starting</th><th>Primary</th><th>Secondary</th><th>Release captain</th></tr>
<tr><td>8 Sep 2026</td><td>Priya Nair</td><td>Daniel Okafor</td><td>Ravi Menon</td></tr>
<tr><td>15 Sep 2026</td><td>Daniel Okafor</td><td>Ravi Menon</td><td>Priya Nair</td></tr>
<tr><td>22 Sep 2026</td><td>Ravi Menon</td><td>Priya Nair</td><td>Daniel Okafor</td></tr>
</tbody></table>
<h2>Severity</h2>
<ul>
<li><strong>Sev1</strong> — dispatch stopped for any client, or data loss. Page primary immediately, escalate to Ravi after 15 minutes, notify Maya.</li>
<li><strong>Sev2</strong> — degraded (ETAs wrong, notifications delayed &gt; 10 min). Page primary, business hours fix.</li>
<li><strong>Sev3</strong> — cosmetic or single-courier issues. Ticket, next sprint.</li>
</ul>
<h2>Client comms</h2>
<p>Northwind requires a status update every 30 minutes during a Sev1, sent to their ops mailbox. Fabrikam and Contoso get the status page only.</p>
<h2>Known failure modes</h2>
<ul>
<li>Redis eviction storm when courier count exceeds ~3,500 — raise the node size, do not restart the routing worker.</li>
<li>Twilio rate limiting during morning peak — notify-service retries with backoff; do not re-queue manually.</li>
</ul>
""",
    "Apollo — Decision log": """
<h2>ADR-001 — PostgreSQL over DynamoDB (Jan 2025)</h2>
<p>Chose PostgreSQL 15 on RDS. Reason: route reconciliation needs multi-row transactions and ad-hoc reporting; the team knows Postgres. Rejected DynamoDB.</p>
<h2>ADR-002 — Go for the routing worker (Feb 2025)</h2>
<p>Route optimisation was 11× faster in Go than the Python prototype at 80 stops. Everything else stays Python.</p>
<h2>ADR-003 — Single region (Mar 2025)</h2>
<p>eu-west-1 only. All three clients are in Ireland and the UK; multi-region adds cost with no latency benefit. Revisit if a client outside Europe signs.</p>
<h2>ADR-004 — Webhooks over polling for client integration (Apr 2025)</h2>
<p>Clients receive signed webhooks for order state changes; polling remains available as a fallback with a 60-second minimum interval.</p>
<h2>ADR-005 — Manual production promotion (Jun 2025)</h2>
<p>After the 12 June incident (auto-deploy shipped a migration during peak), production promotion is manual and windowed. See the Deployment runbook.</p>
<h2>ADR-006 — LaunchDarkly for flags (Aug 2025)</h2>
<p>Replaced the homegrown flag table. Reason: per-client targeting without a deploy.</p>
""",
    "Apollo — Team directory and ownership": """
<table><tbody>
<tr><th>Person</th><th>Role</th><th>Owns</th><th>Ask them about</th></tr>
<tr><td>Maya Iyer</td><td>Product owner</td><td>Roadmap, client relationships</td><td>Priorities, what Northwind wants, contract limits</td></tr>
<tr><td>Ravi Menon</td><td>Tech lead</td><td>Architecture, incident command</td><td>Design decisions, anything cross-service</td></tr>
<tr><td>Priya Nair</td><td>Senior backend engineer</td><td>dispatch-api, public API, webhooks</td><td>Assignment logic, API contracts, HMAC signing</td></tr>
<tr><td>Daniel Okafor</td><td>Backend engineer</td><td>routing-worker, infrastructure, secrets rotation</td><td>Route optimisation, Terraform, EKS</td></tr>
<tr><td>Chen Wei</td><td>Mobile engineer</td><td>courier-app</td><td>Android, location updates, offline mode</td></tr>
<tr><td>Fatima Zahra</td><td>QA engineer</td><td>Contract tests, release sign-off</td><td>Test data, staging, what is covered</td></tr>
</tbody></table>
<h2>Unowned</h2>
<p><strong>notify-service</strong> has had no named owner since Arjun left in July 2026. Priya covers incidents; nobody owns the roadmap for it.</p>
<h2>Working agreements</h2>
<ul><li>Stand-up 09:30 IST / 05:00 Irish time on Google Meet, daily.</li><li>Sprints are two weeks, planning on Monday, review on Friday.</li><li>PRs need one approval; anything touching assignment logic needs Priya's.</li></ul>
""",
    "Apollo — Sprint 14 planning notes (8 Sep 2026)": """
<p>Attendees: Maya, Ravi, Priya, Daniel, Chen, Fatima.</p>
<h2>Goal</h2>
<p>Ship courier ETA v2 to Northwind behind a flag, and close the notify-service backlog.</p>
<h2>Committed</h2>
<ul>
<li>ETA v2 (Routes API traffic-aware) — Daniel, Priya. Flag <code>eta-v2</code>, Northwind only.</li>
<li>Proof-of-delivery photo compression on device — Chen.</li>
<li>Contract test coverage for webhook retries — Fatima.</li>
<li>Rotate Twilio key (due 14 Sep) — Daniel.</li>
</ul>
<h2>Decisions</h2>
<ul>
<li>ETA v2 will NOT ship to Fabrikam this sprint; their integration is on the polling fallback.</li>
<li>Friday deploy freeze stays. Maya asked; Ravi declined, citing ADR-005.</li>
</ul>
<h2>Risks</h2>
<ul><li>Routes API quota — Daniel to request an increase before the 15th.</li><li>notify-service still unowned.</li></ul>
""",
}


async def main(workspace_id: str, space_key: str) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(settings.MONGO_DB)[settings.MONGO_DB_NAME]
    src = await db.sources.find_one({"workspace_id": workspace_id, "type": "confluence"})
    cfg, sec = src["config"], secrets.decrypt_dict(src.get("config_secret"))
    auth = base64.b64encode(f"{cfg['email']}:{sec['api_token']}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Accept": "application/json", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=cfg["base_url"], headers=headers, timeout=30) as c:
        r = await c.get("/rest/api/content", params={"spaceKey": space_key, "type": "page", "limit": 100})
        existing = {p["title"]: p["id"] for p in r.json().get("results", [])}
        for title, body in PAGES.items():
            if title in existing:
                print("exists:", title)
                continue
            r = await c.post("/rest/api/content", json={
                "type": "page", "title": title, "space": {"key": space_key},
                "body": {"storage": {"value": body.strip(), "representation": "storage"}},
            })
            print(r.status_code, title, r.json().get("id") if r.status_code < 300 else r.text[:200])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
