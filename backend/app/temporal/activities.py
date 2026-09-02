"""Temporal Activities for Kairos Batch Processing Pipeline."""
import base64
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import BatchModel, ActionItemModel, OAuthTokenModel
from app.pipelines.graph import run_extraction_pipeline
from app.pipelines.memory import routing_memory
from app.mcp.client_manager import mcp_client_manager


@activity.defn
async def extract_and_route_activity(
    batch_id: str,
    raw_text: str,
    source_type: str,
) -> dict[str, Any]:
    """Runs LangGraph stateless extraction and routing pipeline."""
    state = await run_extraction_pipeline(
        batch_id=batch_id,
        raw_text=raw_text,
        source_type=source_type,
    )
    return {
        "routed_items": state["routed_items"],
        "token_count": state["token_count"],
        "warning_flags": state["warning_flags"],
        "errors": state["errors"],
    }


@activity.defn
async def persist_extracted_items_activity(
    batch_id: str,
    routed_items: list[dict[str, Any]],
    token_count: int,
) -> list[str]:
    """Persists extracted candidates to PostgreSQL and sets batch status to awaiting_approval."""
    item_ids = []
    async with async_session_factory() as session:
        # Update batch
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if not batch:
            # Batch was erased (operator deletion) while the workflow ran.
            # Retrying cannot succeed — fail this activity permanently and
            # let the workflow's remaining steps become no-ops.
            raise ApplicationError(
                f"Batch {batch_id} no longer exists (erased during processing); abandoning.",
                non_retryable=True,
            )
        batch.status = "awaiting_approval"
        batch.token_count = token_count
        from app.pipelines.events import record_event

        await record_event(
            batch_id, "awaiting_review",
            f"{len(routed_items)} items ready for review",
        )

        # Insert items
        for item in routed_items:
            item_id = item.get("id")
            item_model = ActionItemModel(
                id=item_id,
                batch_id=batch_id,
                description=item["description"],
                suggested_tool=item["suggested_tool"],
                final_tool=item["suggested_tool"],
                tool_payload=item.get("tool_payload", {}),
                source_snippet=item.get("source_snippet", item["description"]),
                speaker=item.get("speaker"),
                suggested_assignee=item.get("suggested_assignee"),
                actionability_type=item.get("actionability_type", "task"),
                priority=item.get("priority", "medium"),
                confidence=float(item.get("confidence", 0.8)),
                status="pending",
            )
            session.add(item_model)
            item_ids.append(item_id)

        await session.commit()
    return item_ids


@activity.defn
async def execute_approved_item_activity(
    batch_id: str,
    item_id: str,
    tool: str,
    payload: dict[str, Any],
    description: str,
    sandbox_mode: bool | None = None,
) -> dict[str, Any]:
    """Executes single approved action item via McpClientManager with SHA256 deduplication."""
    result = await mcp_client_manager.execute_action(
        batch_id=batch_id,
        item_id=item_id,
        tool=tool,
        payload=payload,
        item_description=description,
        sandbox_mode=sandbox_mode,
    )
    return {
        "status": result.status,
        "external_url": result.external_url,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "raw_response": result.raw_response,
    }


@activity.defn
async def reject_item_activity(
    batch_id: str,
    item_id: str,
    rejection_reason: str | None,
) -> dict[str, Any]:
    """Marks an item as rejected in the database."""
    async with async_session_factory() as session:
        item_query = select(ActionItemModel).where(ActionItemModel.id == item_id)
        item_res = await session.execute(item_query)
        item = item_res.scalar_one_or_none()
        if item:
            item.status = "rejected"
            item.rejection_reason = rejection_reason or "Rejected by user during review"
            await session.commit()
            return {"status": "rejected", "item_id": item_id}
    return {"status": "not_found", "item_id": item_id}


@activity.defn
async def update_routing_memory_activity(
    item_id: str,
    batch_id: str,
    description: str,
    suggested_tool: str,
    final_tool: str,
    was_overridden: bool,
) -> None:
    """Records user confirmation or override in the semantic routing memory."""
    await routing_memory.record_feedback(
        item_id=item_id,
        batch_id=batch_id,
        item_description=description,
        suggested_tool=suggested_tool,
        final_tool=final_tool,
        was_overridden=was_overridden,
    )


@activity.defn
async def complete_batch_activity(batch_id: str) -> dict[str, Any]:
    """Marks batch status as completed in database."""
    async with async_session_factory() as session:
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if batch:
            batch.status = "completed"
            await session.commit()
            return {"batch_id": batch_id, "status": "completed"}
    return {"batch_id": batch_id, "status": "not_found"}


@activity.defn
async def expire_batch_activity(batch_id: str) -> dict[str, Any]:
    """Auto-archives batch after 7-day approval timeout."""
    async with async_session_factory() as session:
        batch_query = select(BatchModel).where(BatchModel.id == batch_id)
        batch_res = await session.execute(batch_query)
        batch = batch_res.scalar_one_or_none()
        if batch:
            batch.status = "expired"
            await session.commit()
            return {"batch_id": batch_id, "status": "expired"}
    return {"batch_id": batch_id, "status": "not_found"}


