"""Rate limiting middleware backed by an in-process sliding window.

slowapi (Redis-backed) was considered, but the deployment shape is a
single API pod behind no load balancer fan-out, so a per-worker
in-memory limiter is correct, dependency-free, and zero-latency.
If the API is ever scaled horizontally, swap ``InMemoryRateLimiter``
for a Redis token bucket — the middleware contract stays identical.

Limits are deliberately generous for an operator dashboard (this is a
single-user tool) while still capping brute-force and runaway-script
damage: 60 req/min general, 10 req/min on the mutation endpoints.
"""
import time
from collections import defaultdict, deque
from typing import Any, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = now or time.monotonic()
        window = self._hits[key]
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - window[0])) + 1
            return False, max(retry_after, 1)
        window.append(now)
        return True, 0


def _client_ip(request: Request) -> str:
    """Resolve the rate-limit key, immune to client-supplied X-Forwarded-For.

    Uvicorn (>=0.46) enables --proxy-headers by default for loopback peers,
    which rewrites request.client from attacker-controlled X-Forwarded-For —
    so request.client alone cannot be trusted to identify a client. The
    X-Forwarded-For chain is right-to-left: the LAST entry is the one added
    by the hop we actually talk to. Only when TRUST_PROXY is explicitly set
    (deployment behind a proxy that overwrites XFF) do we honor that last
    entry; otherwise the limiter keys every request by its true socket
    peer. A spoofed header then cannot mint fresh identities.
    """
    if settings.TRUST_PROXY:
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[-1].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies per-path-class limits: mutations are stricter than reads."""

    # Every instantiated middleware registers its limiters here so test
    # tooling can clear the in-memory windows between suites sharing one
    # app process (burst tests legitimately exhaust them).
    _active_limiters: list["InMemoryRateLimiter"] = []

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._read_limiter = InMemoryRateLimiter(max_requests=60, window_seconds=60)
        self._write_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)
        type(self)._active_limiters.extend([self._read_limiter, self._write_limiter])

    @classmethod
    def reset_for_tests(cls) -> None:
        """Drops all recorded hit windows (test isolation only)."""
        for limiter in cls._active_limiters:
            limiter._hits.clear()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Health probes must never be throttled.
        if request.url.path in PUBLIC_PATHS_NO_LIMIT:
            return await call_next(request)

        ip = _client_ip(request)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            allowed, retry_after = self._write_limiter.check(ip)
        else:
            allowed, retry_after = self._read_limiter.check(ip)

        if not allowed:
            return Response(
                content='{"detail": "Rate limit exceeded."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


# Paths exempt from rate limiting (health probes)
PUBLIC_PATHS_NO_LIMIT: frozenset[str] = frozenset({"/api/health"})


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects request bodies over 1 MB at the edge.

    Schema caps (raw_text 50k chars, decisions 200, tokens 8k) make a
    legitimate body far smaller; 1 MB headroom keeps batch ingest safe
    while blocking memory-abuse payloads before any parsing happens.
    """

    MAX_BYTES = 1_048_576

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.MAX_BYTES:
                    return Response(
                        content='{"detail": "Request body too large."}',
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                return Response(
                    content='{"detail": "Invalid Content-Length."}',
                    status_code=400,
                    media_type="application/json",
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Sets defensive HTTP response headers on every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if settings.is_production:
            # Backend is API-only; HSTS on the edge proxy covers plain HTTP.
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


def register_security_middleware(app: FastAPI) -> None:
    """Installs security headers + rate limiting (outermost first-run order)."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(MaxBodySizeMiddleware)
