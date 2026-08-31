"""Jira Connector: Integrates with Atlassian Jira Cloud REST API / Rovo MCP and Sandbox."""
import time
import os
import random
import httpx
from typing import Any
from sqlalchemy import select
from app.config import settings
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
        """Retrieves decrypted OAuth token from Postgres or env fallback."""
        async with async_session_factory() as session:
            query = select(OAuthTokenModel).where(OAuthTokenModel.provider == "jira")
            res = await session.execute(query)
            record = res.scalar_one_or_none()
            if record and record.access_token_enc:
                token = decrypt_token(record.access_token_enc)
                return token, None, None

        # Environment variables fallback
        api_token = os.getenv("JIRA_API_TOKEN")
        email = os.getenv("JIRA_EMAIL")
        domain = os.getenv("JIRA_DOMAIN", "company.atlassian.net")
        return api_token, email, domain

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
    ) -> ExecutionResult:
        start_time = time.time()
        project_key = str(payload.get("project_key", "ENG")).upper()
        summary = payload.get("summary") or payload.get("title") or payload.get("description") or "New Jira Issue"
        description = payload.get("description", summary)
        issue_type = payload.get("issue_type", "Task")
        priority = payload.get("priority", "Medium")

        # 1. Sandbox Emulation Mode
        if sandbox_mode:
            issue_num = random.randint(100, 999)
            issue_key = f"{project_key}-{issue_num}"
            simulated_url = f"https://company.atlassian.net/browse/{issue_key}"
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

        # 2. Live Atlassian Jira Cloud Execution
        token, email, domain = await self._get_auth_credentials()
        target_domain = domain or "company.atlassian.net"
        base_url = f"https://{target_domain}"

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
