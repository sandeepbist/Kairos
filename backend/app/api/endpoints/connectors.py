"""Connectors API Endpoints: Health status, OAuth vault, and Sandbox toggles."""
from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import OAuthTokenModel
from app.core.security import encrypt_token
from app.core.operator_settings import (
    load_operator_settings,
    save_operator_setting,
)
from app.mcp.client_manager import mcp_client_manager

router = APIRouter(prefix="/connectors", tags=["connectors"])


class SaveOAuthTokenRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=50)
    access_token: str = Field(min_length=8, max_length=8_192)
    refresh_token: str | None = Field(default=None, max_length=8_192)
    scopes: str | None = Field(default=None, max_length=2_000)


class SandboxToggleRequest(BaseModel):
    sandbox_mode: bool


class ToolTargetsRequest(BaseModel):
    """Operator tool targets. All optional; empty string clears a key."""
    jira_project_key: str | None = Field(default=None, max_length=50)
    jira_domain: str | None = Field(default=None, max_length=200)
    jira_email: str | None = Field(default=None, max_length=320)
    notion_database_id: str | None = Field(default=None, max_length=100)
    github_repo: str | None = Field(default=None, max_length=200)
    github_labels: str | None = Field(default=None, max_length=200)
    confluence_space_key: str | None = Field(default=None, max_length=100)
    clickup_list_id: str | None = Field(default=None, max_length=100)
    asana_workspace: str | None = Field(default=None, max_length=100)


@router.get("/settings", response_model=dict[str, Any])
async def get_operator_settings():
    """Resolved operator settings (DB → env → empty) for the Settings UI."""
    return await load_operator_settings()


@router.put("/settings", response_model=dict[str, Any])
async def put_operator_settings(
    request: ToolTargetsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Persists tool targets to the operator_settings store.

    Only provided fields are written; empty strings clear a key so the
    env fallback (if any) takes over again.
    """
    field_to_key = {
        "jira_project_key": "tool_targets.jira_project_key",
        "jira_domain": "tool_targets.jira_domain",
        "jira_email": "tool_targets.jira_email",
        "notion_database_id": "tool_targets.notion_database_id",
        "github_repo": "tool_targets.github_repo",
        "github_labels": "tool_targets.github_labels",
        "confluence_space_key": "tool_targets.confluence_space_key",
        "clickup_list_id": "tool_targets.clickup_list_id",
        "asana_workspace": "tool_targets.asana_workspace",
    }
    for field, key in field_to_key.items():
        value = getattr(request, field)
        if value is not None:
            await save_operator_setting(key, value, db)
    await db.commit()
    return await load_operator_settings()


@router.get("/status", response_model=dict[str, Any])
async def get_connectors_status(
    db: AsyncSession = Depends(get_db),
):
    """Returns connector health, sandbox flags, and configured OAuth connections."""
    from app.core.operator_settings import get_operator_setting

    mcp_statuses = await mcp_client_manager.get_connectors_status()
    resolved_sandbox = bool(await get_operator_setting(
        "execution.sandbox_mode", default=settings.SANDBOX_MODE
    ))
    settings.SANDBOX_MODE = resolved_sandbox

    # Query configured OAuth tokens
    tokens_query = select(OAuthTokenModel.provider)
    result = await db.execute(tokens_query)
    connected_providers = set(result.scalars().all())

    # Vault provider aliases: a tool may authenticate via a differently
    # named provider credential (email_draft uses the gmail token;
    # confluence_page rides the jira/Atlassian credential; google_tasks
    # may share the calendar token when the grant bundled both scopes).
    tool_provider_aliases = {
        "calendar": {"google_calendar", "calendar"},
        "email_draft": {"gmail", "email_draft"},
        "confluence_page": {"jira", "confluence"},
        "google_tasks": {"google_tasks", "google_calendar"},
    }
    connectors_info = {}
    for tool_name, status_dict in mcp_statuses.items():
        aliases = tool_provider_aliases.get(tool_name, {tool_name})
        connected = bool(aliases & connected_providers) or tool_name == "task_ledger"
        connectors_info[tool_name] = {
            "healthy": status_dict["healthy"],
            "sandbox_mode": settings.SANDBOX_MODE,
            "oauth_connected": connected,
            "type": "custom_internal" if tool_name == "task_ledger" else "official_mcp",
        }

    llm_info = {
        "gemini": {
            "connected": bool("gemini" in connected_providers or "google_ai" in connected_providers or settings.GOOGLE_API_KEY),
            "model": settings.DEFAULT_MODEL_NAME,
        },
        "openai": {
            "connected": bool("openai" in connected_providers or settings.OPENAI_API_KEY),
            "model": "gpt-4o-mini",
        },
    }

    return {
        "sandbox_mode": settings.SANDBOX_MODE,
        "connectors": connectors_info,
        "llm_providers": llm_info,
    }


@router.post("/oauth/save", response_model=dict[str, str])
async def save_oauth_token(
    request: SaveOAuthTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Encrypts and stores user OAuth or LLM API credentials in Postgres vault."""
    provider = request.provider.lower().strip()
    valid_providers = [
        "notion", "jira", "google_calendar", "gmail", "linear", "todoist",
        "gemini", "google_ai", "openai", "github", "confluence", "google_tasks",
        "asana", "clickup",
    ]
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider '{provider}'. Valid options: {valid_providers}",
        )

    enc_access = encrypt_token(request.access_token)
    enc_refresh = encrypt_token(request.refresh_token) if request.refresh_token else None

    # Check if exists, update or insert
    existing_query = select(OAuthTokenModel).where(OAuthTokenModel.provider == provider)
    res = await db.execute(existing_query)
    token_record = res.scalar_one_or_none()

    if token_record:
        token_record.access_token_enc = enc_access
        token_record.refresh_token_enc = enc_refresh
        token_record.scopes = request.scopes
    else:
        new_record = OAuthTokenModel(
            provider=provider,
            access_token_enc=enc_access,
            refresh_token_enc=enc_refresh,
            scopes=request.scopes,
        )
        db.add(new_record)

    await db.commit()
    return {"status": "saved", "provider": provider}


