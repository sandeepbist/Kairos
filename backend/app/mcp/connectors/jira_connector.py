"""Jira Connector: Integrates with Atlassian Jira Cloud REST API / Rovo MCP and Sandbox."""
import time
import os
import random
from typing import Any
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import OAuthTokenModel
from app.core.security import decrypt_token
from .base import BaseConnector, ExecutionResult
from .http import connector_http_client


class JiraConnector(BaseConnector):
    """Executes action items to Atlassian Jira Cloud."""

    @property
    def tool_name(self) -> str:
        return "jira"

    async def health_check(self) -> bool:
        """Verifies whether real Jira credentials exist in OAuth vault or env."""
        token, _, _ = await self._get_auth_credentials()
        return bool(token and token.strip())

    async def _get_auth_credentials(self) -> tuple[str | None, str | None, str | None]:
        """Retrieves decrypted OAuth token + operator-configured email/domain.

        The vault stores the token; the account email and site domain are
        operator settings (DB → env), not secrets, so they live in the
        operator_settings store with JIRA_EMAIL/JIRA_DOMAIN env fallback.
        """
        from app.core.operator_settings import resolve_tool_targets

        targets = await resolve_tool_targets()
        async with async_session_factory() as session:
            query = select(OAuthTokenModel).where(OAuthTokenModel.provider == "jira")
            res = await session.execute(query)
            record = res.scalar_one_or_none()
            if record and record.access_token_enc:
                token = decrypt_token(record.access_token_enc)
                return token, targets.get("jira_email") or None, targets.get("jira_domain") or None

        # Environment variables fallback
        api_token = os.getenv("JIRA_API_TOKEN")
        email = targets.get("jira_email") or os.getenv("JIRA_EMAIL")
        domain = targets.get("jira_domain") or os.getenv("JIRA_DOMAIN")
        return api_token, email, domain

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
        idempotency_key: str | None = None,
    ) -> ExecutionResult:
        start_time = time.time()
        # Operator-configured project key; no demo default — a live call
        # without a real target must fail loudly, not file into "ENG".
        from app.core.operator_settings import resolve_tool_targets

        targets = await resolve_tool_targets()
        default_project = (targets.get("jira_project_key") or "").strip()
        project_key = str(payload.get("project_key") or default_project).upper()
        summary = payload.get("summary") or payload.get("title") or payload.get("description") or "New Jira Issue"
        description = payload.get("description", summary)
        issue_type = payload.get("issue_type", "Task")
        priority = payload.get("priority", "Medium")

        # 1. Sandbox Emulation Mode
        if sandbox_mode:
            issue_num = random.randint(100, 999)
            issue_key = f"{project_key or 'SANDBOX'}-{issue_num}"
            simulated_url = f"https://{targets.get('jira_domain') or 'sandbox.invalid'}/browse/{issue_key}"
            latency_ms = int((time.time() - start_time) * 1000) + 60

            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=simulated_url,
                latency_ms=latency_ms,
                raw_response={
                    "id": f"jira-issue-{issue_key}",
                    "key": issue_key,
                    "summary": summary,
                    "issue_type": issue_type,
                    "priority": priority,
                    "url": simulated_url,
                    "mode": "sandbox",
                },
            )

        # 2. Live execution. OAuth access tokens dispatch over real MCP
        # transport to Atlassian's GA remote server first; any MCP failure
        # falls through to the REST path below.
        from .mcp_transport import execute_via_mcp

        token, email, domain = await self._get_auth_credentials()

        if not project_key:
            raise ValueError(
                "Jira execution failed: no project key. Set one in the "
                "action payload or Settings → Tool targets."
            )

        mcp_result = await execute_via_mcp("jira", token or "", payload) if token else None
        if mcp_result and (mcp_result.get("url") or mcp_result.get("key")):
            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=mcp_result.get("url")
                or (f"https://{domain}/browse/{mcp_result.get('key')}" if domain else mcp_result.get("key")),
                latency_ms=int((time.time() - start_time) * 1000),
                raw_response=mcp_result,
            )
        if not domain:
            raise ValueError(
                "Jira execution failed: no site domain configured. Set your "
                "<site>.atlassian.net domain in Settings → Tool targets or the "
                "JIRA_DOMAIN env var."
            )
        base_url = f"https://{domain}"

        if not token:
            # If live mode requested but no token configured, provide clear error
            raise ValueError(
                "Jira execution failed: No Jira OAuth token or API token found. "
                "Configure Jira in Settings or enable Sandbox Mode."
            )

        jira_fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary[:255],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
        }
        # Optional fields: only set what the operator's payload provides.
        if priority:
            jira_fields["priority"] = {"name": str(priority).capitalize()}
        due_date = payload.get("due_date")
        if due_date:
            jira_fields["duedate"] = str(due_date)

        jira_payload = {"fields": jira_fields}

        headers = {"Content-Type": "application/json"}
        auth = None
        if email and token:
            auth = (email, token)
        else:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with connector_http_client(timeout=10.0) as client:
                resp = await client.post(
                    f"{base_url}/rest/api/3/issue",
                    json=jira_payload,
                    headers=headers,
                    auth=auth,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                if resp.is_success:
                    data = resp.json()
                    created_key = data.get("key", f"{project_key}-100")
                    real_url = f"{base_url}/browse/{created_key}"
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=real_url,
                        latency_ms=latency_ms,
                        raw_response=data,
                    )
                else:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=latency_ms,
                        error=f"Jira API HTTP {resp.status_code}: {resp.text}",
                    )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
