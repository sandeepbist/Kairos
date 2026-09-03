"""Outbound webhooks (Standard Webhooks): signing, events, SSRF guard.

Spec: github.com/standard-webhooks/standard-webhooks — three headers
(`webhook-id`, `webhook-timestamp`, `webhook-signature`), HMAC-SHA256 over
"{msg_id}.{timestamp}.{payload}" with the timestamp inside the signed
content (replay defense), secret `whsec_<base64 24-64 bytes>`, signature
`"v1,<base64>"` space-delimited across keys for zero-downtime rotation.
The sender is stdlib-only; the OFFICIAL `standardwebhooks` verifier is
the test oracle ("our signer, their checker").
"""
import base64
import hashlib
import hmac
import ipaddress
import secrets
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

# The complete decision-outcome surface. Payloads are metadata-only:
# no raw_text, no source_snippet, no tool_payload contents ever leave.
WEBHOOK_EVENT_TYPES: tuple[str, ...] = (
    "action.executed",
    "action.rejected",
    "batch.completed",
    "batch.expired",
    "webhook.test",
)


def generate_webhook_secret() -> str:
    """Returns 'whsec_' + base64(24 random bytes) — handed to the operator
    exactly once; receivers paste it verbatim."""
    return "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()


def generate_msg_id() -> str:
    """Stable id for one event→endpoint delivery; reused on every retry."""
    return "msg_" + base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")


def sign_webhook_event(secret_values: str, msg_id: str, timestamp: int, payload: bytes) -> str:
    """Signs the EXACT bytes that will be POSTed. secret_values may carry
    multiple space-delimited whsec_ keys (rotation grace): one 'v1,'
    entry per key, receivers accept any."""
    parts = []
    for sec in secret_values.split():
        key = base64.b64decode(sec.removeprefix("whsec_"))
        signed = msg_id.encode() + b"." + str(timestamp).encode() + b"." + payload
        digest = hmac.new(key, signed, hashlib.sha256).digest()
        parts.append("v1," + base64.b64encode(digest).decode())
    return " ".join(parts)


def build_delivery_headers(
    secret_values: str, msg_id: str, timestamp: int, payload: bytes
) -> dict[str, str]:
    """The three spec headers plus content type, for one POST."""
    return {
        "content-type": "application/json",
        "webhook-id": msg_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": sign_webhook_event(secret_values, msg_id, timestamp, payload),
    }


def build_envelope(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Standard Webhooks payload envelope: type, ISO-8601 timestamp, data."""
    return {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data": data,
    }


class WebhookUrlError(ValueError):
    """Raised when a webhook URL targets a blocked address or scheme."""


def validate_webhook_url(url: str, *, allow_private: bool = False) -> None:
    """Scheme/port policy + private/reserved address rejection.

    Threat model: the only person who can register a URL already holds
    the operator API key — the risk is foot-gun (pointing Kairos at
    internal infra or a cloud metadata service), not tenant crossover.
    Link-local ranges (169.254.0.0/16, fe80::/10 — cloud metadata) are
    blocked unconditionally; other private ranges are gated by the
    WEBHOOK_ALLOW_PRIVATE_URLS setting because the primary self-hosted
    integration target is an operator's own LAN receiver (n8n, Node-RED,
    Home Assistant on the docker bridge). Validation must run at
    registration AND again at delivery time — DNS can change after
    registration. Redirects are never followed by the delivery client.
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise WebhookUrlError(f"unparseable webhook URL: {e}") from e

    allow_http = allow_private  # LAN receivers may be plain http
    if parsed.scheme not in (("https", "http") if allow_http else ("https",)):
        raise WebhookUrlError(
            "webhook URL must be https"
            + (" (or http when private URLs are allowed)" if allow_http else "")
        )
    # Port policy: public internet endpoints stay on standard ports; LAN
    # receivers (allow_private) run on whatever port the operator's service
    # uses (n8n :5678, Home Assistant :8123, custom receivers).
    if parsed.port is not None and not allow_private and parsed.port not in (80, 443):
        raise WebhookUrlError(f"webhook URL port {parsed.port} not allowed (80/443 only)")
    if not parsed.hostname:
        raise WebhookUrlError("webhook URL has no host")

    host = parsed.hostname
    try:
        # Literal IPs skip resolution.
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError as e:
            raise WebhookUrlError(f"cannot resolve webhook host: {e}") from e
        # EVERY resolved address must pass — checking only the first
        # A-record is the classic multi-record SSRF hole.
        addrs = [ipaddress.ip_address(info[4][0]) for info in infos]

    for addr in addrs:
        if addr.is_link_local:
            raise WebhookUrlError(
                f"{addr} is a link-local address (cloud metadata range) — blocked unconditionally"
            )
        if not allow_private and (
            addr.is_private or addr.is_loopback or addr.is_reserved
            or addr.is_multicast or addr.is_unspecified
        ):
            raise WebhookUrlError(
                f"non-public address {addr}; set WEBHOOK_ALLOW_PRIVATE_URLS for LAN receivers"
            )
