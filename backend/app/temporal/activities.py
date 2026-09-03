"""Temporal Activities for Kairos Batch Processing Pipeline."""
import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models import (
    ActionItemModel,
    BatchModel,
    OAuthTokenModel,
    WebhookDeliveryModel,
    WebhookEndpointModel,
)
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


@activity.defn
async def slack_socket_poll_activity() -> dict[str, Any]:
    """One Socket Mode listening cycle; a clean no-op without tokens.

    Connects, listens for a bounded window, collects message events
    (app mentions and DMs — the two places an operator naturally hands
    Kairos a conversation), and ingests each thread as a standard batch
    through the shared ingest core. Seen-message state is kept in the
    slack vault row's scopes JSON (client_msg_id + ts), so a Schedule
    restart never re-ingests. The builtin slack_sdk client hand-rolls
    its WebSocket transport — no third-party websocket dependency.
    """
    import asyncio
    import os

    app_token = os.getenv("SLACK_APP_TOKEN")
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    if not (app_token and bot_token):
        return {"polled": False, "reason": "slack_not_configured"}

    # Socket Mode requires the slack-sdk package; install is opt-in to
    # keep the base dependency set lean for operators who don't use Slack.
    import importlib.util

    if importlib.util.find_spec("slack_sdk") is None:
        activity.logger.warning(
            "Slack tokens are set but slack-sdk is not installed. "
            "Install with: pip install slack-sdk"
        )
        return {"polled": False, "reason": "slack_sdk_missing"}

    from slack_sdk import WebClient
    from slack_sdk.socket_mode import SocketModeClient
    from slack_sdk.socket_mode.request import SocketModeRequest
    from slack_sdk.socket_mode.response import SocketModeResponse

    from app.core.redaction import redact_error

    collected: list[dict[str, Any]] = []

    def _listener(client: SocketModeClient, req: SocketModeRequest) -> None:
        # Every envelope must be acknowledged or Slack retries it.
        try:
            client.send_socket_mode_response(
                SocketModeResponse(envelope_id=req.envelope_id)
            )
        except Exception:  # noqa: BLE001 — ack failures must not kill the listener thread
            return
        if req.type != "events_api":
            return
        event = (req.payload or {}).get("event") or {}
        if event.get("type") != "message":
            return
        # Skip edits/bots/threads-replies-announcements; keep human text.
        if event.get("subtype") or event.get("bot_id"):
            return
        collected.append({
            "channel": event.get("channel"),
            "channel_type": event.get("channel_type"),
            "user": event.get("user"),
            "text": event.get("text") or "",
            "ts": event.get("ts"),
            "thread_ts": event.get("thread_ts"),
            "client_msg_id": event.get("client_msg_id"),
        })

    try:
        socket_client = SocketModeClient(
            app_token=app_token,
            web_client=WebClient(token=bot_token),
            auto_reconnect_enabled=True,
        )
    except Exception as e:  # noqa: BLE001 — credential/config errors surface as a skipped cycle
        activity.logger.warning("Slack Socket Mode connect failed: %s", redact_error(e))
        return {"polled": False, "reason": "connect_failed"}

    socket_client.socket_mode_request_listeners.append(_listener)

    # The builtin client runs its session on background threads; the
    # activity thread just holds the window open then collects.
    try:
        socket_client.connect()
        if not socket_client.is_connected:
            return {"polled": False, "reason": "connect_failed"}
        # The builtin client keeps its WebSocket on background threads;
        # sleep cooperatively in windows so the activity can heartbeat
        # and stay responsive to Temporal cancellation.
        window_seconds = float(os.getenv("SLACK_LISTEN_SECONDS", "240"))
        listened = 0.0
        while listened < window_seconds:
            await asyncio.sleep(min(5.0, window_seconds - listened))
            listened += 5.0
            try:
                activity.heartbeat()
            except RuntimeError:
                # Direct invocation (tests, manual runs) has no worker
                # context; heartbeats only exist under a real activity.
                pass
            if not socket_client.is_connected:
                raise RuntimeError("slack socket disconnected mid-cycle")
    except Exception as e:  # noqa: BLE001 — one bad cycle waits for the next Schedule tick
        activity.logger.warning("Slack listen cycle failed: %s", redact_error(e))
        return {"polled": False, "reason": "listen_failed"}
    finally:
        try:
            socket_client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    if not collected:
        return {"polled": True, "ingested": 0, "events": 0}

    seen = await _load_slack_seen_state()
    web_client = WebClient(token=bot_token)

    # Group by thread (or channel for unthreaded messages): each group
    # becomes one batch, speaker-attributed via users_info lookup.
    groups: dict[str, list[dict[str, Any]]] = {}
    for msg in collected:
        if not msg["text"]:
            continue
        key = msg["thread_ts"] or msg["ts"] or ""
        dedup_key = msg["client_msg_id"] or f"{msg['channel']}:{msg['ts']}"
        if dedup_key in seen:
            continue
        groups.setdefault(key, []).append(msg)

    if not groups:
        return {"polled": True, "ingested": 0, "events": len(collected)}

    name_cache: dict[str, str] = {}
    ingested = 0
    for _, msgs in groups.items():
        lines = []
        for msg in msgs:
            uid = msg.get("user") or ""
            if uid not in name_cache:
                try:
                    info = web_client.users_info(user=uid)
                    name_cache[uid] = (
                        (info.data.get("user") or {}).get("real_name")
                        or (info.data.get("user") or {}).get("name")
                        or uid
                    )
                except Exception:  # noqa: BLE001 — attribution is best-effort
                    name_cache[uid] = uid
            lines.append(f"{name_cache[uid]}: {msg['text']}")

        text = "\n".join(lines)
        if len(text) < 10:
            continue

        from app.api.endpoints.batches import create_and_start_batch

        async with async_session_factory() as session:
            try:
                await create_and_start_batch(text, "slack_conversation", session)
                ingested += 1
            except Exception as inner:  # noqa: BLE001 — one thread must not kill the cycle
                activity.logger.warning(
                    "Slack thread ingest failed: %s", redact_error(inner)
                )
        # Mark every ingested message seen only after the batch lands;
        # a failed ingest retries next cycle.
        for msg in msgs:
            seen.add(msg["client_msg_id"] or f"{msg['channel']}:{msg['ts']}")

    await _store_slack_seen_state(seen)
    return {"polled": True, "ingested": ingested, "events": len(collected)}


