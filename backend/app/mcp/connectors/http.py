"""Shared HTTP transport with retry for transient connector failures.

Connector calls (Notion, Jira, Calendar) hit third-party APIs that fail
transiently: 429 rate limits, 502/503/504 gateways, connection resets.
Retrying at the httpx transport layer is finer-grained than Temporal's
activity retry (which re-runs the whole activity) and keeps the
SHA-256 idempotency hash stable — a retried request replays the exact
same payload.
"""
import asyncio
import logging
import random

import httpx

logger = logging.getLogger(__name__)

# Statuses that justify an automatic retry
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

_RETRYABLE_NETWORK_ERRORS = (
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_MAX_SECONDS = 8.0


class RetryTransport(httpx.AsyncBaseTransport):
    """Async transport wrapper with bounded retries and jittered backoff.

    Wraps an inner transport so failure injection stays possible in tests.
    Implements the full AsyncBaseTransport protocol (handle_async_request,
    aclose) so httpx can manage its lifecycle normally.
    """

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._inner: httpx.AsyncBaseTransport = transport or httpx.AsyncHTTPTransport()
        self._max_retries = max_retries

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        attempt = 0
        last_error: Exception | None = None
        while attempt <= self._max_retries:
            attempt += 1
            try:
                response = await self._inner.handle_async_request(request)
                if response.status_code in _RETRYABLE_STATUS and attempt <= self._max_retries:
                    retry_after = self._retry_after_seconds(response)
                    logger.warning(
                        "Connector call %s %s returned %d (attempt %d/%d), retrying in %.1fs",
                        request.method,
                        request.url.host,
                        response.status_code,
                        attempt,
                        self._max_retries,
                        retry_after,
                    )
                    # Drain response body so the connection can be reused.
                    await response.aread()
                    await asyncio.sleep(retry_after)
                    continue
                return response
            except _RETRYABLE_NETWORK_ERRORS as e:
                last_error = e
                if attempt > self._max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                logger.warning(
                    "Connector call %s %s failed (%s), attempt %d/%d, retrying in %.1fs",
                    request.method,
                    request.url.host,
                    type(e).__name__,
                    attempt,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
        # Unreachable: the loop always returns or raises.
        assert last_error is not None
        raise last_error

    async def aclose(self) -> None:
        await self._inner.aclose()

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float:
        """Honors Retry-After header (seconds form), else exponential backoff."""
        header = response.headers.get("Retry-After")
        if header:
            try:
                return min(float(header), _BACKOFF_MAX_SECONDS)
            except ValueError:
                pass
        return min(_BACKOFF_BASE_SECONDS * 4 + random.uniform(0, 0.25), _BACKOFF_MAX_SECONDS)

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(
            _BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.25),
            _BACKOFF_MAX_SECONDS,
        )


def connector_http_client(timeout: float = 15.0) -> httpx.AsyncClient:
    """Builds an AsyncClient with the shared retry transport."""
    return httpx.AsyncClient(timeout=timeout, transport=RetryTransport())
