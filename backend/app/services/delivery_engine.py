"""
Resilient Webhook Delivery Engine for HookPulse.
Handles asynchronous HTTP dispatch via httpx, latency measurement,
DeliveryAttempt persistence, exponential backoff evaluation, and real-time Redis Pub/Sub broadcasts.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Optional
import uuid

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.crypto import compute_hmac_signature
from app.core.redis import publish_endpoint_event
from app.db.session import AsyncSessionLocal
from app.models.delivery_attempt import DeliveryAttempt
from app.models.endpoint import Endpoint
from app.models.webhook_event import WebhookEvent
from app.services.backoff import compute_retry_state

logger = logging.getLogger("hookpulse.delivery_engine")

HTTP_TIMEOUT_SECONDS = 10.0


async def dispatch_webhook_event(
    event_id: uuid.UUID,
    session: Optional[AsyncSession] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[DeliveryAttempt]:
    """
    Executes a single delivery attempt for the given WebhookEvent against its endpoint target_url.
    1. Loads the event and associated endpoint.
    2. Constructs HTTP request with standard HookPulse headers and HMAC-SHA256 signature.
    3. Measures execution latency in milliseconds.
    4. Evaluates response status; updates event state (DELIVERED, RETRYING, or DLQ).
    5. Records DeliveryAttempt record in PostgreSQL.
    6. Emits real-time notification on Redis Pub/Sub for connected WebSocket clients.
    """
    if session is None:
        async with AsyncSessionLocal() as local_session:
            return await _execute_dispatch(event_id, local_session, client)
    else:
        return await _execute_dispatch(event_id, session, client)


async def _execute_dispatch(
    event_id: uuid.UUID,
    session: AsyncSession,
    external_client: Optional[httpx.AsyncClient] = None,
) -> Optional[DeliveryAttempt]:
    # 1. Fetch event with attempts and endpoint
    stmt = (
        select(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .options(selectinload(WebhookEvent.attempts), selectinload(WebhookEvent.endpoint))
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        logger.warning(f"Dispatch aborted: WebhookEvent {event_id} not found.")
        return None

    endpoint: Endpoint = event.endpoint
    if not endpoint:
        logger.warning(f"Dispatch aborted: Endpoint for WebhookEvent {event_id} not found.")
        return None

    attempt_number = len(event.attempts) + 1

    # 2. Prepare payload & HMAC signature
    payload_dict = event.payload or {}
    raw_payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    signature = compute_hmac_signature(endpoint.signing_secret, raw_payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "HookPulse-Delivery-Engine/1.0",
        "X-Webhook-Event-ID": str(event.id),
        "X-Webhook-Delivery-Attempt": str(attempt_number),
        "X-Webhook-Signature": signature,
        "X-Event-Type": event.event_type,
    }

    # 3. Perform HTTP Dispatch
    status_code: Optional[int] = None
    response_body_snippet: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0

    start_time = time.perf_counter()

    async def _send_request(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(
            url=endpoint.target_url,
            content=raw_payload_bytes,
            headers=headers,
            timeout=HTTP_TIMEOUT_SECONDS,
        )

    try:
        if external_client is not None:
            resp = await _send_request(external_client)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as new_client:
                resp = await _send_request(new_client)

        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000.0, 2)
        status_code = resp.status_code
        response_body_snippet = resp.text[:1000] if resp.text else None

        if 200 <= status_code < 300:
            # Successful delivery
            event.status = "DELIVERED"
            event.next_retry_at = None
            logger.info(
                f"[Attempt #{attempt_number}] SUCCESS {status_code} for event {event.id} -> {endpoint.target_url} ({latency_ms}ms)"
            )
        else:
            # Target responded with 4xx or 5xx
            error_message = f"Target returned HTTP status {status_code}"
            decision = compute_retry_state(event.retry_count)
            event.status = decision.status
            event.retry_count = decision.new_retry_count
            event.next_retry_at = decision.next_retry_at
            logger.warning(
                f"[Attempt #{attempt_number}] FAILED {status_code} for event {event.id}: {error_message}. Transitioned to {event.status} ({latency_ms}ms)"
            )

    except (httpx.RequestError, httpx.TimeoutException) as exc:
        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000.0, 2)
        error_message = f"{exc.__class__.__name__}: {str(exc)}"[:500]
        decision = compute_retry_state(event.retry_count)
        event.status = decision.status
        event.retry_count = decision.new_retry_count
        event.next_retry_at = decision.next_retry_at
        logger.warning(
            f"[Attempt #{attempt_number}] CONNECTION ERROR for event {event.id}: {error_message}. Transitioned to {event.status} ({latency_ms}ms)"
        )

    except Exception as exc:
        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000.0, 2)
        error_message = f"UnexpectedDispatchError: {str(exc)}"[:500]
        decision = compute_retry_state(event.retry_count)
        event.status = decision.status
        event.retry_count = decision.new_retry_count
        event.next_retry_at = decision.next_retry_at
        logger.error(
            f"[Attempt #{attempt_number}] UNEXPECTED ERROR for event {event.id}: {error_message}. Transitioned to {event.status}"
        )

    # 4. Record DeliveryAttempt
    attempt = DeliveryAttempt(
        event_id=event.id,
        attempt_number=attempt_number,
        response_status=status_code,
        response_body=response_body_snippet,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    await session.refresh(event)

    # Reload attempts for full WS payload consistency
    all_attempts_stmt = (
        select(DeliveryAttempt)
        .where(DeliveryAttempt.event_id == event.id)
        .order_by(DeliveryAttempt.attempt_number.asc())
    )
    all_attempts_res = await session.execute(all_attempts_stmt)
    all_attempts = all_attempts_res.scalars().all()

    # 5. Broadcast real-time update to Redis Pub/Sub for WebSockets
    ws_update = {
        "type": "event.updated",
        "slug": endpoint.slug,
        "event": {
            "id": str(event.id),
            "endpoint_id": str(event.endpoint_id),
            "event_type": event.event_type,
            "headers": event.headers,
            "payload": event.payload,
            "signature_valid": event.signature_valid,
            "status": event.status,
            "retry_count": event.retry_count,
            "next_retry_at": event.next_retry_at.isoformat() if event.next_retry_at else None,
            "created_at": event.created_at.isoformat(),
            "attempts": [
                {
                    "id": a.id,
                    "event_id": str(a.event_id),
                    "attempt_number": a.attempt_number,
                    "response_status": a.response_status,
                    "response_body": a.response_body,
                    "latency_ms": a.latency_ms,
                    "error_message": a.error_message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in all_attempts
            ],
        },
        "latest_attempt": {
            "id": attempt.id,
            "event_id": str(attempt.event_id),
            "attempt_number": attempt.attempt_number,
            "response_status": attempt.response_status,
            "response_body": attempt.response_body,
            "latency_ms": attempt.latency_ms,
            "error_message": attempt.error_message,
            "created_at": attempt.created_at.isoformat(),
        },
    }
    await publish_endpoint_event(endpoint.slug, ws_update)

    return attempt


async def _poll_and_dispatch_retries() -> None:
    """
    Finds pending WebhookEvents scheduled for retry where next_retry_at <= now()
    and triggers an asynchronous delivery dispatch for each.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(WebhookEvent.id)
            .where(
                WebhookEvent.status == "RETRYING",
                WebhookEvent.next_retry_at.is_not(None),
                WebhookEvent.next_retry_at <= now,
            )
            .order_by(WebhookEvent.next_retry_at.asc())
            .limit(20)
        )
        result = await session.execute(stmt)
        event_ids = result.scalars().all()

    if event_ids:
        logger.info(f"Retry worker detected {len(event_ids)} event(s) due for re-dispatch.")
        for eid in event_ids:
            try:
                await dispatch_webhook_event(eid)
            except Exception as exc:
                logger.error(f"Error re-dispatching event {eid} in retry loop: {exc}", exc_info=True)


async def retry_worker_loop(poll_interval: float = 2.0) -> None:
    """
    Continuous background loop that polls for retriable webhook events.
    Runs during the FastAPI application lifespan until shutdown.
    """
    logger.info(f"Background retry worker started (interval: {poll_interval}s).")
    try:
        while True:
            try:
                await _poll_and_dispatch_retries()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"Unexpected error in retry polling loop: {exc}", exc_info=True)

            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        logger.info("Background retry worker received cancellation. Shutting down gracefully.")

