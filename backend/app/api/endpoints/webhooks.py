"""Webhooks API: outbound endpoint CRUD, test dispatch, delivery history.

Standard Webhooks (github.com/standard-webhooks/standard-webhooks): the
secret is generated server-side, Fernet-encrypted into the vault, and
shown to the operator exactly once (create or rotate). All routes sit
behind the operator API key via the shared api_router dependency.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decrypt_token, encrypt_token
from app.db.models import (
    WebhookDeliveryModel,
    WebhookEndpointModel,
    generate_uuid,
)
from app.db.session import get_db
from app.webhooks import (
    WEBHOOK_EVENT_TYPES,
    WebhookUrlError,
    generate_webhook_secret,
    validate_webhook_url,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class CreateWebhookRequest(BaseModel):
    url: str = Field(min_length=12, max_length=2048)
    description: str = Field(default="", max_length=200)
    event_types: list[str] = Field(default_factory=lambda: ["*"])


class UpdateWebhookRequest(BaseModel):
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=200)
    event_types: list[str] | None = None


def _validate_event_types(event_types: list[str]) -> None:
    allowed = set(WEBHOOK_EVENT_TYPES) | {"*"}
    unknown = [e for e in event_types if e not in allowed]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown event types: {unknown}. Allowed: {sorted(allowed)}",
        )


async def _load_endpoint(
    endpoint_id: str, db: AsyncSession
) -> WebhookEndpointModel:
    """Single-row primary-key lookup by Python-side match (the table is
    capped at WEBHOOK_MAX_ENDPOINTS rows, so the scan is trivial)."""
    rows = await db.scalars(select(WebhookEndpointModel))
    for endpoint in rows:
        if endpoint.id == endpoint_id:
            return endpoint
    raise HTTPException(status_code=404, detail="Webhook endpoint not found")


async def _load_delivery(
    endpoint_id: str, delivery_id: str, db: AsyncSession
) -> WebhookDeliveryModel:
    rows = await db.scalars(select(WebhookDeliveryModel))
    for delivery in rows:
        if delivery.id == delivery_id and delivery.endpoint_id == endpoint_id:
            return delivery
    raise HTTPException(status_code=404, detail="Delivery not found")


def _endpoint_dict(endpoint: WebhookEndpointModel) -> dict[str, Any]:
    return {
        "id": endpoint.id,
        "url": endpoint.url,
        "description": endpoint.description,
        "enabled": endpoint.enabled,
        "event_types": endpoint.event_types,
        "created_at": endpoint.created_at.isoformat() if endpoint.created_at else None,
    }


@router.get("", response_model=list[dict[str, Any]])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """All registered endpoints. The secret is never included."""
    rows = await db.scalars(select(WebhookEndpointModel))
    return [_endpoint_dict(e) for e in sorted(rows, key=lambda e: e.created_at)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    request: CreateWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """Registers an endpoint. The secret is returned exactly once."""
    _validate_event_types(request.event_types)

    rows = await db.scalars(select(WebhookEndpointModel))
    if len(list(rows)) >= settings.WEBHOOK_MAX_ENDPOINTS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Webhook endpoint cap reached ({settings.WEBHOOK_MAX_ENDPOINTS}).",
        )

    try:
        validate_webhook_url(request.url, allow_private=settings.WEBHOOK_ALLOW_PRIVATE_URLS)
    except WebhookUrlError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    secret = generate_webhook_secret()
    endpoint = WebhookEndpointModel(
        id=generate_uuid(),
        url=request.url,
        description=request.description,
        secret_enc=encrypt_token(secret),
        event_types=request.event_types,
        enabled=True,
    )
    db.add(endpoint)
    await db.commit()

    return {
        **_endpoint_dict(endpoint),
        "secret": secret,
        "secret_notice": "Store this secret now — it will never be shown again.",
    }


@router.patch("/{endpoint_id}")
async def update_webhook(
    endpoint_id: str,
    request: UpdateWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """Toggles enabled, edits description, or narrows subscribed events."""
    endpoint = await _load_endpoint(endpoint_id, db)
    if request.enabled is not None:
        endpoint.enabled = request.enabled
    if request.description is not None:
        endpoint.description = request.description
    if request.event_types is not None:
        _validate_event_types(request.event_types)
        endpoint.event_types = request.event_types
    await db.commit()
    return _endpoint_dict(endpoint)


@router.post("/{endpoint_id}/rotate")
async def rotate_webhook_secret(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Issues a fresh secret. The previous one stays signable for 24h so
    receivers swap keys without a delivery gap (spec multi-key signing)."""
    endpoint = await _load_endpoint(endpoint_id, db)
    if endpoint.secret_enc:
        endpoint.previous_secret_enc = endpoint.secret_enc
    endpoint.secret_enc = encrypt_token(generate_webhook_secret())
    endpoint.rotated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        **_endpoint_dict(endpoint),
        "secret": decrypt_token(endpoint.secret_enc),
        "secret_notice": "Store this secret now — it will never be shown again.",
    }


