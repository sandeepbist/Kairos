"""Todoist Connector: creates tasks via the Todoist REST v2 API.

Auth: a Todoist API token (settings UI / vault provider `todoist`, or
TODOIST_API_KEY env).
"""
import os
import time
import uuid as _uuid
from typing import Any

from sqlalchemy import select

from app.core.security import decrypt_token
from app.db.models import OAuthTokenModel
from app.db.session import async_session_factory

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

TODOIST_API = "https://api.todoist.com/rest/v2/tasks"

_PRIORITY_LABELS = {"low": "p4", "medium": "p3", "high": "p1"}


class TodoistConnector(BaseConnector):
    """Executes action items as Todoist tasks."""

    @property
    def tool_name(self) -> str:
        return "todoist"

    async def _get_token(self) -> str | None:
        async with async_session_factory() as session:
            res = await session.execute(
                select(OAuthTokenModel).where(OAuthTokenModel.provider == "todoist")
            )
            rec = res.scalar_one_or_none()
            if rec and rec.access_token_enc:
                return decrypt_token(rec.access_token_enc)
        return os.getenv("TODOIST_API_KEY")

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
            content = (
                payload.get("content")
                or payload.get("title")
                or payload.get("summary")
                or payload.get("description")
                or "Untitled task"
            )
            description = payload.get("description") or payload.get("notes") or ""
            due = payload.get("due_date")

            if sandbox_mode:
                fake_id = _uuid.uuid4().hex[:12]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=f"https://app.todoist.com/app/task/{fake_id}",
                    latency_ms=int((time.time() - start_time) * 1000) + 65,
                    raw_response={"id": fake_id, "content": content, "mode": "sandbox"},
                )

            token = await self._get_token()
            if not token:
                raise ValueError(
                    "Todoist execution failed: no API token configured. "
                    "Add a Todoist token in Settings or enable Sandbox Mode."
                )

            headers = {"Authorization": f"Bearer {token}"}
            body: dict[str, Any] = {
                "content": content[:500],
                "description": description[:500],
            }
            if due:
                body["due_string"] = str(due)
                body["due_lang"] = "en"
            body["priority"] = _PRIORITY_LABELS.get(
                str(payload.get("priority", "medium")).lower(), "p3"
            )

            async with connector_http_client(timeout=15.0) as client:
                resp = await client.post(TODOIST_API, data=body, headers=headers)
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json()
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=f"https://app.todoist.com/app/task/{data.get('id')}",
                        latency_ms=latency_ms,
                        raw_response=data,
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error=f"Todoist API HTTP {resp.status_code}",
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
