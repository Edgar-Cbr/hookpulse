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
