# ── Stage 1: build the SPA ────────────────────────────────────────────────────
FROM node:22-slim AS frontend

WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Baked in at build time by Vite. Optional — without it the app falls back to
# email/password login and the Google button is hidden.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build


# ── Stage 2: the app ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# build-essential is needed to compile chromadb / pydantic wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Served by FastAPI at / with an SPA fallback, so judges get one URL.
COPY --from=frontend /ui/dist ./static

ENV CHROMA_PERSIST_DIR=/app/chroma_data \
    STATIC_DIR=/app/static \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