@router.delete("/{endpoint_id}")
async def delete_webhook(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Removes an endpoint; delivery history cascades."""
    endpoint = await _load_endpoint(endpoint_id, db)
    await db.delete(endpoint)
    await db.commit()
    return {"status": "deleted", "id": endpoint_id}


@router.post("/{endpoint_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Enqueues a webhook.test event for this endpoint through the same
    delivery pipeline real events use — the test path IS the real path."""
    await _load_endpoint(endpoint_id, db)
    from app.temporal.activities import emit_webhook_event_activity

    result = await emit_webhook_event_activity(
        "webhook.test",
        {"message": "Kairos webhook test", "endpoint_id": endpoint_id},
        target_endpoint_id=endpoint_id,
    )
    return {"status": "test_dispatched", "deliveries": result.get("deliveries", 0)}


@router.get("/{endpoint_id}/deliveries")
async def list_deliveries(
    endpoint_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Recent delivery attempts with outcome bookkeeping."""
    await _load_endpoint(endpoint_id, db)
    rows = await db.scalars(select(WebhookDeliveryModel))
    mine = [d for d in rows if d.endpoint_id == endpoint_id]
    mine.sort(key=lambda d: d.created_at, reverse=True)
    from app.core.redaction import redact_secrets

    return {
        "deliveries": [
            {
                "id": d.id,
                "event_type": d.event_type,
                "status": d.status,
                "attempts": d.attempts,
                "last_response_code": d.last_response_code,
                "last_error": redact_secrets(d.last_error) if d.last_error else None,
                "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in mine[: min(limit, 50)]
        ]
    }


@router.post("/{endpoint_id}/deliveries/{delivery_id}/redeliver")
async def redeliver_delivery(
    endpoint_id: str,
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-POSTs an existing delivery with the SAME msg_id and payload bytes
    so the receiver's signature check sees identical inputs (spec replay)."""
    delivery = await _load_delivery(endpoint_id, delivery_id, db)
    delivery.status = "pending"
    delivery.attempts = 0
    delivery.next_retry_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "redispatched", "delivery_id": delivery_id}


@router.post("/arm")
async def arm_dispatch_schedule():
    """Creates (idempotently) the 5-minute dispatch Schedule — the same
    contract as the Gmail/Slack pollers."""
    from datetime import timedelta as _td

    from temporalio.client import (
        Schedule,
        ScheduleActionStartWorkflow,
        ScheduleAlreadyRunningError,
        ScheduleIntervalSpec,
        ScheduleSpec,
    )
    from temporalio.common import RetryPolicy

    from app.temporal.webhook_dispatch import WebhookDispatchWorkflow
    from app.temporal.worker import get_temporal_client

    try:
        client = await get_temporal_client()
        await client.create_schedule(
            id="kairos-webhook-dispatch",
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow=WebhookDispatchWorkflow.run,
                    id="webhook-dispatch-cycle",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                    retry_policy=RetryPolicy(maximum_attempts=2),
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=_td(minutes=5))]),
            ),
        )
    except ScheduleAlreadyRunningError:
        return {"status": "scheduled", "interval_minutes": 5, "note": "existing schedule kept"}
    except Exception as e:
        from app.core.redaction import redact_error

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not create dispatch schedule: {redact_error(e)}",
        )
    return {"status": "scheduled", "interval_minutes": 5}
