from fastapi import APIRouter

from app.api.v1.endpoints.endpoints import router as endpoints_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.ingest import router as ingest_router

api_v1_router = APIRouter()

# Mount endpoints CRUD
api_v1_router.include_router(endpoints_router, prefix="/endpoints", tags=["Endpoints"])

# Mount event history & inspect
api_v1_router.include_router(events_router, tags=["Events"])

# Also mount ingest under v1 for convenience (/api/v1/ingest/{slug})
api_v1_router.include_router(ingest_router, tags=["Ingestion"])
