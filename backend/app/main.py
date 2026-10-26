from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.redis import close_redis, get_redis_client
from app.db.session import AsyncSessionLocal, async_engine

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hookpulse")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI Lifespan Context Manager.
    Handles startup infrastructure checks and clean shutdown.
    """
    logger.info("Initializing HookPulse backend engine...")
    yield
    logger.info("Shutting down HookPulse services...")
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


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
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
