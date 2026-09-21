"""Task Ledger MCP Server: custom authored MCP server backed by PostgreSQL.

This is a genuine MCP server (mcp 2.x ``MCPServer``, the renamed FastMCP):
tools are registered via the ``@server.tool()`` decorator and invoked
through ``server.call_tool()`` — the same code path an external MCP
client would exercise over stdio/HTTP. The connector layer goes through
``call_tool`` rather than importing the raw functions, so schema
validation and tool dispatch are always enforced.

Run standalone (external MCP server over stdio):
    python -m app.mcp.servers.task_ledger
"""
import uuid
from typing import Any

from mcp.server.mcpserver import MCPServer
from sqlalchemy import select

from app.db.models import TaskLedgerModel
from app.db.session import async_session_factory

server = MCPServer(
    name="task-ledger",
    version="1.0.0",
    description=(
        "Internal Task Ledger MCP server for action items and fallback tasks "
        "that do not map to external tools."
    ),
)


def _external_url(task_id: str) -> str:
    return f"task_ledger://tasks/{task_id}"


def _task_dict(t: TaskLedgerModel) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "notes": t.notes,
        "priority": t.priority,
        "due_date": t.due_date,
        "status": t.status,
        "external_url": _external_url(t.id),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@server.tool(name="create_task", description="Create a new task in the Task Ledger database.")
async def create_task(
    title: str,
    notes: str = "",
    priority: str = "medium",
    due_date: str | None = None,
    external_ref: str | None = None,
) -> dict[str, Any]:
    """Creates a new record in the task_ledger_tasks table.

    external_ref is a caller-supplied dedup token: when present, an
    existing row with the same ref is returned instead of inserting a
    duplicate, so execution retries are exactly-once. The unique DB
    constraint covers the check-then-act race (IntegrityError falls
    back to re-selecting the winner).
    """
    from sqlalchemy.exc import IntegrityError

    async with async_session_factory() as session:
        if external_ref:
            existing = (
                await session.execute(
                    select(TaskLedgerModel).where(
                        TaskLedgerModel.external_ref == external_ref
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return _task_dict(existing)
        task_id = str(uuid.uuid4())
        task = TaskLedgerModel(
            id=task_id,
            title=title,
            notes=notes,
            priority=priority.lower() if priority else "medium",
            due_date=due_date,
            status="open",
            external_ref=external_ref,
        )
        session.add(task)
        try:
            await session.commit()
        except IntegrityError:
            # Lost the insert race: another call created this ref first.
            await session.rollback()
            existing = (
                await session.execute(
                    select(TaskLedgerModel).where(
                        TaskLedgerModel.external_ref == external_ref
                    )
                )
            ).scalar_one()
            return _task_dict(existing)
        await session.refresh(task)
        return _task_dict(task)


@server.tool(
    name="list_tasks",
    description="List tasks from the Task Ledger with optional status filtering.",
)
async def list_tasks(
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lists tasks from task_ledger_tasks (newest first, capped at 200
    rows per call like the HTTP surface — callers must not be able to
    request unbounded scans)."""
    capped = max(1, min(limit or 50, 200))
    async with async_session_factory() as session:
        query = select(TaskLedgerModel).order_by(TaskLedgerModel.created_at.desc()).limit(capped)
        if status:
            query = query.where(TaskLedgerModel.status == status.lower())
        result = await session.execute(query)
        return [_task_dict(t) for t in result.scalars().all()]


@server.tool(
    name="complete_task",
    description="Mark an existing task in Task Ledger as completed.",
)
async def complete_task(task_id: str) -> dict[str, Any]:
    """Marks task status as completed."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found in Task Ledger")
        task.status = "completed"
        await session.commit()
        await session.refresh(task)
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "external_url": _external_url(task.id),
        }


@server.tool(
    name="delete_task",
    description="Soft-delete a task from Task Ledger.",
)
async def delete_task(task_id: str) -> dict[str, Any]:
    """Marks task status as deleted."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(TaskLedgerModel).where(TaskLedgerModel.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found in Task Ledger")
        task.status = "deleted"
        await session.commit()
        return {"id": task_id, "status": "deleted"}


# Backwards-compatible aliases (existing imports reference these names)
task_ledger_server = server


async def run_stdio() -> None:
    """Entry point for running the server as an external MCP stdio process."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_stdio())