async def _load_slack_seen_state() -> set[str]:
    """Reads the seen-message watermark from the slack vault row."""
    import json as _json

    async with async_session_factory() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "slack")
        )
        rec = res.scalar_one_or_none()
        stored = _json.loads(rec.scopes) if rec and rec.scopes else {}
    return set(stored.get("seen_messages", [])[-2000:])  # bounded ring of recent ids


async def _store_slack_seen_state(seen: set[str]) -> None:
    import json as _json2

    async with async_session_factory() as session:
        res = await session.execute(
            select(OAuthTokenModel).where(OAuthTokenModel.provider == "slack")
        )
        rec = res.scalar_one_or_none()
        if not rec:
            return  # no slack vault row: nothing to persist (env-token operators)
        stored = _json2.loads(rec.scopes) if rec.scopes else {}
        stored["seen_messages"] = sorted(seen)[-2000:]
        rec.scopes = _json2.dumps(stored)
        await session.commit()


# Spec retry schedule (seconds): Immediately→5s→5m→30m→2h→5h→10h→14h→20h→24h.
_WEBHOOK_RETRY_DELAYS: tuple[int, ...] = (
    5, 300, 1800, 7200, 18000, 36000, 50400, 72000, 86400,
)
_WEBHOOK_MAX_ATTEMPTS = 10  # 1 immediate + 9 scheduled retries


@activity.defn
async def emit_webhook_event_activity(
    event_type: str,
    data: dict[str, Any],
    target_endpoint_id: str | None = None,
) -> dict[str, Any]:
    """Fans one event out to every enabled endpoint subscribed to it.

    Creates one pending webhook_deliveries row per endpoint (msg_id minted
    here so it is stable across retries — the spec dedup requirement); the
    dispatch Schedule's scan activity performs the actual POSTs. Webhook
    fan-out must never fail the core pipeline, so every error is logged,
    redacted, and swallowed.
    """
    from app.core.redaction import redact_error
    from app.webhooks import WEBHOOK_EVENT_TYPES, build_envelope

    if event_type not in WEBHOOK_EVENT_TYPES:
        activity.logger.warning("Webhook event %r not in allowlist; skipped.", event_type)
        return {"event_type": event_type, "deliveries": 0, "reason": "unknown_event_type"}

    envelope = build_envelope(event_type, data)
    created = 0
    try:
        from app.webhooks import generate_msg_id

        async with async_session_factory() as session:
            rows = await session.scalars(select(WebhookEndpointModel))
            endpoints = list(rows)
            targets = [
                e for e in endpoints
                if e.enabled
                and (target_endpoint_id is None or e.id == target_endpoint_id)
                and (
                    target_endpoint_id is not None
                    or "*" in (e.event_types or [])
                    or event_type in (e.event_types or [])
                )
            ]
            for endpoint in targets:
                session.add(WebhookDeliveryModel(
                    id=str(uuid.uuid4()),
                    endpoint_id=endpoint.id,
                    msg_id=generate_msg_id(),
                    event_type=event_type,
                    payload=envelope,
                    status="pending",
                    attempts=0,
                    next_retry_at=datetime.now(timezone.utc),
                ))
                created += 1
            await session.commit()
    except Exception as e:  # noqa: BLE001 — webhooks never fail the pipeline
        activity.logger.warning(
            "Webhook emit for %s failed: %s", event_type, redact_error(e)
        )
        return {"event_type": event_type, "deliveries": 0, "reason": redact_error(e)}
    return {"event_type": event_type, "deliveries": created}


