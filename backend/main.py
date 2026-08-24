from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from auth.routes import router as auth_router
from core.config import settings
from db.database import ensure_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    app.state.mongo_client = None
    app.state.mongo_db = None

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

    if not settings.JWT_SECRET:
        print("[Auth] WARNING: JWT_SECRET is empty — login will fail until it is set")

    yield

    if getattr(app.state, "mongo_client", None) is not None:
        app.state.mongo_client.close()
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

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}"}
