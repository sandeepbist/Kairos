"""History API Endpoints: Querying execution logs and batch audit trails."""
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import BatchModel, ExecutionLogModel, ActionItemModel

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[dict[str, Any]])
async def get_execution_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Returns recent batches and their real-world MCP execution status and links."""
    query = (
        select(BatchModel)
        .order_by(BatchModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    batches = result.scalars().all()

    history = []
    for b in batches:
        # Get execution logs for this batch
        logs_query = select(ExecutionLogModel).where(ExecutionLogModel.batch_id == b.id)
        logs_res = await db.execute(logs_query)
        logs = logs_res.scalars().all()

        # Get items count
        items_query = select(ActionItemModel).where(ActionItemModel.batch_id == b.id)
        items_res = await db.execute(items_query)
        items = items_res.scalars().all()

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
