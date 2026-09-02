"""Google Tasks Connector: inserts tasks via the Tasks API v1.

Auth: an OAuth access token with the `tasks` scope (vault provider
`google_tasks`, sharing the Google refresh infrastructure with
`google_calendar`). The default task list is resolved from
tasklists.list — the API's `@default` alias is undocumented, so the
first list is used explicitly. Due dates are RFC3339; the API keeps
only the date part.
"""
import time
import uuid as _uuid
from typing import Any

from .github_connector import load_provider_token

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

TASKS_API = "https://tasks.googleapis.com/tasks/v1"


class GoogleTasksConnector(BaseConnector):
    """Executes action items as Google Tasks entries."""

    @property
    def tool_name(self) -> str:
        return "google_tasks"

    async def _get_token(self) -> str | None:
        # The Google bundle: a tasks-scoped token under its own provider
        # row, falling back to the calendar token (works when the
        # operator's grant bundled both scopes).
        return (
            await load_provider_token("google_tasks")
            or await load_provider_token("google_calendar")
        )

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
            title = (
                payload.get("title")
                or payload.get("summary")
                or payload.get("content")
                or payload.get("description")
                or "Untitled task"
            )
            notes = payload.get("notes") or payload.get("description") or ""
            due = payload.get("due_date")

            if sandbox_mode:
                fake_id = _uuid.uuid4().hex[:12]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url="https://tasks.google.com/embed/list/~" + fake_id,
                    latency_ms=int((time.time() - start_time) * 1000) + 55,
                    raw_response={"id": fake_id, "title": title, "mode": "sandbox"},
                )

            token = await self._get_token()
            if not token:
                raise ValueError(
                    "Google Tasks execution failed: no tasks-scoped token. "
                    "Connect a Google credential with the tasks scope in "
                    "Settings or enable Sandbox Mode."
                )

            headers = {"Authorization": "Bearer " + token}
            async with connector_http_client(timeout=15.0) as client:
                # Resolve the operator's first task list explicitly —
                # the @default alias is an undocumented convention.
                lists_resp = await client.get(
                    TASKS_API + "/users/@me/lists",
                    headers=headers,
                )
                if not lists_resp.is_success:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=int((time.time() - start_time) * 1000),
                        error="Google Tasks lists HTTP " + str(lists_resp.status_code),
                    )
                items = lists_resp.json().get("items", [])
                list_id = payload.get("tasklist_id") or (
                    items[0].get("id") if items else None
                )
                if not list_id:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=int((time.time() - start_time) * 1000),
                        error="Google Tasks: no task list found for this account.",
                    )

                task_body: dict[str, Any] = {
                    "title": title[:1024],
                    "notes": notes[:8192],
                    "status": "needsAction",
                }
                if due:
                    # Keep the date component; Tasks discards times.
                    task_body["due"] = str(due)[:10] + "T00:00:00.000Z"

                resp = await client.post(
                    TASKS_API + "/lists/" + str(list_id) + "/tasks",
                    json=task_body,
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json()
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url="https://tasks.google.com/embed/list/~" + str(data.get("id", "")),
                        latency_ms=latency_ms,
                        raw_response={
                            "id": data.get("id"),
                            "title": data.get("title"),
                            "status": data.get("status"),
                        },
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error="Google Tasks API HTTP " + str(resp.status_code),
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
