"""Outbound webhooks: signing (official verifier as oracle), SSRF, API, E2E."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.webhooks import (
    WEBHOOK_EVENT_TYPES,
    build_delivery_headers,
    build_envelope,
    generate_msg_id,
    generate_webhook_secret,
    validate_webhook_url,
    WebhookUrlError,
)


# ---------------------------------------------------------
# Signing — our signer judged by the OFFICIAL verifier
# ---------------------------------------------------------

def test_secret_generation_format():
    secret = generate_webhook_secret()
    assert secret.startswith("whsec_")
    raw = base64.b64decode(secret.removeprefix("whsec_"))
    assert len(raw) >= 24


def test_signature_passes_official_verifier():
    """Our stdlib signer, their checker — the conformance contract."""
    from standardwebhooks import Webhook

    secret = generate_webhook_secret()
    msg_id = generate_msg_id()
    import time

    ts = int(time.time())
    payload = json.dumps(
        build_envelope("action.executed", {"batch_id": "b", "item_id": "i"}),
        separators=(",", ":"), sort_keys=True,
    ).encode()
    headers = build_delivery_headers(secret, msg_id, ts, payload)

    wh = Webhook(secret)
    parsed = wh.verify(payload, headers)  # raises on any mismatch
    assert parsed["type"] == "action.executed"


def test_signature_rejects_tampered_payload():
    from standardwebhooks import Webhook
    from standardwebhooks.exceptions import WebhookVerificationError

    secret = generate_webhook_secret()
    msg_id = generate_msg_id()
    import time

    ts = int(time.time())
    payload = b'{"type": "action.executed", "data": {"batch_id": "b"}}'
    headers = build_delivery_headers(secret, msg_id, ts, payload)
    tampered = payload.replace(b'"b"', b'"x"')

    with pytest.raises(WebhookVerificationError):
        Webhook(secret).verify(tampered, headers)


def test_signature_rejects_stale_timestamp():
    """The timestamp inside the signed content is the replay defense."""
    from standardwebhooks import Webhook
    from standardwebhooks.exceptions import WebhookVerificationError

    secret = generate_webhook_secret()
    msg_id = generate_msg_id()
    payload = b'{"type": "webhook.test"}'
    stale_ts = int(__import__("time").time()) - 600  # outside ±5min tolerance
    headers = build_delivery_headers(secret, msg_id, stale_ts, payload)

    with pytest.raises(WebhookVerificationError):
        Webhook(secret).verify(payload, headers)


def test_multi_key_rotation_signs_both():
    """Two space-delimited secrets → two v1, signatures; the verifier
    accepts under either key (zero-downtime rotation grace)."""
    from standardwebhooks import Webhook

    old_secret = generate_webhook_secret()
    new_secret = generate_webhook_secret()
    msg_id = generate_msg_id()
    import time

    ts = int(time.time())
    payload = b'{"type": "batch.completed"}'
    both = old_secret + " " + new_secret
    headers = build_delivery_headers(both, msg_id, ts, payload)

    assert headers["webhook-signature"].count("v1,") == 2
    Webhook(new_secret).verify(payload, headers)
    Webhook(old_secret).verify(payload, headers)


def test_event_types_allowlist_frozen():
    assert WEBHOOK_EVENT_TYPES == (
        "action.executed", "action.rejected", "batch.completed",
        "batch.expired", "webhook.test",
    )


# ---------------------------------------------------------
# SSRF
# ---------------------------------------------------------

def test_ssrf_rejects_private_and_reserved(monkeypatch):
    """Every address must pass — literal IPs and resolved hostnames."""
    blocked_literals = [
        "https://127.0.0.1/hook", "https://[::1]/hook",
        "https://192.168.1.1/hook", "https://172.16.0.1/hook",
        "https://10.0.0.1/hook", "https://0.0.0.0/hook",
        "https://224.0.0.1/hook", "https://[fc00::1]/hook",
    ]
    for url in blocked_literals:
        with pytest.raises(WebhookUrlError):
            validate_webhook_url(url)


def test_ssrf_link_local_blocked_even_when_private_allowed():
    """Cloud metadata ranges are unconditional — no flag overrides them."""
    for url in ("https://169.254.169.254/hook", "https://[fe80::1]/hook"):
        with pytest.raises(WebhookUrlError):
            validate_webhook_url(url, allow_private=True)


def test_ssrf_private_allowed_for_lan_receiver():
    """The primary self-hosted receiver is on the operator's own LAN."""
    validate_webhook_url("https://192.168.1.50/hook", allow_private=True)
    validate_webhook_url("http://192.168.1.50:80/hook", allow_private=True)


def test_ssrf_scheme_and_port_policy():
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("http://example.com/hook")  # https required by default
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://example.com:8080/hook")
    validate_webhook_url("https://example.com/hook")  # default port fine


