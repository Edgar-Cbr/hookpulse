import asyncio
from collections import defaultdict
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis import get_endpoint_channel, get_redis_client

logger = logging.getLogger("hookpulse.ws")

websocket_router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections grouped by endpoint slug."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, slug: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[slug].add(websocket)
        logger.info(f"WebSocket connected for endpoint '{slug}'. Total clients for slug: {len(self.active_connections[slug])}")

    def disconnect(self, slug: str, websocket: WebSocket) -> None:
        if slug in self.active_connections:
            self.active_connections[slug].discard(websocket)
            if not self.active_connections[slug]:
                del self.active_connections[slug]
        logger.info(f"WebSocket disconnected from endpoint '{slug}'.")

    async def broadcast_to_slug(self, slug: str, message: str) -> None:
        if slug not in self.active_connections:
            return

        dead_connections: Set[WebSocket] = set()
        for connection in self.active_connections[slug]:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(slug, dead)


manager = ConnectionManager()


@websocket_router.websocket("/ws/endpoints/{slug}")
async def websocket_endpoint(websocket: WebSocket, slug: str):
    """
    Subscribes the WebSocket connection to the Redis Pub/Sub channel for the given slug.
    Streams new webhook events, retry transitions, and delivery attempts in real-time.
    """
    await manager.connect(slug, websocket)

    redis_client = await get_redis_client()
    pubsub = redis_client.pubsub()
    channel_name = get_endpoint_channel(slug)

    async def redis_listener():
        """Listens to Redis Pub/Sub channel and forwards JSON strings to WebSocket."""
        try:
            await pubsub.subscribe(channel_name)
            logger.info(f"Subscribed Redis pubsub to channel '{channel_name}'")
            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await websocket.send_text(str(data))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Error in Redis listener for slug '{slug}': {e}")
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
                await pubsub.aclose()
                await redis_client.aclose()
            except Exception:
                pass

    listener_task = asyncio.create_task(redis_listener())

    try:
        # Keep connection alive and receive client pings/messages
        while True:
            client_msg = await websocket.receive_text()
            if client_msg == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket stream: {slug}")
    except Exception as exc:
        logger.warning(f"WebSocket unexpected error for {slug}: {exc}")
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(slug, websocket)
