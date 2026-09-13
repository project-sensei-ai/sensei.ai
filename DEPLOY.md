# Deploying Sensei

One container. The image builds the React app and FastAPI serves it alongside
`/api/*`, so there is a single URL, no CORS setup and no second deployment.
Chromium for the Google Meet bot ships in the image.

---

## Option A — AWS EC2, one command  (recommended)

From a laptop with AWS credentials (`aws sts get-caller-identity` works) and
a filled-in `backend/.env`:

```bash
deploy/launch-ec2.sh feat/agent-onboarding     # or main
```

What it does:

1. Creates a security group `sensei-web` (80, 443, 22) if there is none.
2. Launches a `t3.large` Amazon Linux 2023 instance with a 30 GB disk.
3. Hands it `deploy/ec2-user-data.sh` with `backend/.env` baked in, which
   installs Docker, clones the branch, and runs
   `deploy/docker-compose.prod.yml` — the app plus **Caddy**, which fetches a
   Let's Encrypt certificate for `<ip-with-dashes>.sslip.io` automatically.
4. Prints the `https://` URL. The first build takes 5–8 minutes; watch with
   `ssh ec2-user@<ip> sudo journalctl -u cloud-final -f` if you attached a key.

Then:

```bash
curl https://<host>/health                       # {"status":"ok",...}
```

and set `FRONTEND_ORIGIN=https://<host>` in the instance's `backend/.env`
(`docker compose ... up -d` again) so invite links carry the public host —
the compose file already does this from `SENSEI_HOST`.

**Cost:** about $2/day for a t3.large. Terminate it after judging ends.

**Bedrock on the instance:** attach an instance profile with
`bedrock:InvokeModel` and set `LLM_BACKEND=bedrock` — no static keys on the
box. The account root cannot call Bedrock; an IAM role or user is required.

## Option B — any Docker host

```bash
SENSEI_HOST=sensei.example.com docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Point the DNS name at the host; Caddy does the rest.

## Option C — Fly.io

```bash
fly launch --no-deploy --copy-config
fly volume create chroma_data --size 1 --region <region>
fly secrets set MONGO_DB="..." JWT_SECRET="$(openssl rand -hex 32)" \
  SECRET_ENCRYPTION_KEY="$(openssl rand -hex 32)" GROQ_API_KEY="gsk_..."
fly deploy
fly secrets set FRONTEND_ORIGIN="https://<app>.fly.dev"
```

`fly.toml` sets the volume mount, the health check and 2 GB of memory —
chromadb plus the embedding model will OOM at 512 MB.

---

## After deploying — the five-minute checklist

1. `curl https://<host>/health` → `{"status":"ok",...}`
2. Open `https://<host>/` — the SPA loads, and a hard refresh on `/chat` still works.
3. Log in as `maya@apollo.demo` (TESTING.md) and ask a question; confirm citations render.
4. On **Tools**, "Reconnect & refresh tools" on the GitHub connection succeeds — the MCP egress works from the box.
5. Generate an invite link and check the host in it is the deployed URL. If not, `FRONTEND_ORIGIN` is unset.
6. Start a companion meeting and type one line; the reply arrives. (The mic needs HTTPS, which Caddy provides.)

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `MONGO_DB` | yes | Atlas connection string |
| `MONGO_DB_NAME` | yes | defaults to `sensei` |
| `JWT_SECRET` | yes | signs session cookies |
| `SECRET_ENCRYPTION_KEY` | yes | encrypts source credentials and tool-grant tokens at rest |
| `GROQ_API_KEY` | unless Bedrock | development / default backend |
| `GROQ_FALLBACK_MODELS` | no | comma list tried when a model's daily quota is exhausted |
| `MAX_GRANT_TOOLS_PER_TURN` | no | granted MCP tools offered per question (default 12) |
| `FRONTEND_ORIGIN` | yes | host used to build invite links |
| `STATIC_DIR` | yes in Docker | `/app/static`; unset locally so the API runs alone |
| `CHROMA_PERSIST_DIR` | yes | put it on a persistent volume |
| `WATCH_INTERVAL_MINUTES` | no | 0 disables the change watcher |
| `DEBUG` | no | `false` in production so session cookies are `Secure` |
| `LLM_BACKEND` | no | `groq` · `bedrock` · `ollama` |
| `BEDROCK_MODEL_ID`, `BEDROCK_BACKGROUND_MODEL_ID` | Bedrock | cross-region inference profiles, e.g. `us.anthropic.claude-sonnet-4-6` |
| `S3_SESSION_BUCKET` | no | agent conversation memory via `S3SessionManager` |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | no | prefer an instance role over static keys |
