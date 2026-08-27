"""Task Ledger MCP Server: Custom authored MCP server backed by PostgreSQL."""
import uuid
from typing import Any
from sqlalchemy import select, update
from mcp.server.mcpserver import MCPServer
from app.db.session import async_session_factory
from app.db.models import TaskLedgerModel

# Initialize FastMCP / MCPServer instance
task_ledger_server = MCPServer(
    name="task-ledger",
    version="1.0.0",
    description="Internal Task Ledger MCP server for action items and fallback tasks",
)


@task_ledger_server.tool(
    name="create_task",
    description="Create a new task in the Task Ledger database.",
)
async def create_task(
    title: str,
    notes: str = "",
    priority: str = "medium",
    due_date: str | None = None,
) -> dict[str, Any]:
    """Creates a new record in task_ledger_tasks table."""
    task_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        task = TaskLedgerModel(
            id=task_id,
            title=title,
            notes=notes,
            priority=priority.lower() if priority else "medium",
            due_date=due_date,
            status="open",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "notes": task.notes,
            "priority": task.priority,
            "due_date": task.due_date,
            "status": task.status,
            "external_url": f"task_ledger://tasks/{task.id}",
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }


@task_ledger_server.tool(
    name="list_tasks",
    description="List tasks from the Task Ledger with optional status filtering.",
)
async def list_tasks(
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lists tasks from task_ledger_tasks."""
    async with async_session_factory() as session:
        query = select(TaskLedgerModel).order_by(TaskLedgerModel.created_at.desc()).limit(limit)
        if status:
            query = query.where(TaskLedgerModel.status == status.lower())
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "notes": t.notes,
                "priority": t.priority,
                "due_date": t.due_date,
                "status": t.status,
                "external_url": f"task_ledger://tasks/{t.id}",
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]


@task_ledger_server.tool(
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
            "external_url": f"task_ledger://tasks/{task.id}",
        }


@task_ledger_server.tool(
    name="delete_task",
    description="Soft-delete or remove a task from Task Ledger.",
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
