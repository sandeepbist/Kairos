"""Tier-2 sink connector tests: GitHub, Confluence, Google Tasks, Asana, ClickUp."""

import pytest

# Fixture value for a fake provider token; never a real credential.
_TEST_PAT_PLACEHOLDER = "test-token-" + str(0) * 12

from app.mcp.client_manager import mcp_client_manager


def test_tier2_tools_registered():
    """All five tier-2 tools resolve through the manager registry."""
    for tool in ("github", "confluence_page", "google_tasks", "asana", "clickup"):
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


# ---------------------------------------------------------
# Asana
# ---------------------------------------------------------

class _FakeAsanaResp:
    is_success = True
    status_code = 201

    def json(self):
        return {
            "data": {
                "gid": "12001",
                "name": "Supplier audit follow-up",
                "permalink_url": "https://app.asana.com/0/1/12001",
            }
        }


class _FakeAsanaWorkspaces:
    is_success = True
    status_code = 200

    def json(self):
        return {"data": [{"gid": "98765", "name": "Main Workspace"}]}


class _FakeAsanaClient:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers=None):
        return _FakeAsanaWorkspaces()

    async def post(self, url, json=None, headers=None, params=None):
        self.sink.update(json or {})
        self.sink["_last_url"] = url
        self.sink["_params"] = params
        return _FakeAsanaResp()


@pytest.mark.asyncio
async def test_asana_creates_task_with_resolved_workspace():
    """Without project/workspace gids the connector resolves the first
    workspace, wraps the body in Asana's data envelope, and requests
    permalink_url via opt_fields."""
    from unittest.mock import patch

    captured: dict = {}

    import app.mcp.connectors.asana_connector as ac

    async def fake_token(self):
        return _TEST_PAT_PLACEHOLDER

    with patch.object(
        ac.AsanaConnector, "_get_token", fake_token
    ), patch.object(
        ac, "connector_http_client", lambda timeout=15.0: _FakeAsanaClient(captured)
    ):
        connector = ac.AsanaConnector()
        run = connector.execute
        result = await run(
            {"name": "Supplier audit follow-up", "notes": "From the call"},
        )
    assert result.status == "success", result.error
    assert result.external_url == "https://app.asana.com/0/1/12001"
    assert captured["data"]["workspace"] == "98765"
    assert "projects" not in captured["data"]
    assert captured["_params"]["opt_fields"] == "permalink_url,name"


@pytest.mark.asyncio
async def test_asana_project_gid_beats_workspace_resolution():
    """A project gid implies its workspace; no workspace lookup happens."""
    from unittest.mock import patch

    import app.mcp.connectors.asana_connector as ac

    async def fake_token(self):
        return _TEST_PAT_PLACEHOLDER

    with patch.object(
        ac.AsanaConnector, "_get_token", fake_token
    ), patch.object(
        ac, "connector_http_client", lambda timeout=15.0: _FakeAsanaClient({})
    ):
        connector = ac.AsanaConnector()
        run = connector.execute
        result = await run({"name": "T", "project_gid": "555"})
    assert result.status == "success", result.error


@pytest.mark.asyncio
async def test_asana_sandbox_and_no_token_paths():
    connector = mcp_client_manager.get_connector("asana")
    run = connector.execute
    sandboxed = await run({"name": "Audit"}, sandbox_mode=True)
    assert sandboxed.status == "success"
    assert "app.asana.com" in (sandboxed.external_url or "")

    live = await run({"name": "Audit"})
    assert live.status == "failed"
    assert "token" in (live.error or "").lower()


# ---------------------------------------------------------
# ClickUp
# ---------------------------------------------------------

class _FakeClickUpResp:
    is_success = True
    status_code = 200

    def json(self):
        return {
            "id": "abc123",
            "name": "Onboarding checklist revamp",
            "url": "https://app.clickup.com/t/1/abc123",
        }


