import os
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from core.config import settings
from db.chroma import get_chroma, get_workspace_collection
from db.database import get_db
from db.membership import require_owner, require_workspace
from db.models import serialize_source

router = APIRouter(tags=["sources"])

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Pydantic input models (discriminated by type) ─────────────────────────────

class GithubSourceIn(BaseModel):
    type: Literal["github"]
    pat: str = Field(..., min_length=1)
    repo: str = Field(..., pattern=r"^[\w.-]+/[\w.-]+$")
    label: str = ""


class UrlSourceIn(BaseModel):
    type: Literal["url"]
    urls: list[str] = Field(..., min_length=1, max_length=20)
    label: str = "URLs"


class ConfluenceSourceIn(BaseModel):
    type: Literal["confluence"]
    base_url: str
    email: str
    api_token: str
    space_key: str
    label: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _source_doc(workspace_id: str, source_type: str, label: str, config: dict, config_secret: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": uuid4().hex,
        "workspace_id": workspace_id,
        "type": source_type,
        "label": label,
        "config": config,
        "status": "pending",
        "stats": {},
        "created_at": now,
        "updated_at": now,
    }
    if config_secret:
        doc["config_secret"] = config_secret
    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def add_source(
    body: GithubSourceIn | UrlSourceIn | ConfluenceSourceIn,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")

    if body.type == "github":
        label = body.label or body.repo
        config = {"repo": body.repo}
        config_secret = {"pat": body.pat}
        doc = _source_doc(ws["_id"], "github", label, config, config_secret)

    elif body.type == "url":
        # Verify each URL is reachable before storing
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=8, follow_redirects=True) as _client:
            for _url in body.urls:
                try:
                    _r = await _client.head(_url, headers={"User-Agent": "Sensei/1.0"})
                    if _r.status_code == 405:  # HEAD not allowed — fall back to GET
                        _r = await _client.get(_url, headers={"User-Agent": "Sensei/1.0"})
                    if _r.status_code == 404:
                        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"URL not found: {_url}")
                except HTTPException:
                    raise
                except Exception as _exc:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"URL not reachable: {_url} — {_exc}")
        label = body.label or f"{len(body.urls)} URL(s)"
        config = {"urls": body.urls}
        doc = _source_doc(ws["_id"], "url", label, config)

    elif body.type == "confluence":
        label = body.label or f"Confluence:{body.space_key}"
        config = {"base_url": body.base_url, "space_key": body.space_key, "email": body.email}
        config_secret = {"api_token": body.api_token}
        doc = _source_doc(ws["_id"], "confluence", label, config, config_secret)

    await db.sources.insert_one(doc)
    return {"source": serialize_source(doc)}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unsupported file type '{ext}'. Allowed: pdf, md, txt, docx")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 20 MB limit")

    source_id = uuid4().hex
    upload_dir = os.path.join(settings.CHROMA_PERSIST_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, f"{source_id}_{file.filename}")

    with open(save_path, "wb") as f:
        f.write(contents)

    label = file.filename or source_id
    s3_uri = None

    if settings.S3_UPLOAD_BUCKET:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            s3_key = f"uploads/{source_id}/{file.filename}"
            s3.put_object(
                Bucket=settings.S3_UPLOAD_BUCKET,
                Key=s3_key,
                Body=contents,
                ContentType=file.content_type or "application/octet-stream",
            )
            s3_uri = f"s3://{settings.S3_UPLOAD_BUCKET}/{s3_key}"

            if settings.BEDROCK_KB_ID and settings.BEDROCK_KB_DATA_SOURCE_ID:
                ba = boto3.client("bedrock-agent", region_name=settings.AWS_REGION)
                ba.start_ingestion_job(
                    knowledgeBaseId=settings.BEDROCK_KB_ID,
                    dataSourceId=settings.BEDROCK_KB_DATA_SOURCE_ID,
                )
        except Exception:
            pass  # S3/KB upload is best-effort; local ingest still runs

    config = {"filename": file.filename, "size": len(contents), "path": save_path, "s3_uri": s3_uri}
    now = datetime.now(timezone.utc)
    doc = {
        "_id": source_id,
        "workspace_id": ws["_id"],
        "type": "file",
        "label": label,
        "config": config,
        "status": "pending",
        "stats": {},
        "created_at": now,
        "updated_at": now,
    }
    await db.sources.insert_one(doc)
    return {"source": serialize_source(doc)}


@router.get("")
async def list_sources(
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws, _role = await require_workspace(user, db)
    cursor = db.sources.find({"workspace_id": ws["_id"]})
    sources = [serialize_source(doc) async for doc in cursor]
    return {"sources": sources}


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await require_owner(user, db, "add or remove sources")
    source = await db.sources.find_one({"_id": source_id, "workspace_id": ws["_id"]})
    if not source:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

    # Remove all chunks from ChromaDB for this source
    try:
        chroma = get_chroma(request)
        collection = get_workspace_collection(chroma, ws["_id"])
        if collection.count() > 0:
            collection.delete(where={"source_id": source_id})
    except Exception:
        pass  # ChromaDB cleanup is best-effort

    await db.sources.delete_one({"_id": source_id})