async def _get_gmail_access_token() -> str | None:
    """Returns a usable access token from the gmail vault row, refreshing
    via Google's OAuth endpoint when expired. GMAIL_CLIENT_ID/SECRET must
    be in env for the refresh leg (a poller cannot use installed-app flows).
    """
    import os

    async with async_session_factory() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
        )
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        from app.core.security import decrypt_token

        access = decrypt_token(rec.access_token_enc) if rec.access_token_enc else ""
        needs_refresh = bool(
            rec.refresh_token_enc
            and (not access or (rec.expires_at and rec.expires_at.timestamp() < _now_ts() + 60))
        )
        if not needs_refresh:
            return access or None
        refresh = decrypt_token(rec.refresh_token_enc)
        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        if not (client_id and client_secret):
            activity.logger.warning(
                "Gmail token expired and GMAIL_CLIENT_ID/SECRET not set; skipping refresh."
            )
            return access or None

    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
        if not resp.is_success:
            activity.logger.warning("Gmail token refresh failed: HTTP %s", resp.status_code)
            return access or None
        payload = resp.json()

    from datetime import datetime, timezone, timedelta
    from app.core.security import encrypt_token as _enc

    async with async_session_factory() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
        )
        rec2 = res.scalar_one()
        rec2.access_token_enc = _enc(payload["access_token"])
        rec2.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(payload.get("expires_in", 3600))
        )
        await session.commit()
    return payload["access_token"]


def _now_ts() -> float:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).timestamp()


@activity.defn
async def ingest_gmail_history_activity() -> dict[str, Any]:
    """One Gmail poll: fetch message additions since the last historyId
    watermark and ingest each new thread as a standard batch.

    The watermark lives in the gmail vault row's scopes field (a compact
    place to keep per-poller state without a new table for the prep
    stage). Best-effort: failures surface as workflow retries.
    """
    import json as _json

    import httpx

    from app.core.redaction import redact_error
    from app.db.session import async_session_factory as _factory
    token = await _get_gmail_access_token()
    if not token:
        return {"polled": False, "reason": "gmail_not_configured"}

    async with _factory() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
        )
        rec = res.scalar_one_or_none()
        stored = _json.loads(rec.scopes) if rec and rec.scopes else {}
        history_id = stored.get("history_id", 0)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        if not history_id:
            # First poll: establish the watermark from the current profile,
            # ingesting nothing (ambient starts from "now").
            profile = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers=headers,
            )
            if not profile.is_success:
                return {"polled": False, "reason": f"profile_http_{profile.status_code}"}
            new_history = int(profile.json().get("historyId", 0))
            await _store_history_id(new_history)
            return {"polled": True, "ingested": 0, "history_id": new_history}

        hist = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/history",
            params={"startHistoryId": history_id, "historyTypes": "messageAdded"},
            headers=headers,
        )
        if not hist.is_success:
            return {"polled": False, "reason": f"history_http_{hist.status_code}"}
        records = hist.json().get("history", [])
        thread_ids: list[str] = []
        for rec_hist in records:
            for added in rec_hist.get("messagesAdded", []):
                mid = added.get("message", {}).get("threadId")
                if mid and mid not in thread_ids:
                    thread_ids.append(mid)

        ingested = 0
        for tid in thread_ids[:10]:  # bounded per poll; Schedule catches up next cycle
            thread = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{tid}",
                params={"format": "full"},
                headers=headers,
            )
            if not thread.is_success:
                continue
            body_parts: list[str] = []
            subject = ""
            for msg in thread.json().get("messages", []):
                headers_m = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers_m.get("subject", subject)
                for part in msg.get("payload", {}).get("parts", []):
                    if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                        body_parts.append(
                            base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
                        )
                snippet = msg.get("snippet", "")
                if snippet:
                    body_parts.append(snippet)
            if not body_parts:
                continue
            text = f"[{subject}]\n\n" + "\n".join(body_parts)
            # Reuse the standard ingest core so polled threads get
            # identical batch handling to pasted text.
            from app.api.endpoints.batches import create_and_start_batch

            async with _factory() as session:
                try:
                    await create_and_start_batch(text, "email_thread", session)
                    ingested += 1
                except Exception as inner:  # noqa: BLE001 — one thread must not kill the poll
                    activity.logger.warning(
                        "Gmail thread %s ingest failed: %s",
                        tid, redact_error(inner),
                    )
        # Advance the watermark to the server's current historyId
        new_history = int(hist.json().get("historyId", history_id))
        await _store_history_id(new_history)
        return {"polled": True, "ingested": ingested, "history_id": new_history}


async def _store_history_id(history_id: int) -> None:
    import json as _json2

    from app.db.models import OAuthTokenModel
    from app.db.session import async_session_factory as _f2

    async with _f2() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "gmail")
        )
        rec = res.scalar_one_or_none()
        if rec:
            stored = _json2.loads(rec.scopes) if rec.scopes else {}
            stored["history_id"] = history_id
            rec.scopes = _json2.dumps(stored)
            await session.commit()
