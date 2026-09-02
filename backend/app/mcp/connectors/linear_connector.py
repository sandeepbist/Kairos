"""Linear Connector: creates issues via the Linear GraphQL API.

Auth: a linear API key (settings UI / vault provider `linear`, or
LINEAR_API_KEY env). Linear's GraphQL endpoint is stable and the
issue-creation surface is small: team id (required by GraphQL) is
resolved from the key's visible teams, defaulting to the first.
"""
import os
import time
from typing import Any

from sqlalchemy import select

from app.core.security import decrypt_token
from app.db.models import OAuthTokenModel
from app.db.session import async_session_factory

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

LINEAR_ENDPOINT = "https://api.linear.app/graphql"

_CREATE_ISSUE = """
mutation CreateIssue($teamId: String!, $title: String!, $description: String!, $priority: Int) {
  issueCreate(input: {teamId: $teamId, title: $title, description: $description, priority: $priority}) {
    success
    issue { id url identifier title }
  }
}
"""


class LinearConnector(BaseConnector):
    """Executes action items as Linear issues."""

    @property
    def tool_name(self) -> str:
        return "linear"

    async def _get_api_key(self) -> str | None:
        async with async_session_factory() as session:
            res = await session.execute(
                select(OAuthTokenModel).where(OAuthTokenModel.provider == "linear")
            )
            rec = res.scalar_one_or_none()
            if rec and rec.access_token_enc:
                return decrypt_token(rec.access_token_enc)
        return os.getenv("LINEAR_API_KEY")

    async def health_check(self) -> bool:
        key = await self._get_api_key()
        return bool(key and key.strip())

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
                or "Untitled Linear issue"
            )
            description = payload.get("description") or payload.get("notes") or ""
            priority_map = {"low": 1, "medium": 2, "high": 3}
            priority = priority_map.get(str(payload.get("priority", "medium")).lower(), 2)

            if sandbox_mode:
                import uuid as _uuid

                fake_id = _uuid.uuid4().hex[:12]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=f"https://linear.app/team/issue/ENG-{fake_id}",
                    latency_ms=int((time.time() - start_time) * 1000) + 70,
                    raw_response={
                        "id": fake_id,
                        "identifier": f"ENG-{fake_id[:6].upper()}",
                        "title": title,
                        "mode": "sandbox",
                    },
                )

            api_key = await self._get_api_key()
            if not api_key:
                raise ValueError(
                    "Linear execution failed: no API key configured. "
                    "Add a Linear API key in Settings or enable Sandbox Mode."
                )

            headers = {"Authorization": api_key, "Content-Type": "application/json"}
            async with connector_http_client(timeout=15.0) as client:
                # Resolve the target team (first visible) once per execution.
                teams = await client.post(
                    LINEAR_ENDPOINT,
                    json={"query": "query Teams { teams { nodes { id name } } }"},
                    headers=headers,
                )
                if not teams.is_success:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=int((time.time() - start_time) * 1000),
                        error=f"Linear teams query HTTP {teams.status_code}",
                    )
                nodes = teams.json().get("data", {}).get("teams", {}).get("nodes", [])
                team_id = (nodes[0]["id"] if nodes else None) or payload.get("team_id")
                if not team_id:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=int((time.time() - start_time) * 1000),
                        error="Linear: no visible team for this API key.",
                    )

                resp = await client.post(
                    LINEAR_ENDPOINT,
                    json={
                        "query": _CREATE_ISSUE,
                        "variables": {
                            "teamId": team_id,
                            "title": title[:500],
                            "description": description[:5000],
                            "priority": priority,
                        },
                    },
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    body = resp.json()
                    data = body.get("data", {}) or {}
                    issue = (data.get("issueCreate") or {}).get("issue") or {}
                    if issue:
                        return ExecutionResult(
                            tool=self.tool_name,
                            status="success",
                            external_url=issue.get("url"),
                            latency_ms=latency_ms,
                            raw_response=issue,
                        )
                    errs = body.get("errors") or [{"message": "issueCreate returned no issue"}]
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=latency_ms,
                        error=f"Linear GraphQL error: {errs[0].get('message', 'unknown')}",
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error=f"Linear API HTTP {resp.status_code}",
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