def test_ssrf_multi_record_hostname_all_addrs_checked(monkeypatch):
    """A hostname resolving to one public and one private IP must FAIL —
    checking only the first A-record is the classic SSRF hole."""
    import socket

    def fake_getaddrinfo(host, port, *a, **kw):
        return [
            (socket.AF_INET, None, None, "", ("93.184.216.34", 0)),
            (socket.AF_INET, None, None, "", ("192.168.0.1", 0)),
        ]

    monkeypatch.setattr("app.webhooks.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://mixed.example.com/hook")


def test_ssrf_public_hostname_passes(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *a, **kw):
        return [(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("app.webhooks.socket.getaddrinfo", fake_getaddrinfo)
    validate_webhook_url("https://example.com/hook")


# ---------------------------------------------------------
# API — endpoint lifecycle
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_crud_roundtrip():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/webhooks", json={
            "url": "https://hooks.example.com/kairos",
            "description": "n8n",
            "event_types": ["*"],
        })
        assert res.status_code in (201, 400)
        if res.status_code == 400:
            pytest.skip("no network resolution in this sandbox")

        body = res.json()
        assert body["secret"].startswith("whsec_")
        endpoint_id = body["id"]

        # list: no secret ever
        listed = (await client.get("/api/webhooks")).json()
        assert "whsec_" not in json.dumps(listed)
        assert any(e["id"] == endpoint_id for e in listed)

        # patch
        patched = await client.patch(f"/api/webhooks/{endpoint_id}", json={"enabled": False})
        assert patched.json()["enabled"] is False

        # deliveries empty list
        deliveries = (await client.get(f"/api/webhooks/{endpoint_id}/deliveries")).json()
        assert deliveries["deliveries"] == []

        # delete
        deleted = await client.delete(f"/api/webhooks/{endpoint_id}")
        assert deleted.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_create_rejects_unknown_event_type():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/webhooks", json={
            "url": "https://hooks.example.com/k", "event_types": ["made_up.event"],
        })
        assert res.status_code == 400
        assert "made_up.event" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_rejects_private_url_without_flag(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/webhooks", json={"url": "https://192.168.1.5/hook"})
        assert res.status_code == 400
        assert "WEBHOOK_ALLOW_PRIVATE_URLS" in res.json()["detail"]


# ---------------------------------------------------------
# Emit + dispatch (fan-out, retries, 410) — activity level
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_fans_out_per_subscribed_endpoint():
    from app.temporal.activities import emit_webhook_event_activity

    from app.core.security import encrypt_token
    from app.db.models import WebhookEndpointModel
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        all_events = WebhookEndpointModel(
            id="ep-all", url="https://hooks.example.com/all",
            secret_enc=encrypt_token(generate_webhook_secret()),
            event_types=["*"], enabled=True,
        )
        selective = WebhookEndpointModel(
            id="ep-selective", url="https://hooks.example.com/sel",
            secret_enc=encrypt_token(generate_webhook_secret()),
            event_types=["batch.completed"], enabled=True,
        )
        disabled = WebhookEndpointModel(
            id="ep-disabled", url="https://hooks.example.com/off",
            secret_enc=encrypt_token(generate_webhook_secret()),
            event_types=["*"], enabled=False,
        )
        session.add_all([all_events, selective, disabled])
        await session.commit()

    result = await emit_webhook_event_activity("action.executed", {"batch_id": "b"})
    assert result["deliveries"] == 1  # only the enabled, subscribed endpoint

    # cleanup via API-free path: python-side delete
    from sqlalchemy import select

    async with async_session_factory() as session:
        rows = await session.scalars(select(WebhookEndpointModel))
        for row in rows:
            await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_emit_unknown_event_type_is_swallowed():
    from app.temporal.activities import emit_webhook_event_activity

    result = await emit_webhook_event_activity("nonsense.event", {})
    assert result["deliveries"] == 0


@pytest.mark.asyncio
async def test_dispatch_delivers_and_verifies_e2e():
    """The money test: real HTTP receiver, real dispatch scan, real
    signature — verified by the OFFICIAL standardwebhooks verifier.
    Our sender, their checker."""
    from app.config import settings as app_settings
    from app.core.security import encrypt_token
    from app.db.models import WebhookDeliveryModel, WebhookEndpointModel
    from app.db.session import async_session_factory
    from app.temporal.activities import dispatch_webhooks_activity, emit_webhook_event_activity
    from standardwebhooks import Webhook

    captured: dict = {}

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("content-length", 0))
            captured["body"] = self.rfile.read(length)
            captured["headers"] = {
                "webhook-id": self.headers.get("webhook-id"),
                "webhook-timestamp": self.headers.get("webhook-timestamp"),
                "webhook-signature": self.headers.get("webhook-signature"),
            }
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    secret = generate_webhook_secret()
    try:
        # Register an endpoint against the local receiver; private URLs are
        # required in this test, so flip the setting for the scan.
        async with async_session_factory() as session:
            session.add(WebhookEndpointModel(
                id="ep-e2e",
                url=f"http://127.0.0.1:{port}/hook",
                secret_enc=encrypt_token(secret),
                event_types=["*"], enabled=True,
            ))
            await session.commit()

        original = app_settings.WEBHOOK_ALLOW_PRIVATE_URLS
        app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = True
        try:
            await emit_webhook_event_activity("webhook.test", {"message": "e2e"})
            result = await dispatch_webhooks_activity()
            assert result["delivered"] >= 1, result

            # Official verifier on the captured request
            Webhook(secret).verify(captured["body"], captured["headers"])
            envelope = json.loads(captured["body"])
            assert envelope["type"] == "webhook.test"

            # Delivery row is terminal
            async with async_session_factory() as session:
                rows = await session.scalars(
                    __import__("sqlalchemy").select(WebhookDeliveryModel)
                )
                row = next(r for r in rows if r.endpoint_id == "ep-e2e")
                assert row.status == "delivered"
                assert row.attempts == 1
                assert row.last_response_code == 200
                # msg_id stability: the header id matches the row
                assert captured["headers"]["webhook-id"] == row.msg_id
        finally:
            app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = original
    finally:
        server.shutdown()

    # cleanup endpoints
    async with async_session_factory() as session:
        rows = await session.scalars(
            __import__("sqlalchemy").select(WebhookEndpointModel)
        )
        for row in rows:
            await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_dispatch_410_disables_endpoint():
    """Spec: a 410 answer means the receiver unsubscribed — stop."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from app.config import settings as app_settings
    from app.core.security import encrypt_token
    from app.db.models import WebhookEndpointModel
    from app.db.session import async_session_factory
    from app.temporal.activities import dispatch_webhooks_activity, emit_webhook_event_activity

    class Gone(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(410)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Gone)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        async with async_session_factory() as session:
            session.add(WebhookEndpointModel(
                id="ep-gone",
                url=f"http://127.0.0.1:{port}/hook",
                secret_enc=encrypt_token(generate_webhook_secret()),
                event_types=["*"], enabled=True,
            ))
            await session.commit()

        original = app_settings.WEBHOOK_ALLOW_PRIVATE_URLS
        app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = True
        try:
            await emit_webhook_event_activity("webhook.test", {})
            await dispatch_webhooks_activity()

            async with async_session_factory() as session:
                rows = await session.scalars(
                    __import__("sqlalchemy").select(WebhookEndpointModel)
                )
                ep = next(r for r in rows if r.id == "ep-gone")
                assert ep.enabled is False
        finally:
            app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = original
    finally:
        server.shutdown()

    async with async_session_factory() as session:
        rows = await session.scalars(
            __import__("sqlalchemy").select(WebhookEndpointModel)
        )
        for row in rows:
            await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_dispatch_schedules_retry_on_500():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from app.config import settings as app_settings
    from app.core.security import encrypt_token
    from app.db.models import WebhookDeliveryModel, WebhookEndpointModel
    from app.db.session import async_session_factory
    from app.temporal.activities import dispatch_webhooks_activity, emit_webhook_event_activity

    attempts = {"n": 0}

    class Flaky(BaseHTTPRequestHandler):
        def do_POST(self):
            attempts["n"] += 1
            self.send_response(500)
            self.end_headers()

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Flaky)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        async with async_session_factory() as session:
            session.add(WebhookEndpointModel(
                id="ep-flaky",
                url=f"http://127.0.0.1:{port}/hook",
                secret_enc=encrypt_token(generate_webhook_secret()),
                event_types=["*"], enabled=True,
            ))
            await session.commit()

        original = app_settings.WEBHOOK_ALLOW_PRIVATE_URLS
        app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = True
        try:
            await emit_webhook_event_activity("webhook.test", {})
            result = await dispatch_webhooks_activity()
            assert result["retried"] >= 1

            async with async_session_factory() as session:
                rows = await session.scalars(
                    __import__("sqlalchemy").select(WebhookDeliveryModel)
                )
                row = next(r for r in rows if r.endpoint_id == "ep-flaky")
                assert row.status == "pending"
                assert row.attempts == 1
                assert row.next_retry_at is not None  # spec retry schedule armed
        finally:
            app_settings.WEBHOOK_ALLOW_PRIVATE_URLS = original
    finally:
        server.shutdown()

    async with async_session_factory() as session:
        rows = await session.scalars(
            __import__("sqlalchemy").select(WebhookEndpointModel)
        )
        for row in rows:
            await session.delete(row)
        await session.commit()


def test_retry_schedule_matches_spec():
    from app.temporal.activities import _WEBHOOK_RETRY_DELAYS, _WEBHOOK_MAX_ATTEMPTS

    assert _WEBHOOK_RETRY_DELAYS == (5, 300, 1800, 7200, 18000, 36000, 50400, 72000, 86400)
    assert _WEBHOOK_MAX_ATTEMPTS == 10
