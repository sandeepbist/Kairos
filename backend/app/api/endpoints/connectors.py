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
from app.mcp.client_manager import mcp_client_manager

router = APIRouter(prefix="/connectors", tags=["connectors"])


class SaveOAuthTokenRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=50)
    access_token: str = Field(min_length=8, max_length=8_192)
    refresh_token: str | None = Field(default=None, max_length=8_192)
    scopes: str | None = Field(default=None, max_length=2_000)


class SandboxToggleRequest(BaseModel):
    sandbox_mode: bool


@router.get("/status", response_model=dict[str, Any])
async def get_connectors_status(
    db: AsyncSession = Depends(get_db),
):
    """Returns connector health, sandbox flags, and configured OAuth connections."""
    mcp_statuses = await mcp_client_manager.get_connectors_status()

    # Query configured OAuth tokens
    tokens_query = select(OAuthTokenModel.provider)
    result = await db.execute(tokens_query)
    connected_providers = set(result.scalars().all())

    connectors_info = {}
    for tool_name, status_dict in mcp_statuses.items():
        connectors_info[tool_name] = {
            "healthy": status_dict["healthy"],
            "sandbox_mode": settings.SANDBOX_MODE,
            "oauth_connected": tool_name in connected_providers or tool_name == "task_ledger",
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
    valid_providers = ["notion", "jira", "google_calendar", "gemini", "google_ai", "openai"]
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
):
    """Toggles Sandbox / Mock Mode for subsequently ingested batches.

    The mode is captured per batch at ingest time and carried through the
    workflow to execution, so it applies even though the Temporal worker
    runs as a separate process.
    """
    settings.SANDBOX_MODE = request.sandbox_mode
    return {
        "sandbox_mode": settings.SANDBOX_MODE,
        "message": (
            "Sandbox mode set to "
            f"{settings.SANDBOX_MODE} — applies to newly ingested batches."
        ),
    }


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
        # Schedule IDs are unique; an existing one means "reconnect",
        # which is fine — the action and interval are unchanged.
        return {"status": "scheduled", "interval_minutes": 15, "note": "existing schedule kept"}
    except Exception as e:
        from app.core.redaction import redact_error
        from fastapi import HTTPException, status as _status

        raise HTTPException(
            status_code=_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not create poll schedule: {redact_error(e)}",
        )

    return {"status": "scheduled", "interval_minutes": 15}
