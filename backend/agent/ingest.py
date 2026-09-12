"""Background ingestion runner — fetches, chunks, and embeds source content into ChromaDB."""
import asyncio
from datetime import datetime, timezone

from db.chroma import get_workspace_collection
from agent.tools import fetch_github, fetch_urls, parse_file, fetch_confluence


# ChromaDB's default embedder (ONNX all-MiniLM-L6-v2) truncates its input at 256
# tokens — roughly 1 000 characters of English. Anything past that is silently
# dropped from the vector, so a 2 000-character chunk had half its text invisible
# to search: a section could be indexed and still be unfindable. 800 characters
# keeps a whole chunk inside the embedder's window.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character-based chunks."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


async def run_ingestion(db, chroma_client, source_id: str) -> None:
    """Fetch content for a source, chunk it, and upsert into ChromaDB."""
    source = await db.sources.find_one({"_id": source_id})
    if not source:
        return

    await db.sources.update_one(
        {"_id": source_id},
        {"$set": {"status": "indexing", "updated_at": datetime.now(timezone.utc)}},
    )

    try:
        raw_docs: list[dict] = []

        if source["type"] == "github":
            cfg = source["config"]
            secret = source.get("config_secret", {})
            raw_docs = await fetch_github(repo=cfg["repo"], pat=secret.get("pat", ""))

        elif source["type"] == "url":
            raw_docs = await fetch_urls(urls=source["config"]["urls"])

        elif source["type"] == "file":
            cfg = source["config"]
            # parse_file is sync — run in thread pool
            raw_docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: parse_file(file_path=cfg["path"], filename=cfg["filename"])
            )

        elif source["type"] == "confluence":
            cfg = source["config"]
            secret = source.get("config_secret", {})
            raw_docs = await fetch_confluence(
                base_url=cfg["base_url"],
                email=cfg["email"],
                api_token=secret.get("api_token", ""),
                space_key=cfg["space_key"],
            )

        # Chunk and collect
        ids, documents, metadatas = [], [], []
        chunk_index = 0
        for doc in raw_docs:
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            for chunk in _chunk_text(content):
                chunk_id = f"{source_id}_{chunk_index}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({**meta, "source_id": source_id, "source_label": source["label"], "chunk": chunk_index})
                chunk_index += 1

        # Remove stale chunks from previous ingest before writing new ones
        collection = get_workspace_collection(chroma_client, source["workspace_id"])
        try:
            collection.delete(where={"source_id": source_id})
        except Exception:
            pass  # collection may be empty on first run

        # Upsert into ChromaDB (default sentence-transformers embedder)
        if ids:
            batch = 500
            for i in range(0, len(ids), batch):
                collection.upsert(
                    ids=ids[i:i+batch],
                    documents=documents[i:i+batch],
                    metadatas=metadatas[i:i+batch],
                )

        pages_crawled = len(raw_docs)
        await db.sources.update_one(
            {"_id": source_id},
            {"$set": {
                "status": "ready",
                "stats": {"chunks_count": chunk_index, "pages_crawled": pages_crawled},
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    except Exception as exc:
        await db.sources.update_one(
            {"_id": source_id},
            {"$set": {
                "status": "error",
                "error_message": str(exc),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
