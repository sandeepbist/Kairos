"""MCP remote transport: real Model Context Protocol dispatch for external tools.

When a connector has an OAuth access token (rather than a static API key),
executions travel over genuine MCP transport to the vendor's GA remote
server — Notion (mcp.notion.com/mcp) and Atlassian (mcp.atlassian.com/v2/mcp)
both being Generally Available as of 2026. Static-key holders continue on
REST (the existing connectors), selected automatically at dispatch time:
same BaseConnector interface, best transport the credential supports.

Design notes:
- Session-per-execution: Kairos executes at human speed (a few times a
  minute at most), and per-execution sessions dodge remote-server session
  expiry entirely. The 2026-07-28 spec made the protocol stateless, so
  there is no initialize handshake to amortize.
- Falls back to REST on ANY transport failure (connect errors, tool errors)
  — an MCP outage must not block an approved action. The retry transport
  inside the REST connectors handles transient HTTP failures.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# GA remote MCP endpoints per vendor docs (verified reachable 2026-09).
MCP_REMOTE_ENDPOINTS: dict[str, str] = {
    "notion": "https://mcp.notion.com/mcp",
    "jira": "https://mcp.atlassian.com/v2/mcp",
}

# Tool names on the remote servers that map to Kairos executions.
# The dispatch tries each in order; vendors evolve tool surfaces over time,
# so alternates are listed per action.
MCP_TOOL_NAMES: dict[str, list[str]] = {
    "notion": ["notion_create_page", "create_page"],
    "jira": ["jira_create_issue", "create_issue"],
}


async def execute_via_mcp(
    tool: str,
    access_token: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Dispatch one execution over real MCP transport.

    Returns the tool result's structured content on success, or None when
    anything fails — the caller falls back to REST without surfacing the
    MCP attempt to the operator (logged at debug level; an MCP outage is
    not an action failure while REST still works).
    """
    endpoint = MCP_REMOTE_ENDPOINTS.get(tool)
    if not endpoint or not access_token:
        return None

    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with streamable_http_client(endpoint) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                for tool_name in MCP_TOOL_NAMES[tool]:
                    result = await session.call_tool(
                        tool_name,
                        arguments=_mcp_arguments(tool, payload),
                    )
                    if not result.is_error:
                        content = getattr(result, "structured_content", None)
                        if isinstance(content, dict):
                            return content
                logger.debug(
                    "MCP dispatch for %s produced no usable result; REST will run.",
                    tool,
                )
                return None
    except Exception as e:  # noqa: BLE001 — any MCP failure means REST fallback
        logger.debug("MCP transport for %s failed (%s); REST fallback.", tool, e)
        return None


def _mcp_arguments(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Maps a Kairos tool payload to the remote MCP tool arguments.

    The remote tools accept near-identical shapes; the mapping below
    normalizes the few field-name differences.
    """
    if tool == "notion":
        return {
            "title": (payload.get("title") or payload.get("summary") or "Untitled page")[:2000],
            "content": payload.get("details") or payload.get("description") or "",
        }
    if tool == "jira":
        return {
            "summary": (payload.get("summary") or payload.get("title") or "Untitled issue")[:255],
            "description": payload.get("description") or "",
            "issue_type": payload.get("issue_type", "Task"),
            "project_key": payload.get("project_key", "PROJ"),
        }
    return dict(payload)
