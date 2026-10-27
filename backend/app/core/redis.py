import json
import logging
from typing import Any, AsyncGenerator, Union
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger("hookpulse.redis")

# Global redis connection pool
redis_pool: redis.ConnectionPool | None = None

EVENT_CHANNEL_PREFIX = "hookpulse:events:"


def get_endpoint_channel(slug: str) -> str:
    """Returns the Redis Pub/Sub channel name for a specific endpoint slug."""
    return f"{EVENT_CHANNEL_PREFIX}{slug}"


def get_redis_pool() -> redis.ConnectionPool:
    global redis_pool
    if redis_pool is None:
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
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
        subscribers = await client.publish(channel, payload)
        logger.debug(f"Published message to {channel} ({subscribers} active subscribers)")
        return subscribers
    except Exception as exc:
        logger.warning(f"Failed to publish to channel {channel}: {exc}")
        return 0
    finally:
        await client.aclose()


async def publish_endpoint_event(slug: str, event_data: dict[str, Any]) -> int:
    """Publishes a structured event message to an endpoint's specific channel."""
    channel = get_endpoint_channel(slug)
    return await publish_event(channel, event_data)
