"""Task Ledger Connector: Custom Postgres-backed MCP integration."""
import time
from typing import Any
from .base import BaseConnector, ExecutionResult
from app.mcp.servers.task_ledger import create_task


class TaskLedgerConnector(BaseConnector):
    """Executes action items to internal Task Ledger."""

    @property
    def tool_name(self) -> str:
        return "task_ledger"

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = False,
    ) -> ExecutionResult:
        start_time = time.time()
        try:
            title = payload.get("title") or payload.get("summary") or payload.get("description") or "Untitled Task"
            notes = payload.get("notes") or payload.get("description") or ""
            priority = payload.get("priority", "medium")
            due_date = payload.get("due_date")

            result = await create_task(
                title=title,
                notes=notes,
                priority=str(priority),
                due_date=str(due_date) if due_date else None,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=result["external_url"],
                latency_ms=latency_ms,
                raw_response=result,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=latency_ms,
                error=str(e),
            )

    async def health_check(self) -> bool:
        return True
