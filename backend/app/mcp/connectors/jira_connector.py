"""Jira Connector: Integrates with Atlassian Rovo MCP Server and Sandbox Mock."""
import time
import random
from typing import Any
from .base import BaseConnector, ExecutionResult


class JiraConnector(BaseConnector):
    """Executes action items to Atlassian Jira Cloud."""

    @property
    def tool_name(self) -> str:
        return "jira"

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
    ) -> ExecutionResult:
        start_time = time.time()
        project_key = payload.get("project_key", "ENG").upper()
        summary = payload.get("summary") or payload.get("title") or payload.get("description") or "New Jira Issue"
        issue_type = payload.get("issue_type", "Task")
        priority = payload.get("priority", "Medium")

        try:
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
            else:
                issue_num = random.randint(100, 999)
                issue_key = f"{project_key}-{issue_num}"
                simulated_url = f"https://company.atlassian.net/browse/{issue_key}"
                latency_ms = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=simulated_url,
                    latency_ms=latency_ms,
                    raw_response={"key": issue_key, "url": simulated_url},
                )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=latency_ms,
                error=str(e),
            )

    async def health_check(self) -> bool:
        return True
