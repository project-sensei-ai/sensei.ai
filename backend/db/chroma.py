from fastapi import HTTPException, Request, status


def get_chroma(request: Request):
    client = getattr(request.app.state, "chroma_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store unavailable",
        )
    return client


def get_workspace_collection(client, workspace_id: str):
    return client.get_or_create_collection(
        name=f"ws_{workspace_id}",
        metadata={"hnsw:space": "cosine"},
    )
