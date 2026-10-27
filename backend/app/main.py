import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.api.v1.endpoints.ingest import router as ingest_router
from app.api.v1.router import api_v1_router
from app.api.ws import websocket_router
from app.core.config import settings
from app.core.redis import close_redis, get_redis_client
from app.db.base import Base
from app.db.session import AsyncSessionLocal, async_engine
import app.models  # Register all models with Base.metadata
from app.models.endpoint import Endpoint
from app.services.delivery_engine import retry_worker_loop

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hookpulse")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI Lifespan Context Manager.
    - Initializes database tables (SQLAlchemy 2.0).
    - Seeds default TaxGuard endpoint for out-of-the-box operation.
    - Handles graceful shutdown of DB and Redis connections.
    """
    logger.info("Initializing HookPulse backend engine...")

    # Auto-initialize database tables
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified and initialized successfully.")
    except Exception as exc:
        logger.warning(f"Database table auto-initialization deferred or failed: {exc}")

    # Seed default endpoint (TaxGuard Fiscal Webhook)
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Endpoint).where(Endpoint.slug == settings.DEFAULT_ENDPOINT_SLUG)
            result = await session.execute(stmt)
            endpoint = result.scalar_one_or_none()
            if not endpoint:
                endpoint = Endpoint(
                    slug=settings.DEFAULT_ENDPOINT_SLUG,
                    name=settings.DEFAULT_ENDPOINT_NAME,
                    target_url=settings.DEFAULT_TARGET_URL,
                    signing_secret=settings.DEFAULT_SIGNING_SECRET,
                    is_active=True,
                )
                session.add(endpoint)
                await session.commit()
                logger.info(f"Default seed endpoint created: {settings.DEFAULT_ENDPOINT_SLUG}")
            else:
                logger.info(f"Default seed endpoint already present: {settings.DEFAULT_ENDPOINT_SLUG}")
    except Exception as exc:
        logger.warning(f"Default endpoint seeding deferred or failed: {exc}")

    # Start background retry worker loop
    worker_task = asyncio.create_task(retry_worker_loop(poll_interval=2.0))
    logger.info("Background retry worker loop registered in lifespan.")

    yield

    logger.info("Shutting down HookPulse services...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    await async_engine.dispose()
    logger.info("HookPulse shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Real-time webhook gateway, live payload inspector & resilient delivery engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public high-speed ingest route: POST /ingest/{slug}
app.include_router(ingest_router)

# Versioned API: /api/v1/...
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Real-time WebSocket route: WS /ws/endpoints/{slug}
app.include_router(websocket_router)


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "ingest_sample": "/ingest/{slug}",
        "ws_sample": "/ws/endpoints/{slug}",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint verifying PostgreSQL and Redis availability.
    Returns 200 OK if both services are responsive.
    """
    pg_healthy = False
    redis_healthy = False

    # Check PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                pg_healthy = True
    except Exception as exc:
        logger.warning(f"PostgreSQL health check failed: {exc}")

    # Check Redis
    try:
        redis_client = await get_redis_client()
        pong = await redis_client.ping()
        if pong:
            redis_healthy = True
        await redis_client.aclose()
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")

    is_ok = pg_healthy and redis_healthy
    status_code = status.HTTP_200_OK if is_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if is_ok else "degraded",
            "postgres": pg_healthy,
            "redis": redis_healthy,
        },
    )
