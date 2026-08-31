"""FastAPI Application Main Entrypoint for Kairos Backend."""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.auth import require_api_key
from app.core.logging import configure_logging
from app.core.ratelimit import register_security_middleware
from app.api.router import api_router
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: logging, schema init, graceful teardown."""
    configure_logging()
    logger.info(
        "Starting %s (env=%s, sandbox=%s)",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.SANDBOX_MODE,
    )
    await init_db()
    yield
    logger.info("Shutdown signal received; flushing telemetry.")
    from app.core.telemetry import telemetry

    telemetry.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Ambient Action Agent API",
    version="1.0.0",
    lifespan=lifespan,
    # OpenAPI is operator tooling: keep it exposed in dev, hide it in prod
    # unless explicitly re-enabled via env.
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# CORS Configuration: exact origins only (no wildcard) — production values
# come from CORS_ORIGINS env. Credentials disabled since auth is header-key
# based, not cookie-based, so the browser needs no credentialed CORS mode.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
    max_age=600,
)

# Security headers + rate limiting
register_security_middleware(app)

# Mount API routes behind the API key dependency. Applying it here at
# include_router time (not by mutating api_router.dependencies) is what
# actually attaches the guard to every mounted sub-route.
app.include_router(api_router, dependencies=[Depends(require_api_key)])


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse({"detail": "Resource not found."}, status_code=404)


@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestration and monitoring."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "sandbox_mode": settings.SANDBOX_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
