"""Slack Events API endpoint, and the record of what Sensei said in Slack."""
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from auth.deps import get_current_user
from core.config import settings
from db.database import get_db
from db.membership import require_workspace
from slack_channel.service import handle_event, verify_signature

router = APIRouter(tags=["slack"])


async def _handle(db, chroma_client, payload: dict) -> None:
    try:
        result = await handle_event(db, chroma_client, payload)
        print(f"[slack] {result.get('outcome')}: {result.get('reason')}")
    except Exception as exc:
        print(f"[slack] event failed: {exc}")


@router.post("/events")
async def slack_events(request: Request, background: BackgroundTasks):
    """
    Slack posts every event here and expects a 200 within three seconds, so
    the work happens after the response. A retry (X-Slack-Retry-Num) is
    acknowledged without being handled again.
    """
    body = await request.body()
    if settings.SLACK_SIGNING_SECRET and not verify_signature(
        settings.SLACK_SIGNING_SECRET, request.headers.get("X-Slack-Request-Timestamp"),
        body, request.headers.get("X-Slack-Signature"),
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Slack signature check failed")
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not JSON")
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    if request.headers.get("X-Slack-Retry-Num"):
        return {"ok": True, "note": "already received"}
    if payload.get("type") == "event_callback":
        background.add_task(_handle, request.app.state.mongo_db, request.app.state.chroma_client, payload)
    return {"ok": True}


@router.get("/activity")
async def slack_activity(user=Depends(get_current_user), db=Depends(get_db)):
    """What Sensei has said, and declined to say, in this project's Slack."""
    ws, _ = await require_workspace(user, db)
    rows = await db.slack_replies.find({"workspace_id": ws["_id"]}).sort("at", -1).limit(30).to_list(30)
    return {
        "signing_secret_set": bool(settings.SLACK_SIGNING_SECRET),
        "proactive": settings.SLACK_PROACTIVE,
        "replies": [{
            "id": r["_id"], "channel": r.get("channel_name") or r.get("channel"), "text": r.get("text"),
            "mode": r.get("mode"), "reason": r.get("reason"), "posted": r.get("posted"), "indexed": r.get("indexed"),
            "answer": r.get("answer"), "at": r["at"].isoformat() if hasattr(r.get("at"), "isoformat") else r.get("at"),
        } for r in rows],
    }
