"""History API Endpoints: Querying execution logs and batch audit trails."""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionItemModel, BatchModel, ExecutionLogModel
from app.db.session import get_db

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[dict[str, Any]])
async def get_execution_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Returns recent batches and their real-world MCP execution status and links."""
    # History volume is bounded (single operator); one bounded page scan
    # per table with Python-side grouping keeps the whole endpoint at
    # three round-trips for any limit instead of the old 1+2N shape.
    batches = list(
        (await db.scalars(select(BatchModel).order_by(BatchModel.created_at.desc())))
    )[: min(limit, 200)]

    batch_ids = {b.id for b in batches}
    logs_by_batch: dict[str, list] = {}
    items_by_batch: dict[str, list] = {}
    if batch_ids:
        for log in await db.scalars(select(ExecutionLogModel)):
            if log.batch_id in batch_ids:
                logs_by_batch.setdefault(log.batch_id, []).append(log)
        for item in await db.scalars(select(ActionItemModel)):
            if item.batch_id in batch_ids:
                items_by_batch.setdefault(item.batch_id, []).append(item)

    history = []
    for b in batches:
        logs = logs_by_batch.get(b.id, [])
        items = items_by_batch.get(b.id, [])

        history.append({
            "batch_id": b.id,
            "source_type": b.source_type,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "token_count": b.token_count,
            "total_items": len(items),
            "executed_items": len([i for i in items if i.status == "executed"]),
            "rejected_items": len([i for i in items if i.status == "rejected"]),
            "logs": [
                {
                    "id": log.id,
                    "item_id": log.item_id,
                    "tool": log.tool,
                    "status": log.status,
                    "external_url": log.external_url,
                    "item_description": log.item_description,
                    "latency_ms": log.latency_ms,
                    "executed_at": log.executed_at.isoformat() if log.executed_at else None,
                }
                for log in logs
            ],
        })

    return history


@router.delete("/batches/{batch_id}", response_model=dict[str, str])
async def delete_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Deletes a batch and all dependent records (GDPR-style erasure).

    Cascades remove action items and execution logs. Routing feedback
    rows carry no raw transcript content and are retained for the
    learning loop. Batches whose Temporal workflow is still mid-flight
    (processing/executing) are refused with 409 — deleting under a live
    workflow would leave it retrying against a missing parent.
    """
    batches = list(await db.scalars(select(BatchModel)))
    batch = next((b for b in batches if b.id == batch_id), None)
    if not batch:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with ID '{batch_id}' not found.",
        )
    if batch.status in ("processing", "executing"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Batch '{batch_id}' is still {batch.status}. "
                "Wait for it to reach a terminal state (awaiting_approval, "
                "completed, expired, or failed) before deleting."
            ),
        )
    await db.delete(batch)
    await db.commit()
    return {"status": "deleted", "batch_id": batch_id}
