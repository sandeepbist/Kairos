"""Notion Connector: Integrates with Official Notion API / MCP Server and Sandbox."""
import time
import os
import uuid
import httpx
from typing import Any
from sqlalchemy import select
from app.config import settings
from app.db.session import async_session_factory
from app.db.models import OAuthTokenModel
from app.core.security import decrypt_token
from .base import BaseConnector, ExecutionResult


class NotionConnector(BaseConnector):
    """Executes action items to Notion Workspace."""

    @property
    def tool_name(self) -> str:
        return "notion"

    async def health_check(self) -> bool:
        """Verifies whether real Notion credentials exist in OAuth vault or env."""
        token = await self._get_auth_token()
        return bool(token and token.strip())

    async def _get_auth_token(self) -> str | None:
        """Retrieves decrypted OAuth token from Postgres or env fallback."""
        async with async_session_factory() as session:
            query = select(OAuthTokenModel).where(OAuthTokenModel.provider == "notion")
            res = await session.execute(query)
            record = res.scalar_one_or_none()
            if record and record.access_token_enc:
                return decrypt_token(record.access_token_enc)

        return os.getenv("NOTION_API_KEY")

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
    ) -> ExecutionResult:
        start_time = time.time()
        title = payload.get("title") or payload.get("summary") or payload.get("description") or "Untitled Notion Page"
        database_id = payload.get("database_id") or os.getenv("NOTION_DATABASE_ID", "roadmap_db")
        details = payload.get("details") or payload.get("description", "")

        # 1. Sandbox Emulation Mode
        if sandbox_mode:
            fake_id = str(uuid.uuid4()).replace("-", "")
            simulated_url = f"https://notion.so/{fake_id}"
            latency_ms = int((time.time() - start_time) * 1000) + 80

            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=simulated_url,
                latency_ms=latency_ms,
                raw_response={
                    "id": fake_id,
                    "title": title,
                    "database_id": database_id,
                    "url": simulated_url,
                    "mode": "sandbox",
                },
            )

        # 2. Live Notion API v1 Execution
        token = await self._get_auth_token()
        if not token:
            raise ValueError(
                "Notion execution failed: No Notion integration token configured. "
                "Add your Notion Internal Secret (secret_...) in Settings."
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                target_parent: dict[str, str] | None = None

                # Check if explicit database_id is provided
                if database_id and database_id != "roadmap_db":
                    target_parent = {"database_id": database_id}
                else:
                    # Dynamically search accessible Notion databases/pages for the integration
                    search_res = await client.post(
                        "https://api.notion.so/v1/search",
                        json={"page_size": 5},
                        headers=headers,
                    )
                    if search_res.is_success:
                        search_data = search_res.json()
                        results = search_data.get("results", [])
                        for res_item in results:
                            obj_type = res_item.get("object")
                            if obj_type == "database":
                                target_parent = {"database_id": res_item["id"]}
                                break
                            elif obj_type == "page" and not target_parent:
                                target_parent = {"page_id": res_item["id"]}

                if not target_parent:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=int((time.time() - start_time) * 1000),
                        error=(
                            "Notion Error: No accessible parent database or page found. "
                            "In Notion, open your database or page, click the '...' menu -> 'Connect to' -> select your Kairos Integration."
                        ),
                    )

                # Format Notion page payload
                if "database_id" in target_parent:
                    notion_body = {
                        "parent": target_parent,
                        "properties": {
                            "title": {
                                "title": [{"type": "text", "text": {"content": title[:2000]}}]
                            }
                        },
                    }
                else:
                    notion_body = {
                        "parent": target_parent,
                        "properties": {
                            "title": {
                                "title": [{"type": "text", "text": {"content": title[:2000]}}]
                            }
                        },
                    }

                if details:
                    notion_body["children"] = [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": details[:2000]}}]
                            },
                        }
                    ]

                resp = await client.post(
                    "https://api.notion.so/v1/pages",
                    json=notion_body,
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                if resp.is_success:
                    data = resp.json()
                    page_id = data.get("id", "").replace("-", "")
                    page_url = data.get("url") or f"https://notion.so/{page_id}"
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=page_url,
                        latency_ms=latency_ms,
                        raw_response=data,
                    )
                else:
                    err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("message", resp.text)
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=latency_ms,
                        error=f"Notion API Error ({resp.status_code}): {err_msg}",
                    )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
