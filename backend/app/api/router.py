"""Main API router combining all endpoint modules."""
from fastapi import APIRouter
from .endpoints.batches import router as batches_router
from .endpoints.history import router as history_router
from .endpoints.connectors import router as connectors_router
from .endpoints.ingest_exports import router as ingest_exports_router
from .endpoints.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(batches_router)
api_router.include_router(history_router)
api_router.include_router(connectors_router)
api_router.include_router(ingest_exports_router)
api_router.include_router(webhooks_router)