class _FakeClickUpClient:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        self.sink.update(json or {})
        self.sink["_last_url"] = url
        self.sink["_headers"] = headers
        return _FakeClickUpResp()


@pytest.mark.asyncio
async def test_clickup_creates_task_on_named_list():
    """The personal token goes in the Authorization header bare (ClickUp's
    contract — no Bearer prefix) and priority maps to ClickUp's levels."""
    from unittest.mock import patch

    captured: dict = {}

    import app.mcp.connectors.clickup_connector as cuc

    async def fake_token(self):
        return _TEST_PAT_PLACEHOLDER

    with patch.object(
        cuc.ClickUpConnector, "_get_token", fake_token
    ), patch.object(
        cuc, "connector_http_client", lambda timeout=15.0: _FakeClickUpClient(captured)
    ):
        connector = cuc.ClickUpConnector()
        run = connector.execute
        result = await run(
            {"name": "Onboarding checklist revamp", "list_id": "901", "priority": "high"},
        )
    assert result.status == "success", result.error
    assert result.external_url == "https://app.clickup.com/t/1/abc123"
    assert captured["_last_url"].endswith("/list/901/task")
    assert captured["_headers"]["Authorization"] == _TEST_PAT_PLACEHOLDER
    assert captured["priority"] == 2  # high → ClickUp urgent-adjacent level


@pytest.mark.asyncio
async def test_clickup_requires_list():
    """No list id in payload or env → specific error, never a crash."""
    import os

    connector = mcp_client_manager.get_connector("clickup")
    saved = os.environ.pop("CLICKUP_TARGET_LIST", None)
    try:
        run = connector.execute
        result = await run({"name": "No list"})
        assert result.status == "failed"
        assert "list" in (result.error or "").lower()
    finally:
        if saved is not None:
            os.environ["CLICKUP_TARGET_LIST"] = saved


@pytest.mark.asyncio
async def test_new_tools_keyword_routing():
    """Extractor routes Asana/ClickUp intent correctly."""
    from app.pipelines.extract import deterministic_fallback_extractor as dfe

    items = dfe(
        "Nadia: Log the supplier audit follow-up in Asana by Friday.",
        "meeting_transcript",
    )
    assert any(i["suggested_tool"] == "asana" for i in items)

    items2 = dfe(
        "Omar: Put the onboarding checklist revamp on our ClickUp list.",
        "meeting_transcript",
    )
    assert any(i["suggested_tool"] == "clickup" for i in items2)


class _StatusResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.is_success = 200 <= status < 300
        self._payload = payload or {}

    def json(self):
        return self._payload


