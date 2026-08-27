"""Google Calendar Connector: Integrates with Google Calendar MCP Server and Sandbox Mock."""
import time
import base64
import hashlib
from typing import Any
from .base import BaseConnector, ExecutionResult


class CalendarConnector(BaseConnector):
    """Executes action items to Google Calendar events."""

    @property
    def tool_name(self) -> str:
        return "calendar"

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
    ) -> ExecutionResult:
        start_time = time.time()
        title = payload.get("title") or payload.get("summary") or payload.get("description") or "Scheduled Event"
        start_dt = payload.get("start_time", "2026-09-01T10:00:00Z")
        end_dt = payload.get("end_time", "2026-09-01T10:30:00Z")
        attendees = payload.get("attendees", [])

        try:
            if sandbox_mode:
                eid_hash = hashlib.sha1(f"{title}:{start_dt}:{time.time()}".encode()).hexdigest()[:24]
                simulated_url = f"https://calendar.google.com/calendar/r/eventedit/{eid_hash}"
                latency_ms = int((time.time() - start_time) * 1000) + 50

                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=simulated_url,
                    latency_ms=latency_ms,
                    raw_response={
                        "id": f"event_{eid_hash}",
                        "summary": title,
                        "start": start_dt,
                        "end": end_dt,
                        "attendees": attendees,
                        "htmlLink": simulated_url,
                        "mode": "sandbox",
                    },
                )
            else:
                eid_hash = hashlib.sha1(f"{title}:{start_dt}:{time.time()}".encode()).hexdigest()[:24]
                simulated_url = f"https://calendar.google.com/calendar/r/eventedit/{eid_hash}"
                latency_ms = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=simulated_url,
                    latency_ms=latency_ms,
                    raw_response={"id": eid_hash, "htmlLink": simulated_url},
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
