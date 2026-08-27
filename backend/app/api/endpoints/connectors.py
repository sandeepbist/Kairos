"""Connectors API Endpoints: Health status, OAuth vault, and Sandbox toggles."""
from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import OAuthTokenModel
from app.core.security import encrypt_token, decrypt_token
from app.mcp.client_manager import mcp_client_manager

router = APIRouter(prefix="/connectors", tags=["connectors"])


class SaveOAuthTokenRequest(BaseModel):
    provider: str  # notion, jira, google_calendar
    access_token: str
    refresh_token: str | None = None
    scopes: str | None = None


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

    return {
        "sandbox_mode": settings.SANDBOX_MODE,
        "connectors": connectors_info,
    }


@router.post("/oauth/save", response_model=dict[str, str])
async def save_oauth_token(
    request: SaveOAuthTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Encrypts and stores user OAuth credentials in Postgres vault."""
    provider = request.provider.lower().strip()
    if provider not in ["notion", "jira", "google_calendar"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider '{provider}'.",
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


@router.post("/sandbox-toggle", response_model=dict[str, Any])
async def toggle_sandbox_mode(
    request: SandboxToggleRequest,
):
    """Toggles Sandbox / Mock Mode dynamically for live demos."""
    settings.SANDBOX_MODE = request.sandbox_mode
    return {
        "sandbox_mode": settings.SANDBOX_MODE,
        "message": f"Sandbox mode set to {settings.SANDBOX_MODE}",
    }
