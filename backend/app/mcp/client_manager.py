from datetime import datetime, timezone
import json
import hashlib
import uuid
from typing import Any
from sqlalchemy import select
from app.config import settings
from app.db.session import async_session_factory
from app.db.models import ExecutionLogModel, ActionItemModel
from .connectors import (
    BaseConnector,
    ExecutionResult,
    TaskLedgerConnector,
    NotionConnector,
    JiraConnector,
    CalendarConnector,
)


class McpClientManager:
    """Manages connector execution, SHA256 deduplication, and execution logs."""

    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {
            "task_ledger": TaskLedgerConnector(),
            "notion": NotionConnector(),
            "jira": JiraConnector(),
            "calendar": CalendarConnector(),
        }

    def get_connector(self, tool_name: str) -> BaseConnector:
        """Retrieves connector by name or raises ValueError."""
        normalized = tool_name.lower().strip()
        if normalized not in self._connectors:
            raise ValueError(f"Unsupported tool '{tool_name}'. Available: {list(self._connectors.keys())}")
        return self._connectors[normalized]

    @staticmethod
    def compute_idempotency_hash(
        batch_id: str,
        item_id: str,
        tool: str,
        payload: dict[str, Any],
    ) -> str:
        """Computes deterministic SHA256 hash across batch, item, tool, and sorted payload."""
        payload_canonical = json.dumps(payload, sort_keys=True, default=str)
        raw_key = f"{batch_id}:{item_id}:{tool.lower()}:{payload_canonical}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def execute_action(
        self,
        batch_id: str,
        item_id: str,
        tool: str,
        payload: dict[str, Any],
        item_description: str | None = None,
        sandbox_mode: bool | None = None,
    ) -> ExecutionResult:
        """Executes action item with deduplication checks and DB logging."""
        effective_sandbox = sandbox_mode if sandbox_mode is not None else settings.SANDBOX_MODE
        idempotency_hash = self.compute_idempotency_hash(batch_id, item_id, tool, payload)

        # 1. Idempotency Check against execution_logs
        async with async_session_factory() as session:
            existing_log_query = select(ExecutionLogModel).where(
                ExecutionLogModel.idempotency_hash == idempotency_hash,
                ExecutionLogModel.status == "success",
            )
            existing_log_res = await session.execute(existing_log_query)
            existing_log = existing_log_res.scalar_one_or_none()

            if existing_log:
                return ExecutionResult(
                    tool=tool,
                    status="success",
                    external_url=existing_log.external_url,
                    latency_ms=0,
                    raw_response={
                        "deduplicated": True,
                        "idempotency_hash": idempotency_hash,
                        "original_log_id": existing_log.id,
                    },
                )

        # 2. Dispatch to target connector
        connector = self.get_connector(tool)
        result = await connector.execute(payload, sandbox_mode=effective_sandbox)

        # 3. Record Execution Log & Update Action Item Status
        async with async_session_factory() as session:
            log_id = str(uuid.uuid4())
            log_entry = ExecutionLogModel(
                id=log_id,
                item_id=item_id,
                batch_id=batch_id,
                tool=tool,
                status=result.status,
                idempotency_hash=idempotency_hash,
                external_url=result.external_url,
                item_description=item_description or payload.get("title") or payload.get("summary") or "",
                latency_ms=result.latency_ms,
                error=result.error,
            )
            session.add(log_entry)

            # Update ActionItemModel if item exists in DB
            item_query = select(ActionItemModel).where(ActionItemModel.id == item_id)
            item_res = await session.execute(item_query)
            action_item = item_res.scalar_one_or_none()
            if action_item:
                action_item.status = "executed" if result.status == "success" else "failed"
                action_item.external_url = result.external_url
                action_item.final_tool = tool
                if result.status == "success":
                    action_item.executed_at = datetime.now(timezone.utc)

            await session.commit()

        return result

    async def get_connectors_status(self) -> dict[str, Any]:
        """Returns health status and configured modes for all connectors."""
        statuses = {}
        for name, connector in self._connectors.items():
            is_healthy = await connector.health_check()
            statuses[name] = {
                "healthy": is_healthy,
                "sandbox_mode": settings.SANDBOX_MODE,
            }
        return statuses


# Global default client manager instance
mcp_client_manager = McpClientManager()
