"""Telemetry and Observability Wrapper: Langfuse tracing integration."""
import logging
from typing import Any
from app.config import settings

logger = logging.getLogger(__name__)


class TelemetryClient:
    """Wrapper around Langfuse or local structured telemetry."""

    def __init__(self):
        self._enabled = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)
        self._langfuse = None

        if self._enabled:
            try:
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                logger.info("Langfuse observability initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Langfuse client: {e}")
                self._enabled = False

    def log_trace(
        self,
        batch_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
        latency_ms: int = 0,
        token_count: int = 0,
    ) -> str:
        """Logs structured telemetry and returns trace link."""
        trace_url = f"https://cloud.langfuse.com/project/kairos/traces/{batch_id}"
        if self._enabled and self._langfuse:
            try:
                trace = self._langfuse.trace(
                    id=batch_id,
                    name=name,
                    metadata=metadata or {},
                )
                trace.generation(
                    name=f"{name}_generation",
                    usage={"total_tokens": token_count},
                )
            except Exception as e:
                logger.debug(f"Langfuse trace emission failed: {e}")

        return trace_url


telemetry = TelemetryClient()
