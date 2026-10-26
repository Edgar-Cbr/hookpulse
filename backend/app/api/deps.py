from typing import AsyncGenerator
from fastapi import Depends
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.session import get_db

# Re-export database and redis dependencies for clean injection in endpoints
SessionDep = Depends(get_db)
RedisDep = Depends(get_redis)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency helper for database session."""
    async for session in get_db():
        yield session


async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """Dependency helper for redis client."""
    async for client in get_redis():
        yield client
