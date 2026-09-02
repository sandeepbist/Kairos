"""Tier-2 sink connector tests: GitHub, Confluence, Google Tasks."""

import pytest

# Fixture value for a fake provider token; never a real credential.
_TEST_PAT_PLACEHOLDER = "test-token-" + str(0) * 12

from app.mcp.client_manager import mcp_client_manager


def test_tier2_tools_registered():
    """All three tier-2 tools resolve through the manager registry."""
    for tool in ("github", "confluence_page", "google_tasks"):
        connector = mcp_client_manager.get_connector(tool)
        assert connector.tool_name == tool


def test_tier2_mcp_endpoint_map():
    """The MCP transport carries the GitHub + Confluence endpoints and
    the current tool-name alternates."""
    from app.mcp.connectors.mcp_transport import MCP_REMOTE_ENDPOINTS, MCP_TOOL_NAMES

    assert MCP_REMOTE_ENDPOINTS["github"] == "https://api.githubcopilot.com/mcp/"
    assert MCP_REMOTE_ENDPOINTS["confluence_page"] == "https://mcp.atlassian.com/v2/mcp"
    assert MCP_TOOL_NAMES["jira"][0] == "createJiraIssue"
    assert MCP_TOOL_NAMES["github"][0] == "issue_write"


@pytest.mark.asyncio
async def test_github_live_requires_repo():
    """Without a target repository the connector fails with a clear
    message pointing at the payload/env configuration."""
    connector = mcp_client_manager.get_connector("github")
    run = connector.execute
    result = await run({"title": "No repo given"})
    assert result.status == "failed"
    assert "repository" in (result.error or "")


@pytest.mark.asyncio
async def test_confluence_live_requires_space():
    connector = mcp_client_manager.get_connector("confluence_page")
    run = connector.execute
    result = await run({"title": "No space given"})
    assert result.status == "failed"
    assert "space" in (result.error or "").lower()


class _FakeResp:
    is_success = True
    status_code = 201

    def json(self):
        return {"id": 1, "number": 7, "html_url": "https://github.com/a/b/issues/7"}


class _FakeClient:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        self.sink.update(json or {})
        return _FakeResp()


@pytest.mark.asyncio
async def test_github_labels_string_form_normalized():
    """The review UI edits labels as a comma string; the connector
    normalizes both forms before the API call."""
    from unittest.mock import patch

    captured: dict = {}

    import app.mcp.connectors.github_connector as gc

    async def fake_token(self):
        return _TEST_PAT_PLACEHOLDER

    with patch.object(
        gc.GitHubConnector, "_get_token", fake_token
    ), patch.object(
        gc, "connector_http_client", lambda timeout=15.0: _FakeClient(captured)
    ):
        connector = gc.GitHubConnector()
        run = connector.execute
        result = await run({"title": "T", "repo": "a/b", "labels": "kairos, bug"})
    assert result.status == "success", result.error
    assert captured["labels"] == ["kairos", "bug"]


@pytest.mark.asyncio
async def test_google_tasks_live_requires_token():
    """Without any Google credential the failure is explicit, never a crash."""
    from unittest.mock import patch

    import app.mcp.connectors.google_tasks_connector as gt

    async def no_token(self):
        return None

    with patch.object(gt.GoogleTasksConnector, "_get_token", no_token):
        connector = gt.GoogleTasksConnector()
        run = connector.execute
        result = await run({"title": "T"})
    assert result.status == "failed"
    assert "token" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_confluence_mcp_success_path():
    """When the remote MCP dispatch returns a result, the connector
    wraps it as a success with the transport recorded."""
    from unittest.mock import patch

    import app.mcp.connectors.confluence_connector as cc

    async def fake_mcp(tool, token, payload):
        return {
            "success": True,
            "url": "https://acme.atlassian.com/wiki/spaces/TEAM/pages/998",
        }

    async def fake_token(self):
        return _TEST_PAT_PLACEHOLDER

    with patch.object(cc, "execute_via_mcp", fake_mcp), patch.object(
        cc.ConfluenceConnector, "_get_token", fake_token
    ):
        connector = cc.ConfluenceConnector()
        run = connector.execute
        result = await run(
            {"title": "Decision log", "space_key": "TEAM", "content": "We chose Postgres."},
        )
    assert result.status == "success"
    assert "atlassian.com/wiki" in (result.external_url or "")
    assert result.raw_response.get("transport") == "mcp"
