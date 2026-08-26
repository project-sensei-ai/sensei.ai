"""Chat endpoint — queries ChromaDB and answers via Groq."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from groq import Groq
from pydantic import BaseModel, Field

from auth.deps import get_current_user
from core.config import settings
from db.chroma import get_chroma, get_workspace_collection
from db.database import get_db

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    ws = await db.workspaces.find_one({"owner_id": user["id"]})
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No workspace found — complete onboarding first")

    chroma = get_chroma(request)
    collection = get_workspace_collection(chroma, ws["_id"])

    count = collection.count()
    if count == 0:
        return {
            "answer": "No sources have been indexed yet. Add and ingest some sources in onboarding first.",
            "citations": [],
        }

    n = min(5, count)
    results = collection.query(
        query_texts=[body.question],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    if not docs:
        return {"answer": "I couldn't find relevant content for that question.", "citations": []}

    # Build numbered context + deduplicated citations
    context_parts: list[str] = []
    citations: list[dict] = []
    seen_labels: set[str] = set()

    for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances)):
        label = (
            meta.get("source_label")
            or meta.get("repo")
            or meta.get("title")
            or meta.get("url")
            or "Unknown source"
        )
        context_parts.append(f"[{i + 1}] {label}\n{doc}")
        if label not in seen_labels:
            seen_labels.add(label)
            citations.append({
                "index": i + 1,
                "source_label": label,
                "excerpt": doc[:250] + ("…" if len(doc) > 250 else ""),
                "score": round(1 - float(dist), 3),
            })

    context = "\n\n---\n\n".join(context_parts)

    if not settings.GROQ_API_KEY:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "GROQ_API_KEY not configured")

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    completion = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Sensei, a helpful AI assistant embedded in a project knowledge platform.\n\n"
                    "Behaviour rules:\n"
                    "- For greetings, small-talk, or general questions (e.g. 'how are you', 'what can you do'): "
                    "respond naturally and helpfully from your own knowledge — do NOT reference the context.\n"
                    "- For questions about the project, code, or documentation: answer ONLY from the numbered "
                    "context passages below. Cite every claim inline with [N] matching the passage number. "
                    "If the context is insufficient, say so clearly — never fabricate.\n"
                    "- Be concise. Use markdown for code or lists when helpful."
                ),
            },
            {
                "role": "user",
                "content": f"Context passages from indexed sources:\n{context}\n\nQuestion: {body.question}",
            },
        ],
        max_tokens=1024,
        temperature=0.1,
    )

    answer = completion.choices[0].message.content or ""
    return {"answer": answer, "citations": citations}