@router.delete("/oauth/{provider}", response_model=dict[str, str])
async def delete_oauth_token(
    provider: str,
    db: AsyncSession = Depends(get_db),
):
    """Removes stored OAuth credentials for a provider from Postgres vault."""
    prov = provider.lower().strip()
    query = select(OAuthTokenModel).where(OAuthTokenModel.provider == prov)
    res = await db.execute(query)
    record = res.scalar_one_or_none()
    if record:
        await db.delete(record)
        await db.commit()
    return {"status": "deleted", "provider": prov}



@router.post("/sandbox-toggle", response_model=dict[str, Any])
async def toggle_sandbox_mode(
    request: SandboxToggleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Toggles Sandbox / Mock Mode for subsequently ingested batches.

    The mode is persisted in the operator_settings store (survives
    restarts, visible to the Temporal worker process) and captured per
    batch at ingest time, so it applies even though the worker runs
    separately. Env var SANDBOX_MODE seeds the initial value.
    """
    await save_operator_setting("execution.sandbox_mode", request.sandbox_mode, db)
    await db.commit()
    settings.SANDBOX_MODE = request.sandbox_mode
    return {
        "sandbox_mode": settings.SANDBOX_MODE,
        "message": (
            "Sandbox mode set to "
            f"{settings.SANDBOX_MODE} — applies to newly ingested batches."
        ),
    }


# Fixed Temporal Schedule ids (see setup_gmail_schedule/setup_slack_schedule).
_GMAIL_SCHEDULE_ID = "kairos-gmail-poll"
_SLACK_SCHEDULE_ID = "kairos-slack-listen"


async def _schedule_state(schedule_id: str) -> dict[str, Any]:
    """Describes one poller schedule, simplified to running/paused/missing.

    Uses the shared Temporal client; a missing (never armed or deleted)
    schedule surfaces as {"armed": False, "state": "missing"} instead of
    an error so the UI can always render both chips.
    """
    from temporalio.service import RPCError, RPCStatusCode

    from app.temporal.worker import get_temporal_client

    try:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(schedule_id)
        desc = await handle.describe()
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return {"armed": False, "state": "missing"}
        raise
    return {
        "armed": True,
        "state": "paused" if desc.schedule.state.paused else "running",
    }


async def _resume_if_paused(
    schedule_id: str, interval_minutes: int, client: Any
) -> dict[str, Any]:
    """Duplicate-create path: the fixed-id schedule already exists. If the
    operator paused it via schedule/stop, unpause so Start genuinely
    re-arms the poller; an already-running schedule is left untouched."""
    from temporalio.service import RPCError, RPCStatusCode

    try:
        desc = await client.get_schedule_handle(schedule_id).describe()
        if not desc.schedule.state.paused:
            return {"status": "scheduled", "interval_minutes": interval_minutes, "note": "existing schedule kept"}
        await client.get_schedule_handle(schedule_id).unpause(
            note="Resumed via Kairos connectors API (reconnect)."
        )
    except RPCError as e:
        # The create above just reported the schedule as existing; a
        # vanished-in-between row is surfaced but never masked.
        if e.status != RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not resume schedule: {e.message}",
            )
    return {"status": "scheduled", "interval_minutes": interval_minutes, "note": "resumed paused schedule"}


@router.get("/pollers", response_model=dict[str, Any])
async def get_poller_status():
    """Live armed/paused state of the two ambient poller schedules
    (Gmail 15-min poll, Slack 5-min listen cycle)."""
    return {
        "gmail": await _schedule_state(_GMAIL_SCHEDULE_ID),
        "slack": await _schedule_state(_SLACK_SCHEDULE_ID),
    }


async def _pause_schedule(schedule_id: str, what: str) -> dict[str, str]:
    """Pauses (does not delete) a poller schedule. A paused schedule keeps
    its configuration, so Start re-arms it without recreating anything."""
    from temporalio.service import RPCError, RPCStatusCode

    from app.temporal.worker import get_temporal_client

    try:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause(note=f"Paused via Kairos connectors API ({what}).")
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {what} schedule exists to pause.",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not pause {what} schedule: {e.message}",
        )
    return {"status": "paused", "schedule": schedule_id}


@router.post("/gmail/schedule/stop", response_model=dict[str, str])
async def stop_gmail_schedule():
    """Pauses the Temporal Schedule that polls Gmail (idempotent)."""
    return await _pause_schedule(_GMAIL_SCHEDULE_ID, "Gmail poll")


@router.post("/slack/schedule/stop", response_model=dict[str, str])
async def stop_slack_schedule():
    """Pauses the Temporal Schedule that runs the Slack listen cycle
    (idempotent)."""
    return await _pause_schedule(_SLACK_SCHEDULE_ID, "Slack listen")


@router.post("/gmail/schedule")
async def setup_gmail_schedule(
    db: AsyncSession = Depends(get_db),
):
    """Creates (or updates) the Temporal Schedule that polls Gmail.

    Idempotent: the schedule id is fixed, so reconnecting Gmail just
    re-arms the same 15-minute poll. Deleting the gmail vault
    credential makes polls no-op (the activity checks the vault
    first).
    """
    from datetime import timedelta as _td

    from temporalio.client import (
        ScheduleActionStartWorkflow,
        Schedule,
        ScheduleAlreadyRunningError,
        ScheduleIntervalSpec,
        ScheduleSpec,
    )
    from temporalio.common import RetryPolicy

    from app.temporal.worker import get_temporal_client
    from app.temporal.gmail_poll import GmailPollWorkflow
    from app.config import settings

    try:
        client = await get_temporal_client()
        await client.create_schedule(
            id="kairos-gmail-poll",
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow=GmailPollWorkflow.run,
                    id="gmail-poll-cycle",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                    retry_policy=RetryPolicy(maximum_attempts=2),
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=_td(minutes=15))],
                ),
            ),
        )
    except ScheduleAlreadyRunningError:
        # Reconnect: the fixed-id schedule already exists. If the operator
        # had paused it (schedule/stop), resume so Start actually re-arms
        # the poll instead of leaving it silently paused forever.
        return await _resume_if_paused(_GMAIL_SCHEDULE_ID, 15, client)
    except Exception as e:
        from app.core.redaction import redact_error
        from fastapi import HTTPException, status as _status

        raise HTTPException(
            status_code=_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not create poll schedule: {redact_error(e)}",
        )

    return {"status": "scheduled", "interval_minutes": 15}


@router.post("/slack/schedule")
async def setup_slack_schedule(
    db: AsyncSession = Depends(get_db),
):
    """Creates (or updates) the Temporal Schedule that runs the Slack
    Socket Mode listen cycle.

    The cycle runs every 5 minutes and listens for a bounded window
    (SLACK_LISTEN_SECONDS, default 240s), so the bot sees ~continuous
    coverage without a long-lived process to supervise. Idempotent like
    the Gmail schedule: reconnecting Slack just re-arms it. Without
    SLACK_APP_TOKEN/SLACK_BOT_TOKEN in the worker's environment every
    cycle is a clean no-op.
    """
    from datetime import timedelta as _td

    from temporalio.client import (
        ScheduleActionStartWorkflow,
        Schedule,
        ScheduleAlreadyRunningError,
        ScheduleIntervalSpec,
        ScheduleSpec,
    )
    from temporalio.common import RetryPolicy

    from app.temporal.worker import get_temporal_client
    from app.temporal.slack_ingest import SlackIngestWorkflow
    from app.config import settings

    try:
        client = await get_temporal_client()
        await client.create_schedule(
            id="kairos-slack-listen",
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow=SlackIngestWorkflow.run,
                    id="slack-listen-cycle",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                    retry_policy=RetryPolicy(maximum_attempts=2),
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=_td(minutes=5))],
                ),
            ),
        )
    except ScheduleAlreadyRunningError:
        return await _resume_if_paused(_SLACK_SCHEDULE_ID, 5, client)
    except Exception as e:
        from app.core.redaction import redact_error
        from fastapi import HTTPException, status as _status

        raise HTTPException(
            status_code=_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not create listen schedule: {redact_error(e)}",
        )

    return {"status": "scheduled", "interval_minutes": 5}


class TestConnectionRequest(BaseModel):
    """Tool-level connection probe for the Settings UI Test button."""
    tool: str = Field(min_length=2, max_length=50)


@router.post("/test", response_model=dict[str, Any])
async def test_connector_connection(
    request: TestConnectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Probes one connector's readiness by tool name.

    Success means the connector's health_check passed — for OAuth tools
    that is "a usable credential exists in the vault (or env)", for the
    built-in task ledger it is always true. Details are phrased for the
    operator and never echo any part of a stored secret.

    The registry (mcp_client_manager._connectors) is the single source
    of truth for tool names; get_connector normalizes (lower/strip) and
    raises ValueError for anything outside the 12 routing targets.
    """
    try:
        connector = mcp_client_manager.get_connector(request.tool)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown tool '{request.tool}'. Valid tools: "
                "task_ledger, notion, jira, calendar, linear, todoist, "
                "email_draft, github, confluence_page, google_tasks, "
                "asana, clickup."
            ),
        )

    tool = request.tool.lower().strip()
    if tool == "task_ledger":
        # Built-in, DB-backed, no external credential to probe.
        return {
            "tool": tool,
            "success": True,
            "detail": "Built-in — always available",
        }

    try:
        healthy = await connector.health_check()
    except Exception:
        # A connector whose probe crashes is reported as not ready, not
        # as a 500: the Settings UI renders a red row either way.
        healthy = False

    detail = (
        "Credential found and connector ready"
        if healthy
        else "No credential stored for this connector"
    )
    return {
        "tool": tool,
        "success": bool(healthy),
        "detail": detail,
    }
