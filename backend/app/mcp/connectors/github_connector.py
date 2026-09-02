"""GitHub Connector: creates issues via the GitHub REST API.

Auth: an operator PAT (settings UI / vault provider `github`, or
GITHUB_API_TOKEN env). A fine-grained PAT with `issues: write` scoped
to the target repository is the least-privilege credential; classic
PATs with the `repo` scope also work. The repo is configured per
action (owner/name in the payload) or via GITHUB_TARGET_REPO
("owner/name").
"""
import os
import time
import uuid as _uuid
from typing import Any

from sqlalchemy import select

from app.core.security import decrypt_token
from app.db.models import OAuthTokenModel
from app.db.session import async_session_factory

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client

GITHUB_API = "https://api.github.com"


async def load_provider_token(provider: str) -> str | None:
    """Reads one provider credential from the vault. The table holds at
    most a dozen rows (unique provider), so scanning them and matching
    in Python is both cheap and structurally injection-proof."""
    async with async_session_factory() as session:
        rows = await session.scalars(select(OAuthTokenModel))
        for rec in rows:
            if rec.provider == provider and rec.access_token_enc:
                return decrypt_token(rec.access_token_enc)
    return None


def _parse_repo(repo_spec: str | None) -> tuple[str | None, str | None]:
    """Splits an "owner/name" spec; tolerates a full github.com URL."""
    if not repo_spec:
        return None, None
    spec = repo_spec.strip().strip("/")
    if "github.com/" in spec:
        spec = spec.split("github.com/", 1)[1]
    parts = [p for p in spec.split("/") if p]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None


class GitHubConnector(BaseConnector):
    """Executes action items as GitHub issues."""

    @property
    def tool_name(self) -> str:
        return "github"

    async def _get_token(self) -> str | None:
        return await load_provider_token("github") or os.getenv("GITHUB_API_TOKEN")

    async def health_check(self) -> bool:
        token = await self._get_token()
        return bool(token and token.strip())

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = False,
    ) -> ExecutionResult:
        start_time = time.time()
        try:
            title = (
                payload.get("title")
                or payload.get("summary")
                or payload.get("description")
                or "Untitled issue"
            )
            owner, repo = _parse_repo(
                payload.get("repo")
                or payload.get("repository")
                or os.getenv("GITHUB_TARGET_REPO")
            )

            body_parts = [payload.get("description") or payload.get("notes") or ""]
            snippet = payload.get("source_snippet")
            if snippet:
                body_parts.append("\n> " + str(snippet))
            speaker = payload.get("speaker")
            if speaker:
                body_parts.append("\n\n_Spoken by " + str(speaker) + "_")
            body = "\n".join(body_parts).strip()
            labels = payload.get("labels") or ["kairos"]
            if isinstance(labels, str):
                # The review UI edits labels as a comma-separated string.
                labels = [l.strip() for l in labels.split(",") if l.strip()]

            if sandbox_mode:
                fake_num = _uuid.uuid4().hex[:5]
                base = "https://github.com/" + (owner or "acme") + "/" + (repo or "planning")
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=base + "/issues/" + fake_num,
                    latency_ms=int((time.time() - start_time) * 1000) + 60,
                    raw_response={
                        "number": fake_num,
                        "title": title,
                        "mode": "sandbox",
                    },
                )

            token = await self._get_token()
            if not (owner and repo):
                raise ValueError(
                    "GitHub execution failed: no target repository. Set one "
                    "in the action payload (owner/name) or GITHUB_TARGET_REPO."
                )
            if not token:
                raise ValueError(
                    "GitHub execution failed: no PAT configured. "
                    "Add a GitHub token in Settings or enable Sandbox Mode."
                )

            headers = {
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            async with connector_http_client(timeout=15.0) as client:
                resp = await client.post(
                    GITHUB_API + "/repos/" + str(owner) + "/" + str(repo) + "/issues",
                    json={
                        "title": title[:256],
                        "body": body[:60000],
                        "labels": labels,
                    },
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json()
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=data.get("html_url"),
                        latency_ms=latency_ms,
                        raw_response={
                            "id": data.get("id"),
                            "number": data.get("number"),
                            "html_url": data.get("html_url"),
                        },
                    )
                detail = ""
                try:
                    detail = resp.json().get("message", "")
                except Exception:  # noqa: BLE001 — error bodies are optional
                    pass
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error="GitHub API HTTP " + str(resp.status_code) + ": " + detail,
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
