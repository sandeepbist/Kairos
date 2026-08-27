"""Base connector interface for MCP tools and Sandbox execution."""
from abc import ABC, abstractmethod
from typing import Any, Literal
from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    """Normalized execution response from any target connector."""
    tool: str
    status: Literal["success", "failed"]
    external_url: str | None = None
    latency_ms: int = 0
    raw_response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class BaseConnector(ABC):
    """Abstract base class for all MCP and API connectors."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Name of the target tool (notion, jira, calendar, task_ledger)."""
        pass

    @abstractmethod
    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = False,
    ) -> ExecutionResult:
        """Executes the action item payload against the real or mock MCP server."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifies connection health or readiness of the connector."""
        pass
