"""Google Calendar Connector: Integrates with Google Calendar API v3 / MCP Server and Sandbox."""
import time
import os
import uuid
from typing import Any
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import OAuthTokenModel
from app.core.security import decrypt_token
from .base import BaseConnector, ExecutionResult
from .http import connector_http_client


class CalendarConnector(BaseConnector):
    """Executes action items to Google Calendar."""

    @property
    def tool_name(self) -> str:
        return "calendar"

    async def health_check(self) -> bool:
        """Verifies whether real Google Calendar credentials exist in OAuth vault or env."""
        token = await self._get_auth_token()
        return bool(token and token.strip())

    async def _get_auth_token(self) -> str | None:
        """Retrieves decrypted OAuth token from Postgres or env fallback."""
        async with async_session_factory() as session:
            query = select(OAuthTokenModel).where(OAuthTokenModel.provider.in_(["google_calendar", "calendar"]))
            res = await session.execute(query)
            record = res.scalar_one_or_none()
            if record and record.access_token_enc:
                return decrypt_token(record.access_token_enc)

        return os.getenv("GOOGLE_CALENDAR_TOKEN")

    async def execute(
        self,
        payload: dict[str, Any],
        sandbox_mode: bool = True,
    ) -> ExecutionResult:
        start_time = time.time()
        title = payload.get("title") or payload.get("summary") or "New Calendar Event"
        start_time_iso = payload.get("start_time") or "2026-09-01T14:00:00Z"
        end_time_iso = payload.get("end_time") or "2026-09-01T15:00:00Z"
        attendees = payload.get("attendees", [])
        reminder_minutes = payload.get("reminder_minutes_before", 30)

        # 1. Sandbox Emulation Mode
        if sandbox_mode:
            fake_eid = str(uuid.uuid4())[:18]
            simulated_url = f"https://calendar.google.com/calendar/event?eid={fake_eid}"
            latency_ms = int((time.time() - start_time) * 1000) + 75

            return ExecutionResult(
                tool=self.tool_name,
                status="success",
                external_url=simulated_url,
                latency_ms=latency_ms,
                raw_response={
                    "id": fake_eid,
                    "summary": title,
                    "start": {"dateTime": start_time_iso},
                    "end": {"dateTime": end_time_iso},
                    "attendees": attendees,
                    "htmlLink": simulated_url,
                    "mode": "sandbox",
                },
            )

        # 2. Live Google Calendar API v3 Execution
        token = await self._get_auth_token()
        if not token:
            raise ValueError(
                "Google Calendar execution failed: No OAuth token configured. "
                "Connect Google Calendar in Settings or enable Sandbox Mode."
            )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        cal_body = {
            "summary": title,
            "description": "Scheduled by Kairos Ambient Action Agent",
            "start": {"dateTime": start_time_iso},
            "end": {"dateTime": end_time_iso},
            "attendees": [{"email": str(a)} for a in attendees if a],
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            },
        }

        try:
            async with connector_http_client(timeout=10.0) as client:
                resp = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    json=cal_body,
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                if resp.is_success:
                    data = resp.json()
                    event_url = data.get("htmlLink") or f"https://calendar.google.com/calendar/event?eid={data.get('id')}"
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=event_url,
                        latency_ms=latency_ms,
                        raw_response=data,
                    )
                else:
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="failed",
                        latency_ms=latency_ms,
                        error=f"Google Calendar API HTTP {resp.status_code}: {resp.text}",
                    )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
