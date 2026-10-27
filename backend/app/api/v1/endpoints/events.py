import logging
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.models.endpoint import Endpoint
from app.models.webhook_event import WebhookEvent
from app.schemas.event import WebhookEventDetail
from app.services.delivery_engine import dispatch_webhook_event

logger = logging.getLogger("hookpulse.events")

router = APIRouter()


@router.get("/endpoints/{slug}/events", response_model=List[WebhookEventDetail])
async def list_endpoint_events(
    slug: str,
    limit: int = Query(default=50, ge=1, le=100, description="Max events to return"),
    session: AsyncSession = Depends(get_db_session),
) -> List[WebhookEventDetail]:
    """
    Retrieve the last N events for a given endpoint slug, including all delivery attempts.
    Uses selectinload for optimized eager-loading of attempt timelines.
    """
    # Verify endpoint exists
    ep_stmt = select(Endpoint).where(Endpoint.slug == slug)
    ep_res = await session.execute(ep_stmt)
    endpoint = ep_res.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint '{slug}' not found.",
        )

    # Query events with loaded delivery attempts
    stmt = (
        select(WebhookEvent)
        .where(WebhookEvent.endpoint_id == endpoint.id)
        .options(selectinload(WebhookEvent.attempts))
        .order_by(WebhookEvent.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    return [WebhookEventDetail.model_validate(e) for e in events]


@router.get("/events/{event_id}", response_model=WebhookEventDetail)
async def get_event_detail(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookEventDetail:
    """
    Retrieve a specific webhook event by ID with its complete delivery attempts timeline.
    """
    stmt = (
        select(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .options(selectinload(WebhookEvent.attempts))
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found.",
        )

    return WebhookEventDetail.model_validate(event)


@router.post("/events/{event_id}/replay", response_model=WebhookEventDetail, status_code=status.HTTP_200_OK)
async def replay_webhook_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> WebhookEventDetail:
    """
    Manual Webhook Replay Endpoint.
    Forces an immediate delivery attempt for an event in DLQ or DELIVERED state.
    Updates the event state, logs a new DeliveryAttempt, notifies WebSocket subscribers,
    and returns the updated event with its refreshed timeline.
    """
    stmt = (
        select(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .options(selectinload(WebhookEvent.attempts))
    )
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' not found.",
        )

    logger.info(f"Manual replay triggered for event {event_id} (current status: {event.status})")

    # Dispatch the delivery attempt immediately
    attempt = await dispatch_webhook_event(event_id=event.id)
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute replay dispatch for this event.",
        )

    # Reload fresh state with attempts
    session.expire_all()
    reloaded_res = await session.execute(stmt)
    updated_event = reloaded_res.scalar_one()

    return WebhookEventDetail.model_validate(updated_event)

