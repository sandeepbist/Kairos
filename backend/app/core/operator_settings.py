"""Operator settings: DB-first resolution with env fallback.

Single source of truth for operator-settable configuration — tool
targets (Jira project, Notion database, GitHub repo, …) and the
sandbox/live execution mode. Values live in the operator_settings
table so the FastAPI process and the Temporal worker (separate
processes) agree, and so toggles survive restarts; env vars remain
the deployment-time source via the resolution chain

    DB value → environment variable → empty/None

Nothing here invents defaults: an unset target resolves to "" and the
connector refuses to execute live with an actionable message rather
than firing at a demo placeholder.
"""
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OperatorSettingsModel
from app.db.session import async_session_factory

# key → env var(s) probed in order. First non-empty wins.
# execution.sandbox_mode is boolean: parsed from "true"/"1"/"yes".
SETTING_ENV_SOURCES: dict[str, tuple[str, ...]] = {
    "execution.sandbox_mode": ("SANDBOX_MODE",),
    "tool_targets.jira_project_key": ("KAIROS_JIRA_PROJECT_KEY",),
    "tool_targets.jira_domain": ("KAIROS_JIRA_DOMAIN", "JIRA_DOMAIN"),
    "tool_targets.jira_email": ("KAIROS_JIRA_EMAIL", "JIRA_EMAIL"),
    "tool_targets.notion_database_id": ("KAIROS_NOTION_DATABASE_ID", "NOTION_DATABASE_ID"),
    "tool_targets.github_repo": ("KAIROS_GITHUB_TARGET_REPO", "GITHUB_TARGET_REPO"),
    "tool_targets.github_labels": ("KAIROS_GITHUB_LABELS",),
    "tool_targets.confluence_space_key": ("KAIROS_CONFLUENCE_SPACE_KEY", "CONFLUENCE_SPACE_KEY"),
    "tool_targets.clickup_list_id": ("KAIROS_CLICKUP_TARGET_LIST", "CLICKUP_TARGET_LIST"),
    "tool_targets.asana_workspace": ("KAIROS_ASANA_WORKSPACE", "ASANA_WORKSPACE"),
}

_BOOLEAN_KEYS = {"execution.sandbox_mode"}


def _coerce_env(key: str, raw: str) -> Any:
    if key in _BOOLEAN_KEYS:
        return raw.strip().lower() in ("true", "1", "yes", "on")
    return raw


async def load_operator_settings(keys: list[str] | None = None) -> dict[str, Any]:
    """Resolves the requested keys (all when None) through DB → env.

    Returns a flat dict of key → value. DB values are stored as JSON;
    env values are read as raw strings.
    """
    wanted = keys if keys is not None else list(SETTING_ENV_SOURCES)
    resolved: dict[str, Any] = {}

    db_keys: set[str] = set()
    async with async_session_factory() as session:
        result = await session.execute(
            select(OperatorSettingsModel).where(OperatorSettingsModel.key.in_(wanted))
        )
        for row in result.scalars().all():
            db_keys.add(row.key)
            resolved[row.key] = row.value

    for key in wanted:
        if key in db_keys:
            continue
        for env_name in SETTING_ENV_SOURCES.get(key, ()):
            raw = os.getenv(env_name, "")
            if raw:
                resolved[key] = _coerce_env(key, raw)
                break
        resolved.setdefault(key, False if key in _BOOLEAN_KEYS else "")
    return resolved


async def resolve_tool_targets() -> dict[str, str]:
    """Resolved tool target map for extraction prefill and connectors."""
    keys = [key for key in SETTING_ENV_SOURCES if key.startswith("tool_targets.")]
    values = await load_operator_settings(keys)
    return {key.removeprefix("tool_targets."): str(v or "") for key, v in values.items()}


async def get_operator_setting(key: str, default: Any = None) -> Any:
    """Resolves a single key; `default` when unset everywhere."""
    resolved = await load_operator_settings([key])
    value = resolved.get(key)
    if isinstance(value, bool):
        return value
    if value in ("", None):
        return default
    return value


async def save_operator_setting(key: str, value: Any, db: AsyncSession) -> None:
    """Upserts one key. Caller owns the transaction (commit/rollback)."""
    result = await db.execute(select(OperatorSettingsModel).where(OperatorSettingsModel.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        db.add(OperatorSettingsModel(key=key, value=value))
    else:
        row.value = value
