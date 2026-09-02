"""Email-draft Connector: creates a Gmail draft for the operator to review
and send — the highest-value target for email-thread inputs.

Auth reuses the `gmail` vault credential (the same one the Gmail poller
uses), falling back to GMAIL_ACCESS_TOKEN env. Executions create drafts
via the Gmail API — nothing is ever sent automatically; the operator
clicks send. This preserves the human-approval posture: even the draft
itself waits in the mailbox for a final look.
"""
import base64
import os
import time
import uuid as _uuid
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select

from app.core.security import decrypt_token
from app.db.models import OAuthTokenModel
from app.db.session import async_session_factory

from .base import BaseConnector, ExecutionResult
from .http import connector_http_client


class EmailDraftConnector(BaseConnector):
    """Executes action items as ready-to-send Gmail drafts."""

    @property
    def tool_name(self) -> str:
        return "email_draft"

    async def _get_token(self) -> str | None:
        async with async_session_factory() as session:
            res = await session.execute(
                select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
            )
            rec = res.scalar_one_or_none()
            if rec and rec.access_token_enc:
                return decrypt_token(rec.access_token_enc)
        return os.getenv("GMAIL_ACCESS_TOKEN")

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
            subject = (
                payload.get("subject")
                or payload.get("title")
                or payload.get("summary")
                or "Draft from Kairos"
            )
            body = payload.get("body") or payload.get("description") or payload.get("notes") or ""
            to = payload.get("to") or payload.get("attendee") or ""
            cc = payload.get("cc") or ""

            if sandbox_mode:
                fake_id = _uuid.uuid4().hex[:16]
                return ExecutionResult(
                    tool=self.tool_name,
                    status="success",
                    external_url=f"https://mail.google.com/mail/u/0/#draft?compose={fake_id}",
                    latency_ms=int((time.time() - start_time) * 1000) + 60,
                    raw_response={
                        "id": fake_id,
                        "subject": subject,
                        "to": to,
                        "mode": "sandbox",
                    },
                )

            token = await self._get_token()
            if not token:
                raise ValueError(
                    "Email draft failed: no Gmail credential configured. "
                    "Connect Gmail in Settings or enable Sandbox Mode."
                )

            message = EmailMessage()
            message["To"] = str(to) if to else ""  # operator fills the rest in the draft
            if cc:
                message["Cc"] = str(cc)
            message["Subject"] = str(subject)[:998]
            message.set_content(str(body)[:50000])
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            async with connector_http_client(timeout=15.0) as client:
                resp = await client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
                    json={"message": {"raw": raw}},
                    headers=headers,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                if resp.is_success:
                    data = resp.json()
                    draft_id = data.get("id", "")
                    return ExecutionResult(
                        tool=self.tool_name,
                        status="success",
                        external_url=(
                            f"https://mail.google.com/mail/u/0/#draft?compose={draft_id}"
                            if draft_id
                            else None
                        ),
                        latency_ms=latency_ms,
                        raw_response=data,
                    )
                return ExecutionResult(
                    tool=self.tool_name,
                    status="failed",
                    latency_ms=latency_ms,
                    error=f"Gmail drafts API HTTP {resp.status_code}",
                )
        except Exception as e:
            return ExecutionResult(
                tool=self.tool_name,
                status="failed",
                latency_ms=int((time.time() - start_time) * 1000),
                error=str(e),
            )
