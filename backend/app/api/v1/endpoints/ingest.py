import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.crypto import verify_hmac_signature
from app.core.redis import publish_endpoint_event
from app.models.endpoint import Endpoint
from app.models.webhook_event import WebhookEvent
from app.schemas.event import IngestResponse

logger = logging.getLogger("hookpulse.ingest")

router = APIRouter()


@router.post("/ingest/{slug}", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_webhook(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    x_webhook_signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_event_type: str | None = Header(default=None, alias="X-Event-Type"),
) -> IngestResponse:
    """
    High-speed webhook ingestion endpoint.
    1. Extracts raw body and headers.
    2. Validates constant-time HMAC-SHA256 signature against endpoint secret.
    3. Persists WebhookEvent to PostgreSQL with 'PENDING' state.
    4. Emits real-time event via Redis Pub/Sub to WebSockets.
    5. Returns 202 Accepted in under 15ms.
    """
    # 1. Fetch active endpoint
    stmt = select(Endpoint).where(Endpoint.slug == slug, Endpoint.is_active.is_(True))
    result = await session.execute(stmt)
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active webhook endpoint '{slug}' not found.",
        )

    # 2. Extract raw bytes & headers
    raw_body = await request.body()
    signature_header = x_webhook_signature or x_hub_signature_256

    # 3. Constant-time HMAC-SHA256 signature verification
    is_valid_sig = verify_hmac_signature(
        secret=endpoint.signing_secret,
        raw_body=raw_body,
        provided_sig=signature_header,
    )

    # 4. Parse payload
    payload_data: Dict[str, Any] = {}
    if raw_body:
        try:
            payload_data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            payload_data = {"raw_content": raw_body.decode("utf-8", errors="replace")}

    # 5. Determine event type
    event_type = (
        x_event_type
        or payload_data.get("event_type")
        or payload_data.get("type")
        or payload_data.get("event")
        or "webhook.generic"
    )

    # Convert request headers to serializable dict
    headers_dict = dict(request.headers)

    # 6. Persist WebhookEvent
    event = WebhookEvent(
        endpoint_id=endpoint.id,
        event_type=str(event_type),
        headers=headers_dict,
        payload=payload_data,
        signature_valid=is_valid_sig,
        status="PENDING",
        retry_count=0,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    # 7. Publish to Redis Pub/Sub for immediate WebSocket broadcast
    ws_message = {
        "type": "event.created",
        "slug": slug,
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
            "attempts": [],
        },
    }
    await publish_endpoint_event(slug, ws_message)
    logger.info(f"Ingested webhook {event.id} on '{slug}' [HMAC valid={is_valid_sig}]")

    # 8. Return 202 Accepted
    return IngestResponse(
        event_id=event.id,
        status=event.status,
        signature_valid=event.signature_valid,
        message="Webhook accepted for processing",
    )
