"""
Token accounting.

Credits ran out today with no way to see what had spent them. Every background
operation now records what it cost, so the answer to "what is eating the budget"
is a query rather than a guess.
"""
from datetime import datetime, timezone


def _tokens(usage) -> tuple[int, int]:
    """Pull input/output counts out of whatever shape the SDK hands back."""
    if usage is None:
        return 0, 0
    get = usage.get if isinstance(usage, dict) else lambda k, d=0: getattr(usage, k, d)
    return int(get("inputTokens", 0) or 0), int(get("outputTokens", 0) or 0)


async def record(db, workspace_id: str, operation: str, usage, model: str = "") -> None:
    """Log what one operation cost. Never raises — accounting must not break work."""
    try:
        inp, out = _tokens(usage)
        if not (inp or out):
            return
        now = datetime.now(timezone.utc)
        await db.token_usage.insert_one({
            "workspace_id": workspace_id,
            "operation": operation,
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "at": now,
        })
        print(f"[usage] {operation}: {inp:,} in + {out:,} out = {inp + out:,} tokens")
    except Exception:
        pass


async def summary(db, workspace_id: str) -> dict:
    """Spend for a workspace, by operation."""
    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": "$operation",
                    "total": {"$sum": "$total_tokens"},
                    "runs": {"$sum": 1}}},
        {"$sort": {"total": -1}},
    ]
    by_op = [
        {"operation": r["_id"], "total_tokens": r["total"], "runs": r["runs"]}
        async for r in db.token_usage.aggregate(pipeline)
    ]
    return {"total_tokens": sum(r["total_tokens"] for r in by_op), "by_operation": by_op}
