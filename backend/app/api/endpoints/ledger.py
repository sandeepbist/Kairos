"""Ledger API Endpoints: HTTP surface over the internal Task Ledger.

The Task Ledger already exists as a first-class MCP server
(app/mcp/servers/task_ledger.py) that the Temporal worker calls for
fallback tasks. This module exposes the same data over plain HTTP for
the operator UI — list, complete, and soft-delete — so the dashboard can
render and manage ledger tasks without going through the MCP tool path.

Contract notes (mirrors the MCP server's semantics):
- Listing excludes soft-deleted rows unless "deleted" is asked for by
  name via ?status=deleted.
- Complete is a no-op-safe flip: it 404s on missing or deleted tasks.
- Delete is a soft delete (status='deleted'); the row is retained for
  audit, and repeat deletes 404 rather than ping-ponging state.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TaskLedgerModel
from app.db.session import get_db

router = APIRouter(prefix="/ledger", tags=["ledger"])


def _task_dict(task: TaskLedgerModel) -> dict[str, Any]:
    """Serializes a ledger row for the UI (datetimes → ISO strings)."""
    return {
        "id": task.id,
        "title": task.title,
        "notes": task.notes,
        "priority": task.priority,
        "due_date": task.due_date,
        "status": task.status,
        "external_url": f"task_ledger://tasks/{task.id}",
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/tasks", response_model=list[dict[str, Any]])
async def list_ledger_tasks(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Lists ledger tasks, newest first.

    Soft-deleted rows are hidden unless the caller explicitly asks for
    them (?status=deleted) — the dashboard trash view — or lists every
    status by name. Limit is capped at 200 rows per page.
    """
    capped_limit = max(1, min(limit, 200))
    query = select(TaskLedgerModel).order_by(TaskLedgerModel.created_at.desc())
    if status is not None and status.strip():
        query = query.where(TaskLedgerModel.status == status.strip().lower())
    else:
        # Default view excludes soft-deleted rows.
        query = query.where(TaskLedgerModel.status != "deleted")
    tasks = list(await db.scalars(query.limit(capped_limit)))
    return [_task_dict(t) for t in tasks]


@router.post("/tasks/{task_id}/complete", response_model=dict[str, str])
async def complete_ledger_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Marks a ledger task completed (open → completed).

    Missing and already-deleted tasks are treated the same: 404, so a
    stale dashboard tab can never resurrect a deleted row.
    """
    task = (
        await db.scalars(
            select(TaskLedgerModel).where(
                TaskLedgerModel.id == task_id,
                TaskLedgerModel.status != "deleted",
            )
        )
    ).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found in Task Ledger.",
        )

    task.status = "completed"
    await db.commit()
    return {"status": "completed", "task_id": task_id}


@router.delete("/tasks/{task_id}", response_model=dict[str, str])
async def delete_ledger_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Soft-deletes a ledger task (status='deleted'; row retained).

    Deleting an already-deleted task 404s — the idempotent-but-honest
    choice: the caller's view of the row is stale and should refresh.
    """
    task = (
        await db.scalars(
            select(TaskLedgerModel).where(
                TaskLedgerModel.id == task_id,
                TaskLedgerModel.status != "deleted",
            )
        )
    ).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found in Task Ledger.",
        )

    task.status = "deleted"
    await db.commit()
    return {"status": "deleted", "task_id": task_id}
