"""Phase 9 Battle Tests: Retry transport and workflow decision validation."""
import httpx
import pytest

from app.mcp.connectors.http import RetryTransport


class _FlakyTransport(httpx.AsyncBaseTransport):
    """Fails with retryable statuses/exceptions N times, then succeeds."""

    def __init__(self, failures: int = 2, exc: Exception | None = None):
        self.failures = failures
        self.exc = exc
        self.calls = 0

    async def handle_async_request(self, request):
        self.calls += 1
        if self.calls <= self.failures:
            if self.exc is not None:
                raise self.exc
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)


@pytest.mark.asyncio
async def test_retry_transport_recovers_from_503():
    flaky = _FlakyTransport(failures=2)
    async with httpx.AsyncClient(transport=RetryTransport(transport=flaky)) as client:
        res = await client.get("https://api.example.com/x")
    assert res.status_code == 200
    assert flaky.calls == 3


@pytest.mark.asyncio
async def test_retry_transport_recovers_from_network_errors():
    flaky = _FlakyTransport(failures=1, exc=httpx.ConnectError("reset"))
    async with httpx.AsyncClient(transport=RetryTransport(transport=flaky)) as client:
        res = await client.get("https://api.example.com/x")
    assert res.status_code == 200
    assert flaky.calls == 2


@pytest.mark.asyncio
async def test_retry_transport_gives_up_after_max_retries():
    flaky = _FlakyTransport(failures=99)
    transport = RetryTransport(transport=flaky, max_retries=2)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await client.get("https://api.example.com/x")
    # Exhausted retries surface the last retryable response, not a crash
    assert res.status_code == 503
    assert flaky.calls == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_retry_transport_honors_retry_after_header():
    class RateLimited(httpx.AsyncBaseTransport):
        def __init__(self):
            self.calls = 0

        async def handle_async_request(self, request):
            self.calls += 1
            if self.calls == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    request=request,
                )
            return httpx.Response(200, json={"ok": True}, request=request)

    inner = RateLimited()
    async with httpx.AsyncClient(transport=RetryTransport(transport=inner)) as client:
        res = await client.get("https://api.example.com/x")
    assert res.status_code == 200
    assert inner.calls == 2


def test_retry_after_numeric_date_and_absent():
    """Retry-After honors seconds and HTTP-date forms; absent header
    backs off exponentially by attempt."""
    import httpx
    from app.mcp.connectors.http import RetryTransport

    def resp(headers):
        return httpx.Response(503, headers=headers)

    assert RetryTransport._retry_after_seconds(resp({"Retry-After": "2"}), 1) == 2.0
    assert RetryTransport._retry_after_seconds(resp({"Retry-After": "120"}), 1) == 8.0
    future = resp({"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"})
    assert 0 < RetryTransport._retry_after_seconds(future, 1) <= 8.0
    d1 = RetryTransport._retry_after_seconds(resp({}), 1)
    d3 = RetryTransport._retry_after_seconds(resp({}), 3)
    assert 0 < d1 < d3 <= 8.0
