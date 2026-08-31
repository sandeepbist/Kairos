"""Task Ledger Connector: routes executions through the MCP server's tool layer.

The connector invokes the Task Ledger MCP server via ``server.call_tool``
(the same dispatch path an external MCP client would use over stdio or
streamable HTTP), rather than importing the raw tool functions. This keeps
schema validation and tool dispatch in play for every execution.
"""
import time
from typing import Any

from app.mcp.servers.task_ledger import server as task_ledger_server

from .base import BaseConnector, ExecutionResult


class TaskLedgerConnector(BaseConnector):
    """Executes action items against the internal Task Ledger MCP server."""

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
            title = (
                payload.get("title")
                or payload.get("summary")
                or payload.get("description")
                or "Untitled Task"
            )
            notes = payload.get("notes") or payload.get("description") or ""
            priority = payload.get("priority", "medium")
            due_date = payload.get("due_date")

            result = await task_ledger_server.call_tool(
                "create_task",
                {
                    "title": str(title),
                    "notes": str(notes),
                    "priority": str(priority),
                    "due_date": str(due_date) if due_date else None,
                },
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # call_tool returns CallToolResult; extract structured content
            tool_output = self._extract_result(result)
            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=tool_output.get("external_url"),
                latency_ms=latency_ms,
                raw_response=tool_output,
            )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )

    @staticmethod
    def _extract_result(result: Any) -> dict[str, Any]:
        """Normalizes CallToolResult structured content into a dict."""
        # mcp 2.x: result.content is a list; structured content may live in
        # result.structured_content or as JSON text content blocks.
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                import json

                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, TypeError):
                    continue
        return {}

    async def health_check(self) -> bool:
        return True
