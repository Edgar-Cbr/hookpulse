import json
from typing import Any, AsyncGenerator, Union
import redis.asyncio as redis
from app.core.config import settings

# Global redis connection pool
redis_pool: redis.ConnectionPool | None = None


def get_redis_pool() -> redis.ConnectionPool:
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return redis_pool


async def get_redis_client() -> redis.Redis:
    """Returns a redis client instance from the pool."""
    pool = get_redis_pool()
    return redis.Redis(connection_pool=pool)


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Dependency that yields an async redis client."""
    client = await get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis() -> None:
    """Closes redis connection pool on shutdown."""
    global redis_pool
    if redis_pool is not None:
        await redis_pool.disconnect()
        redis_pool = None


async def publish_event(channel: str, message: Union[dict[str, Any], str]) -> int:
    """
    Publishes a message to a Redis Pub/Sub channel.
    If message is a dictionary, it is serialized to JSON string.
    """
    client = await get_redis_client()
    try:
        payload = json.dumps(message) if isinstance(message, dict) else message
        return await client.publish(channel, payload)
    finally:
        await client.aclose()