@activity.defn
async def dispatch_webhooks_activity() -> dict[str, Any]:
    """One dispatch scan: POSTs every pending delivery whose retry time has
    come (bounded at 50 per tick — operator scale; the next tick catches
    up). The delivery client never follows redirects, and the URL is
    re-validated immediately before the POST (DNS can change after
    registration). Outcomes: 2xx → delivered; 410 → endpoint disabled;
    anything else → scheduled retry with jitter until the attempt budget
    is exhausted.
    """
    import json as _json
    import random

    import httpx

    from app.config import settings as _settings
    from app.core.redaction import redact_error
    from app.core.security import decrypt_token
    from app.webhooks import (
        WebhookUrlError,
        build_delivery_headers,
        validate_webhook_url,
    )

    delivered = failed = disabled = retried = 0
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(WebhookDeliveryModel)
            .where(
                WebhookDeliveryModel.status == "pending",
                WebhookDeliveryModel.next_retry_at <= datetime.now(timezone.utc),
            )
            .order_by(WebhookDeliveryModel.created_at)
            .limit(50)
        )
        deliveries = list(rows)
        if not deliveries:
            return {"scanned": 0}

        endpoint_ids = {d.endpoint_id for d in deliveries}
        ep_rows = await session.scalars(select(WebhookEndpointModel))
        endpoints = {e.id: e for e in ep_rows if e.id in endpoint_ids}

        async with httpx.AsyncClient(
            timeout=_settings.WEBHOOK_TIMEOUT_SECONDS, follow_redirects=False,
        ) as client:
            for delivery in deliveries:
                endpoint = endpoints.get(delivery.endpoint_id)
                if not endpoint or not endpoint.enabled:
                    delivery.status = "disabled" if not endpoint else delivery.status
                    continue

                # Serialize once; sign and POST the exact same bytes.
                body = _json.dumps(
                    delivery.payload, separators=(",", ":"), sort_keys=True
                ).encode("utf-8")

                try:
                    validate_webhook_url(
                        endpoint.url, allow_private=_settings.WEBHOOK_ALLOW_PRIVATE_URLS
                    )
                    secrets_value = decrypt_token(endpoint.secret_enc)
                    if (
                        endpoint.previous_secret_enc
                        and endpoint.rotated_at
                        and datetime.now(timezone.utc) - endpoint.rotated_at
                        < timedelta(hours=24)
                    ):
                        secrets_value += " " + decrypt_token(endpoint.previous_secret_enc)

                    ts = int(datetime.now(timezone.utc).timestamp())
                    headers = build_delivery_headers(secrets_value, delivery.msg_id, ts, body)
                    resp = await client.post(endpoint.url, content=body, headers=headers)
                    delivery.last_response_code = resp.status_code
                    delivery.attempts += 1

                    if 200 <= resp.status_code < 300:
                        delivery.status = "delivered"
                        delivery.delivered_at = datetime.now(timezone.utc)
                        delivery.next_retry_at = None
                        delivered += 1
                    elif resp.status_code == 410:
                        # Spec: the receiver unsubscribed — stop everything.
                        delivery.status = "disabled"
                        endpoint.enabled = False
                        disabled += 1
                    else:
                        if delivery.attempts >= _WEBHOOK_MAX_ATTEMPTS:
                            delivery.status = "failed"
                            delivery.next_retry_at = None
                            failed += 1
                        else:
                            delay = _WEBHOOK_RETRY_DELAYS[
                                min(delivery.attempts - 1, len(_WEBHOOK_RETRY_DELAYS) - 1)
                            ]
                            # Jitter lives in the activity (non-determinism
                            # belongs here, never in a workflow).
                            delay = delay * (1.0 + random.uniform(0.0, 0.2))
                            delivery.next_retry_at = (
                                datetime.now(timezone.utc) + timedelta(seconds=delay)
                            )
                            retried += 1
                except (WebhookUrlError, httpx.HTTPError) as e:
                    delivery.attempts += 1
                    delivery.last_error = str(redact_error(e))[:500]
                    if delivery.attempts >= _WEBHOOK_MAX_ATTEMPTS:
                        delivery.status = "failed"
                        delivery.next_retry_at = None
                        failed += 1
                    else:
                        delay = _WEBHOOK_RETRY_DELAYS[
                            min(delivery.attempts - 1, len(_WEBHOOK_RETRY_DELAYS) - 1)
                        ]
                        delivery.next_retry_at = (
                            datetime.now(timezone.utc) + timedelta(seconds=delay)
                        )
                        retried += 1
                except Exception as e:  # noqa: BLE001 — one bad delivery never kills the scan
                    delivery.last_error = str(redact_error(e))[:500]

        await session.commit()

    return {
        "scanned": len(deliveries),
        "delivered": delivered,
        "retried": retried,
        "failed": failed,
        "disabled": disabled,
    }
