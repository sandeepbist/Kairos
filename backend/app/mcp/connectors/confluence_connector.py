"""Confluence Connector: creates pages via the Atlassian remote MCP
server (mcp.atlassian.com/v2/mcp).

MCP-only by design: the Rovo server's `createConfluenceContent`
handles page creation with dynamic schemas (cloudId/spaceId
resolution), so no REST leg is needed. Reuses the same Atlassian
credential the operator configured for Jira — one vault row powers
both tools. Sandbox mode fabricates a plausible wiki URL.
"""
import os
import time
import uuid as _uuid
from typing import Any

from .github_connector import load_provider_token

from .base import BaseConnector, ExecutionResult
from .mcp_transport import execute_via_mcp


class ConfluenceConnector(BaseConnector):
    """Executes action items as Confluence pages."""

    @property
    def tool_name(self) -> str:
        return "confluence_page"

    async def _get_token(self) -> str | None:
        # Same Atlassian credential as the Jira connector.
        return (
            await load_provider_token("jira")
            or await load_provider_token("confluence")
            or os.getenv("ATLASSIAN_API_TOKEN")
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
                or payload.get("description")
                or "Untitled page"
            )
            content = (
                payload.get("content")
                or payload.get("details")
                or payload.get("description")
                or ""
            )
            space_key = payload.get("space_key") or payload.get("space_id")

            if sandbox_mode:
                fake_id = _uuid.uuid4().hex[:8]
                space = space_key or "TEAM"
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url="https://kairos-sandbox.atlassian.com/wiki/spaces/"
                    + str(space) + "/pages/" + fake_id,
                    latency_ms=int((time.time() - start_time) * 1000) + 80,
                    raw_response={
                        "page_id": fake_id,
                        "title": title,
                        "mode": "sandbox",
                    },
                )

            token = await self._get_token()
            if not space_key:
                raise ValueError(
                    "Confluence execution failed: no target space. Set space_key "
                    "in the action payload."
                )
            if not token:
                raise ValueError(
                    "Confluence execution failed: no Atlassian credential. "
                    "Connect Jira (same credential) or set ATLASSIAN_API_TOKEN, "
                    "or enable Sandbox Mode."
                )

            # MCP dispatch: createConfluenceContent on the v2 server.
            # The tool resolves cloudId itself for workspace-scoped tokens;
            # spaceKey identifies the destination space.
            mcp_result = await execute_via_mcp(
                "confluence_page", token, {
                    "title": title[:255],
                    "spaceKey": str(space_key)[:60],
                    "content": content[:30000] if content else title,
                    "type": "page",
                }
            )
            if mcp_result and mcp_result.get("success"):
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=str(mcp_result.get("url") or ""),
                    latency_ms=int((time.time() - start_time) * 1000),
                    raw_response={"transport": "mcp", **mcp_result},
                )
            detail = (mcp_result or {}).get("error") or "MCP dispatch returned no result"
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error="Confluence MCP: " + str(detail),
            )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
