"""ClickUp Connector: creates tasks via the ClickUp REST API v2.

Auth: an operator personal API token (settings UI / vault provider
`clickup`, or CLICKUP_API_TOKEN env; the pk_… form from ClickUp
settings → Apps). The target list is named per action
(list_id payload field or CLICKUP_TARGET_LIST) — ClickUp organizes
work as team → space → folder → list, and a list is where tasks live.
"""
import os
import time
import uuid as _uuid
from typing import Any

from .github_connector import load_provider_token

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

CLICKUP_API = "https://api.clickup.com/api/v2"

# Kairos priority labels → ClickUp's numeric levels (1 urgent … 4 low).
_PRIORITY = {"low": 4, "medium": 3, "high": 2, "urgent": 1}


class ClickUpConnector(BaseConnector):
    """Executes action items as ClickUp tasks."""

    @property
    def tool_name(self) -> str:
        return "clickup"

    async def _get_token(self) -> str | None:
        return await load_provider_token("clickup") or os.getenv("CLICKUP_API_TOKEN")

    async def health_check(self) -> bool:
        token = await self._get_token()
        return bool(token and token.strip())

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = False,
    ) -> ExecutionResult:
        start_time = time.time()
        try:
            name = (
                payload.get("name")
                or payload.get("title")
                or payload.get("summary")
                or payload.get("content")
                or "Untitled task"
            )
            description = payload.get("description") or payload.get("notes") or ""
            priority = _PRIORITY.get(
                str(payload.get("priority", "medium")).lower(), 3
            )
            list_id = payload.get("list_id") or payload.get("list") or os.getenv(
                "CLICKUP_TARGET_LIST"
            )

            if sandbox_mode:
                fake_id = _uuid.uuid4().hex[:12]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url="https://app.clickup.com/t/fake/" + fake_id,
                    latency_ms=int((time.time() - start_time) * 1000) + 75,
                    raw_response={"id": fake_id, "name": name, "mode": "sandbox"},
                )

            token = await self._get_token()
            if not list_id:
                raise ValueError(
                    "ClickUp execution failed: no target list. Set list_id in "
                    "the action payload or CLICKUP_TARGET_LIST."
                )
            if not token:
                raise ValueError(
                    "ClickUp execution failed: no API token configured. "
                    "Add a ClickUp token in Settings or enable Sandbox Mode."
                )

            headers = {"Authorization": token, "Content-Type": "application/json"}
            async with connector_http_client(timeout=15.0) as client:
                resp = await client.post(
                    CLICKUP_API + "/list/" + str(list_id) + "/task",
                    json={
                        "name": name[:200],
                        "description": description[:60000],
                        "priority": priority,
                    },
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json()
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=data.get("url"),
                        latency_ms=latency_ms,
                        raw_response={
                            "id": data.get("id"),
                            "name": data.get("name"),
                        },
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error="ClickUp API HTTP " + str(resp.status_code),
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
