# Deploying Sensei

One container. The image builds the React app and FastAPI serves it alongside
`/api/*`, so there is a single URL, no CORS setup and no second deployment.

Verify the image locally first:

```bash
docker compose up --build
open http://localhost:8000
```

> **Not yet run.** The Dockerfile has been checked statically — every `COPY`
> source exists, both base images are pinned, and the two build steps
> (`npm ci && npm run build`, then `pip install -r requirements.txt`) are known
> to succeed natively. But the image itself has never been built, because Docker
> is not installed on the development machine. Build it once before relying on
> any of the deployment paths below.

---

## Option A — Fly.io  (fastest; recommended if the clock is short)

```bash
fly launch --no-deploy --copy-config          # pick a name + region
fly volume create chroma_data --size 1 --region <region>
fly secrets set \
  MONGO_DB="mongodb+srv://..." \
  JWT_SECRET="$(openssl rand -hex 32)" \
  GROQ_API_KEY="gsk_..."
fly deploy --build-arg VITE_GOOGLE_CLIENT_ID="<google-client-id>"   # arg optional
fly secrets set FRONTEND_ORIGIN="https://<app>.fly.dev"             # invite links
```

`fly.toml` already sets the volume mount, the health check and 2 GB of memory —
chromadb plus sentence-transformers will OOM at 512 MB.

---

## Option B — AWS App Runner  (on-theme for an AWS hackathon)

```bash
aws ecr create-repository --repository-name sensei
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <acct>.dkr.ecr.us-east-1.amazonaws.com

docker build --platform linux/amd64 \
  --build-arg VITE_GOOGLE_CLIENT_ID="<google-client-id>" \
  -t <acct>.dkr.ecr.us-east-1.amazonaws.com/sensei:latest .
docker push <acct>.dkr.ecr.us-east-1.amazonaws.com/sensei:latest
```

Create the App Runner service from that image with port `8000`, health check
path `/health`, at least 2 GB memory, and these environment variables:

| Variable | Value |
|---|---|
| `MONGO_DB` | Atlas connection string |
| `MONGO_DB_NAME` | `sensei` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `GROQ_API_KEY` | Groq key, or set `LLM_BACKEND=bedrock` and attach an instance role with Bedrock access |
| `FRONTEND_ORIGIN` | the App Runner URL, once known |
| `STATIC_DIR` | `/app/static` |
| `DEBUG` | `false` |

**Caveat:** App Runner storage is ephemeral, so the ChromaDB directory is lost
on every deploy and sources need re-ingesting. Either accept that for a demo, or
set `S3_UPLOAD_BUCKET` + `BEDROCK_KB_ID` so uploaded files are indexed by Bedrock
Knowledge Bases instead. Fly's volume avoids the problem outright.

---

## After deploying — the five-minute checklist

1. `curl https://<host>/health` → `{"status":"ok",...}`
2. Open `https://<host>/` — the SPA loads, and a hard refresh on
   `/chat` still works (the SPA fallback).
3. Log in with the demo account from [TESTING.md](TESTING.md) and ask a question;
   confirm citations render.
4. Generate an invite link and check the host in it is the deployed URL, not
   `localhost:5173`. If it is wrong, `FRONTEND_ORIGIN` is unset.
5. If you are using Google sign-in, add `https://<host>` to **Authorized
   JavaScript origins** in the Google Cloud console, and rebuild with
   `VITE_GOOGLE_CLIENT_ID` — Vite bakes it in at build time.

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `MONGO_DB` | yes | Atlas connection string |
| `MONGO_DB_NAME` | yes | defaults to `sensei` |
| `JWT_SECRET` | yes | signs session cookies |
| `GROQ_API_KEY` | unless Bedrock | development / default backend |
| `FRONTEND_ORIGIN` | yes | host used to build invite links |
| `STATIC_DIR` | yes in Docker | `/app/static`; unset locally so the API runs alone |
| `CHROMA_PERSIST_DIR` | yes | put it on a persistent volume |
| `DEBUG` | no | `false` in production so session cookies are `Secure` |
| `LLM_BACKEND` | no | `groq` · `bedrock` · `ollama` |
| `S3_SESSION_BUCKET` | no | agent conversation memory via `S3SessionManager` |
| `S3_UPLOAD_BUCKET`, `BEDROCK_KB_ID`, `BEDROCK_KB_DATA_SOURCE_ID` | no | Bedrock Knowledge Bases for uploaded files |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | no | prefer an instance role over static keys |
