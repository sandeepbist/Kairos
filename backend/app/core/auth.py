"""API-key authentication dependency and security utilities.

Single-operator model: one bearer token (``API_KEY``) gates every
non-health endpoint. The key is compared in constant time to avoid
timing side channels, and absent from logs and error responses.
"""
import hashlib
import hmac
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from app.config import settings

logger = logging.getLogger(__name__)

# Header form is preferred; query param supported for curl/demos and SSE.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="api_key", auto_error=False)

# Endpoints exempt from authentication (liveness/readiness probes)
PUBLIC_PATHS: frozenset[str] = frozenset(
    {"/api/health", "/docs", "/redoc", "/openapi.json"}
)


def _key_digest(value: str) -> bytes:
    """Hash keys before comparison so raw secrets never hit string compare."""
    return hashlib.sha256(value.encode("utf-8")).digest()


def _configured_key_digest() -> bytes | None:
    if settings.API_KEY:
        return _key_digest(settings.API_KEY)
    return None


async def require_api_key(
    request: Request,
    header_key: str | None = Depends(_api_key_header),
    query_key: str | None = Depends(_api_key_query),
) -> str:
    """Rejects the request unless a valid operator API key is presented.

    When no API_KEY is configured (local development only), the request
    is allowed through with a warning, so a fresh checkout still boots.
    Production config validation guarantees this cannot happen there.
    """
    provided = header_key or query_key
    expected_digest = _configured_key_digest()

    if expected_digest is None:
        if settings.is_production:
            # Defensive: config validation should have blocked startup.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication is not configured.",
            )
        logger.debug("Auth disabled (no API_KEY configured); allowing request.")
        return "anonymous"

    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not hmac.compare_digest(_key_digest(provided), expected_digest):
        logger.warning(
            "Rejected request with invalid API key: %s %s",
            request.method,
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return "operator"
