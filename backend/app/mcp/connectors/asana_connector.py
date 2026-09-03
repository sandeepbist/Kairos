"""Asana Connector: creates tasks via the Asana REST API v1.0.

Auth: an operator personal access token (settings UI / vault provider
`asana`, or ASANA_API_TOKEN env) generated instantly in the Asana
developer console — no OAuth flow needed.

Asana requires every task to live in a workspace: the connector
resolves the operator's first workspace via /workspaces when no
workspace or project gid is supplied in the payload. Responses wrap
the entity in a `data` object; permalink_url is an opt_field.
"""
import os
import time
import uuid as _uuid
from typing import Any

from .github_connector import load_provider_token

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

ASANA_API = "https://app.asana.com/api/1.0"


class AsanaConnector(BaseConnector):
    """Executes action items as Asana tasks."""

    @property
    def tool_name(self) -> str:
        return "asana"

    async def _get_token(self) -> str | None:
        return await load_provider_token("asana") or os.getenv("ASANA_API_TOKEN")

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
            notes = payload.get("notes") or payload.get("description") or ""
            due_on = payload.get("due_date")
            project_gid = payload.get("project_gid") or payload.get("project")
            workspace_gid = payload.get("workspace_gid") or payload.get("workspace")

            if sandbox_mode:
                fake_gid = _uuid.uuid4().hex[:12]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url="https://app.asana.com/0/"
                    + str(project_gid or "0") + "/" + fake_gid,
                    latency_ms=int((time.time() - start_time) * 1000) + 70,
                    raw_response={"gid": fake_gid, "name": name, "mode": "sandbox"},
                )

            token = await self._get_token()
            if not token:
                raise ValueError(
                    "Asana execution failed: no PAT configured. "
                    "Add an Asana token in Settings or enable Sandbox Mode."
                )

            headers = {"Authorization": "Bearer " + token}
            async with connector_http_client(timeout=15.0) as client:
                # Tasks must land in a workspace. A project gid implies
                # one; otherwise resolve the operator's first workspace.
                if not (project_gid or workspace_gid):
                    ws_resp = await client.get(
                        ASANA_API + "/workspaces", headers=headers,
                    )
                    if ws_resp.is_success:
                        entries = ws_resp.json().get("data", [])
                        workspace_gid = (
                            entries[0].get("gid") if entries else None
                        )
                    if not workspace_gid:
                        return ExecutionResult(
                            tool=self.tool_name,
                            status="failed",
                            latency_ms=int((time.time() - start_time) * 1000),
                            error="Asana: no visible workspace for this token.",
                        )

                body: dict[str, Any] = {
                    "name": name[:1024],
                    "notes": notes[:60000],
                }
                if project_gid:
                    body["projects"] = [str(project_gid)[:32]]
                if workspace_gid:
                    body["workspace"] = str(workspace_gid)[:32]
                if due_on:
                    # Asana takes YYYY-MM-DD; keep the date component.
                    body["due_on"] = str(due_on)[:10]

                resp = await client.post(
                    ASANA_API + "/tasks",
                    # permalink_url is opt-in on this endpoint.
                    params={"opt_fields": "permalink_url,name"},
                    json={"data": body},
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json().get("data", {})
                    url = data.get("permalink_url") or (
                        "https://app.asana.com/0/" + str(data.get("gid", ""))
                    )
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=url,
                        latency_ms=latency_ms,
                        raw_response={
                            "gid": data.get("gid"),
                            "name": data.get("name"),
                        },
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error="Asana API HTTP " + str(resp.status_code),
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
