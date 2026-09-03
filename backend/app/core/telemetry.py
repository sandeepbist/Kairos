"""Telemetry and Observability: Langfuse v4 tracing integration.

v4 SDK surface: start_observation(kind="trace") returns a trace object
whose observation_url is real (no fabricated URLs). Traces fail open —
observability must never block the pipeline.
"""
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class TelemetryClient:
    """Thin wrapper over Langfuse v4; no-op when unconfigured."""

    def __init__(self) -> None:
        self._client: Any | None = None
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse observability initialized.")
            except Exception as e:
                logger.warning("Langfuse init failed (tracing disabled): %s", e)
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @staticmethod
    def genai_attributes(
        operation: str,
        tool_name: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Builds metadata keyed to the OpenTelemetry GenAI semantic
        conventions (gen_ai.*) so any OTel-compatible backend parses
        Kairos traces natively, not only Langfuse.
        Ref: open-telemetry/semantic-conventions-genai, gen-ai-spans.md.

        Only real convention attributes are emitted; app-specific values
        (latency, ids) ride as kairos.* keys instead of invented
        gen_ai.* names.
        """
        attrs: dict[str, Any] = {"gen_ai.operation.name": operation}
        if tool_name:
            # gen_ai.tool.name + gen_ai.tool.description mark MCP/connector
            # tool dispatches per the mcp.md conventions.
            attrs["gen_ai.tool.name"] = tool_name
        if input_tokens:
            attrs["gen_ai.usage.input_tokens"] = input_tokens
        if output_tokens:
            attrs["gen_ai.usage.output_tokens"] = output_tokens
        if extra:
            attrs.update(extra)
        return attrs

    def log_trace(
        self,
        batch_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
        latency_ms: int = 0,
        token_count: int = 0,
    ) -> str | None:
        """Emits one trace; returns its real Langfuse URL, or None."""
        if not self._client:
            return None
        try:
            trace = self._client.start_observation(
                name=name,
                kind="trace",
                id=batch_id,
                metadata={**(metadata or {}), "latency_ms": latency_ms, "token_count": token_count},
            )
            url = getattr(trace, "observation_url", None)
            trace.end()
            return url
        except Exception as e:
            logger.debug("Langfuse trace emission failed: %s", e)
            return None

    def shutdown(self) -> None:
        """Flushes the background exporter on process exit."""
        if self._client:
            try:
                self._client.shutdown()
            except Exception:
                pass


telemetry = TelemetryClient()