class _SeqClient:
    """Fake client replaying canned responses in order, capturing posts."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers=None):
        return self.responses.pop(0)

    async def post(self, url, json=None, headers=None, data=None):
        self.posts.append({"url": url, "json": json, "data": data})
        return self.responses.pop(0)


async def _seeded_token(self):
    return "test-token"


@pytest.mark.asyncio
async def test_asana_workspaces_failure_reports_status():
    """A failing workspaces call must surface its HTTP status, not the
    generic 'no visible workspace' message."""
    import app.mcp.connectors.asana_connector as ac

    orig_client = ac.connector_http_client
    orig_token = ac.AsanaConnector._get_token
    ac.connector_http_client = lambda timeout=15.0: _SeqClient(
        [_StatusResp(401, {"errors": [{"message": "Not Authorized"}]})]
    )
    ac.AsanaConnector._get_token = _seeded_token
    try:
        res = await ac.AsanaConnector().execute({"name": "x"}, sandbox_mode=False)
        assert res.status == "failed"
        assert "401" in (res.error or "")
    finally:
        ac.connector_http_client = orig_client
        ac.AsanaConnector._get_token = orig_token


@pytest.mark.asyncio
async def test_clickup_missing_url_falls_back_to_deep_link():
    """ClickUp list-task responses often omit url: success must still
    carry a clickable link."""
    import app.mcp.connectors.clickup_connector as cc

    orig_client = cc.connector_http_client
    orig_token = cc.ClickUpConnector._get_token
    cc.connector_http_client = lambda timeout=15.0: _SeqClient(
        [_StatusResp(200, {"id": "abc123", "name": "x"})]
    )
    cc.ClickUpConnector._get_token = _seeded_token
    try:
        res = await cc.ClickUpConnector().execute(
            {"name": "x", "list_id": "123"}, sandbox_mode=False
        )
        assert res.status == "success"
        assert res.external_url == "https://app.clickup.com/t/abc123"
    finally:
        cc.connector_http_client = orig_client
        cc.ClickUpConnector._get_token = orig_token


@pytest.mark.asyncio
async def test_email_recipients_join_lists():
    """List-form to/cc normalize to comma strings instead of Python
    reprs that the Gmail API would reject."""
    import base64
    import app.mcp.connectors.email_draft_connector as ec

    orig_client = ec.connector_http_client
    orig_token = ec.EmailDraftConnector._get_token
    clients = []
    seq = _SeqClient([_StatusResp(200, {"id": "draft1"})])
    clients.append(seq)
    ec.connector_http_client = lambda timeout=15.0: seq
    ec.EmailDraftConnector._get_token = _seeded_token
    try:
        res = await ec.EmailDraftConnector().execute(
            {"subject": "s", "body": "b",
             "to": ["a@x.co", "b@x.co"], "cc": ["c@x.co"]},
            sandbox_mode=False,
        )
        assert res.status == "success"
        raw = seq.posts[0]["json"]["message"]["raw"]
        mime = base64.urlsafe_b64decode(raw).decode()
        assert "a@x.co, b@x.co" in mime and "c@x.co" in mime
        assert "['a@x.co'" not in mime
    finally:
        ec.connector_http_client = orig_client
        ec.EmailDraftConnector._get_token = orig_token


@pytest.mark.asyncio
async def test_google_tasks_rejects_garbage_due_date():
    """Non-date due values fail with a named error instead of a sliced
    guess the API refuses opaquely (connector convention: failed result,
    not a raise)."""
    import app.mcp.connectors.google_tasks_connector as gc

    orig_client = gc.connector_http_client
    orig_token = gc.GoogleTasksConnector._get_token
    seq = _SeqClient([_StatusResp(200, {"items": [{"id": "list1"}]})])
    gc.connector_http_client = lambda timeout=15.0: seq
    gc.GoogleTasksConnector._get_token = _seeded_token
    try:
        res = await gc.GoogleTasksConnector().execute(
            {"title": "x", "due_date": "next Friday-ish"},
            sandbox_mode=False,
        )
        assert res.status == "failed"
        assert "due_date" in (res.error or "")
        assert seq.posts == []  # rejected before any task POST
    finally:
        gc.connector_http_client = orig_client
        gc.GoogleTasksConnector._get_token = orig_token


@pytest.mark.asyncio
async def test_github_dict_labels_fall_back_to_configured():
    """Non-string, non-list labels would 422 at GitHub; they fall back
    to the operator's configured set instead."""
    import app.mcp.connectors.github_connector as gc

    captured = {}

    class FakeResp:
        is_success = True
        status_code = 201

        def json(self):
            return {"id": 9, "number": 3, "html_url": "https://github.com/a/b/issues/3"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, json=None, headers=None):
            captured.update(json or {})
            return FakeResp()

    orig_client = gc.connector_http_client
    orig_token = gc.GitHubConnector._get_token
    gc.connector_http_client = lambda timeout=15.0: FakeClient()
    gc.GitHubConnector._get_token = _seeded_token
    try:
        res = await gc.GitHubConnector().execute(
            {"title": "x", "repo": "a/b", "labels": {"weird": "dict"}},
            sandbox_mode=False,
        )
        assert res.status == "success"
        assert isinstance(captured.get("labels"), list)
    finally:
        gc.connector_http_client = orig_client
        gc.GitHubConnector._get_token = orig_token
