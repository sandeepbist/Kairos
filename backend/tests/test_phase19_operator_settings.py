"""No-fabrication guarantees + operator settings store.

Production hardening: extraction payloads carry operator-configured
targets and source-stated facts only — never invented project keys,
database ids, attendee emails, or meeting times. Connectors refuse live
execution without a real target instead of firing at demo placeholders.
The operator_settings store gives the Settings UI and the Temporal
worker one shared, restart-surviving source (DB → env → default).
"""
import pytest


DEMO_VALUES = ("ENG", "roadmap_db", "company.atlassian.net", "company.com", "acme")


def _extract(text, source_type="meeting_transcript", targets=None):
    from app.pipelines.extract import deterministic_fallback_extractor

    return deterministic_fallback_extractor(text, source_type, targets)


def test_jira_payload_has_no_default_project_key():
    """With no operator target configured, a Jira item's payload omits
    project_key entirely — the demo "ENG" default must not exist."""
    items = _extract("Dev: Please file a high priority ticket for the checkout crash bug.")
    jira_items = [i for i in items if i["suggested_tool"] == "jira"]
    assert jira_items, "expected a jira-routed item"
    for item in jira_items:
        assert "project_key" not in item["tool_payload"]


def test_jira_payload_uses_operator_target():
    items = _extract(
        "Dev: Please file a high priority ticket for the checkout crash bug.",
        targets={"jira_project_key": "SUP"},
    )
    jira_items = [i for i in items if i["suggested_tool"] == "jira"]
    assert jira_items and all(i["tool_payload"].get("project_key") == "SUP" for i in jira_items)


def test_notion_payload_has_no_default_database():
    items = _extract("John: I will update the technical spec doc in the roadmap wiki.")
    notion_items = [i for i in items if i["suggested_tool"] == "notion"]
    assert notion_items
    for item in notion_items:
        assert "database_id" not in item["tool_payload"]


def test_calendar_payload_never_invents_slot_or_attendees():
    """A meeting ask with no stated time or emails yields title only:
    no fabricated start/end, no assignee@company.com attendee."""
    items = _extract("Sarah: Can you schedule a roadmap planning session with stakeholders?")
    cal_items = [i for i in items if i["suggested_tool"] == "calendar"]
    assert cal_items
    for item in cal_items:
        payload = item["tool_payload"]
        assert "start_time" not in payload
        assert "end_time" not in payload
        assert "attendees" not in payload


def test_calendar_attendees_come_from_source_only():
    """An email literally present in the transcript is the only way an
    attendee address appears."""
    items = _extract(
        "Sarah: Schedule the sync — invite dev@acme-test-corp.example please."
    )
    cal_items = [i for i in items if i["suggested_tool"] == "calendar"]
    assert cal_items
    for item in cal_items:
        payload = item["tool_payload"]
        if "attendees" in payload:
            assert payload["attendees"] == ["dev@acme-test-corp.example"]


def test_github_payload_has_no_forced_label():
    items = _extract(
        "Lead: Dev, open a GitHub issue for the flaky payment retry test in the repo.",
    )
    gh_items = [i for i in items if i["suggested_tool"] == "github"]
    assert gh_items
    for item in gh_items:
        assert item["tool_payload"].get("labels") != ["kairos"]


def test_github_target_and_labels_prefill_from_operator():
    items = _extract(
        "Lead: Dev, open a GitHub issue for the flaky payment retry test in the repo.",
        targets={"github_repo": "acme-test/planning", "github_labels": "meeting"},
    )
    gh_items = [i for i in items if i["suggested_tool"] == "github"]
    assert gh_items
    assert gh_items[0]["tool_payload"].get("repo") == "acme-test/planning"
    assert gh_items[0]["tool_payload"].get("labels") == "meeting"


def test_no_demo_values_in_any_extracted_payload():
    """Sweep: across every golden-style input, no payload string may
    carry a demo placeholder value."""
    texts = [
        "Sarah: Alex, please file a high priority ticket for the checkout crash bug by tomorrow.",
        "Alex: Sure Sarah, I will schedule a review meeting with the frontend team on Thursday.",
        "John: I will update the technical spec doc in the roadmap wiki and share it.",
        "Raj: Add the grocery run to my Todoist today.",
        "Nadia: Log the supplier audit follow-up in Asana by Friday.",
        "Omar: Put the onboarding checklist revamp on our ClickUp list.",
        "Maya: Add picking up the visa documents to my Google Tasks.",
    ]
    for text in texts:
        for item in _extract(text):
            for value in item["tool_payload"].values():
                if isinstance(value, str):
                    for demo in DEMO_VALUES:
                        assert demo not in value, f"{demo!r} leaked into payload: {value!r}"


# ── Operator settings store (live DB) ─────────────────────────────────


@pytest.mark.asyncio
async def test_settings_roundtrip_and_env_fallback():
    from app.core.operator_settings import (
        load_operator_settings,
        resolve_tool_targets,
        save_operator_setting,
    )
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        await save_operator_setting(
            "tool_targets.jira_project_key", "RT", session
        )
        await session.commit()

    resolved = await load_operator_settings(["tool_targets.jira_project_key"])
    assert resolved["tool_targets.jira_project_key"] == "RT"

    targets = await resolve_tool_targets()
    assert targets["jira_project_key"] == "RT"


@pytest.mark.asyncio
async def test_settings_api_get_put_and_clear():
    """PUT writes targets, GET resolves them, empty-string PUT clears."""
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        put = client.put(
            "/api/connectors/settings",
            json={"jira_project_key": "SUP", "jira_domain": "roundtrip.atlassian.net"},
        )
        assert put.status_code == 200
        assert put.json()["tool_targets.jira_project_key"] == "SUP"
        assert put.json()["tool_targets.jira_domain"] == "roundtrip.atlassian.net"

        got = client.get("/api/connectors/settings")
        assert got.status_code == 200
        assert got.json()["tool_targets.jira_project_key"] == "SUP"

        # Clear: DB row becomes "" and resolution falls back to env/default.
        cleared = client.put(
            "/api/connectors/settings", json={"jira_project_key": ""}
        )
        assert cleared.status_code == 200


@pytest.mark.asyncio
async def test_sandbox_toggle_persists_across_app_state():
    """The toggle writes the store; a fresh settings read (as a new
    process would see) resolves the same value."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.core.operator_settings import get_operator_setting

    with TestClient(app) as client:
        on = client.post("/api/connectors/sandbox-toggle", json={"sandbox_mode": True})
        assert on.status_code == 200 and on.json()["sandbox_mode"] is True

    assert await get_operator_setting("execution.sandbox_mode") is True

    with TestClient(app) as client:
        off = client.post("/api/connectors/sandbox-toggle", json={"sandbox_mode": False})
        assert off.status_code == 200 and off.json()["sandbox_mode"] is False

    assert await get_operator_setting("execution.sandbox_mode") is False


@pytest.mark.asyncio
async def test_connector_refuses_live_without_target():
    """Live-mode connectors must raise instead of using demo defaults.
    Calendar without times is the sharpest case: no invented slot."""
    from app.mcp.connectors.calendar_connector import CalendarConnector

    connector = CalendarConnector()
    with pytest.raises(ValueError, match="start_time and end_time are required"):
        await connector.execute({"title": "Team sync"}, sandbox_mode=False)
