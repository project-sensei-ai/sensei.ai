import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from auth.routes import router as auth_router
from activity.routes import router as activity_router
from artifacts.routes import router as artifacts_router
from answers.routes import router as answers_router
from briefs.routes import router as briefs_router
from gaps.routes import router as gaps_router
from chat.routes import router as chat_router
from core.config import settings
from db.database import ensure_indexes
from ingest.routes import router as ingest_router
from meetings.routes import router as meetings_router
from readiness.routes import router as readiness_router
from slack_channel.routes import router as slack_router
from sources.routes import router as sources_router
from toolgrants.routes import router as tools_router
from trust.routes import router as trust_router
from watch.routes import router as watch_router
from workspaces.routes import router as workspaces_router


async def _watch_loop(app: FastAPI) -> None:
    """Re-read every workspace's sources on an interval, and stay quiet unless
    something material moved."""
    from agent.watch import watch_workspace

    interval = settings.WATCH_INTERVAL_MINUTES * 60
    while True:
        await asyncio.sleep(interval)
        try:
            db = app.state.mongo_db
            async for ws in db.workspaces.find({}):
                await watch_workspace(db, app.state.chroma_client, ws["_id"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[watch] loop error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    app.state.mongo_client = None
    app.state.mongo_db = None
    app.state.chroma_client = None

    if not settings.MONGO_DB:
        print("[MongoDB] MONGO_DB not set — skipping database connection")
    else:
        try:
            print("[MongoDB] Connecting...")
            client = AsyncIOMotorClient(
                settings.MONGO_DB,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
            )
            await client.admin.command("ping")
            app.state.mongo_client = client
            app.state.mongo_db = client[settings.MONGO_DB_NAME]
            await ensure_indexes(app.state.mongo_db)
            hosts = ", ".join(f"{h}:{p}" for h, p in client.nodes)
            print(f"[MongoDB] Connected OK — cluster: {hosts} — db: '{settings.MONGO_DB_NAME}'")
        except Exception as exc:
            print(f"[MongoDB] CONNECTION FAILED: {exc}")

    try:
        print(f"[ChromaDB] Initializing at '{settings.CHROMA_PERSIST_DIR}'...")
        app.state.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        print("[ChromaDB] Ready")
    except Exception as exc:
        print(f"[ChromaDB] INIT FAILED: {exc}")

    if not settings.JWT_SECRET:
        print("[Auth] WARNING: JWT_SECRET is empty — login will fail until it is set")

    # The background watch. Off unless an interval is configured, because a loop
    # that re-reads every connected source on a timer costs API quota and
    # provider tokens, and that should be a decision rather than a default.
    watcher = None
    if settings.WATCH_INTERVAL_MINUTES > 0 and app.state.mongo_db is not None:
        watcher = asyncio.create_task(_watch_loop(app))
        print(f"[watch] checking every {settings.WATCH_INTERVAL_MINUTES} min")

    yield

    if watcher is not None:
        watcher.cancel()

    # Warm MCP sessions hold background threads; close them off the loop.
    try:
        from toolgrants.pool import close_all
        await close_all()
    except Exception:
        pass

    if getattr(app.state, "mongo_client", None) is not None:
        app.state.mongo_client.close()
    app.state.chroma_client = None
    print("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every API route lives under /api so a built SPA can be served from the same
# origin — no CORS, no second deploy, one URL. In dev, Vite proxies /api through
# to this app without rewriting, so the paths are identical in both.
API_PREFIX = "/api"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(workspaces_router, prefix=f"{API_PREFIX}/workspaces")
app.include_router(sources_router, prefix=f"{API_PREFIX}/sources")
app.include_router(ingest_router, prefix=f"{API_PREFIX}/ingest")
app.include_router(chat_router, prefix=f"{API_PREFIX}/chat")
app.include_router(briefs_router, prefix=f"{API_PREFIX}/briefs")
app.include_router(gaps_router, prefix=f"{API_PREFIX}/gaps")
app.include_router(activity_router, prefix=f"{API_PREFIX}/activity")
app.include_router(answers_router, prefix=f"{API_PREFIX}/answers")
app.include_router(trust_router, prefix=f"{API_PREFIX}/trust")
app.include_router(watch_router, prefix=f"{API_PREFIX}/watch")
app.include_router(tools_router, prefix=f"{API_PREFIX}/tools")
app.include_router(artifacts_router, prefix=f"{API_PREFIX}/artifacts")
app.include_router(meetings_router, prefix=f"{API_PREFIX}/meetings")
app.include_router(readiness_router, prefix=f"{API_PREFIX}/readiness")
app.include_router(slack_router, prefix=f"{API_PREFIX}/slack")


def _health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}


# Unprefixed /health too, so container and platform health probes work as-is.
app.get("/health")(_health)
app.get(f"{API_PREFIX}/health")(_health)


# ── SPA ───────────────────────────────────────────────────────────────────────
# Mounted only when a build is present (the Docker image copies one in). Without
# it this stays an API-only app, which is what `uvicorn main:app --reload` wants.
_static = Path(settings.STATIC_DIR)

if (_static / "index.html").is_file():
    if (_static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """Serve built files, falling back to index.html so client routes work on reload."""
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (_static / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static.resolve()):
            return FileResponse(candidate)
        # The shell must never be cached: hashed assets can be, but a stale
        # index.html keeps pointing at an old bundle after every rebuild.
        return FileResponse(_static / "index.html", headers={"Cache-Control": "no-store, must-revalidate"})

    print(f"[SPA] Serving built frontend from '{_static}'")
else:
    @app.get("/")
    async def root():
        return {"message": f"Welcome to {settings.APP_NAME}", "docs": "/docs", "api": API_PREFIX}
