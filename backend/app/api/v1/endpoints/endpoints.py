import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.crypto import generate_endpoint_slug, generate_signing_secret
from app.models.endpoint import Endpoint
from app.models.webhook_event import WebhookEvent
from app.schemas.endpoint import (
    EndpointCreate,
    EndpointRead,
    EndpointStats,
    EndpointUpdate,
)

logger = logging.getLogger("hookpulse.endpoints")

router = APIRouter()


async def get_stats_map(session: AsyncSession) -> dict:
    """Aggregates event counts grouped by endpoint_id."""
    stmt = (
        select(
            WebhookEvent.endpoint_id,
            func.count(WebhookEvent.id).label("total"),
            func.count(case((WebhookEvent.status == "PENDING", 1))).label("pending"),
            func.count(case((WebhookEvent.status == "DELIVERED", 1))).label("delivered"),
            func.count(case((WebhookEvent.status == "RETRYING", 1))).label("retrying"),
            func.count(case((WebhookEvent.status == "DLQ", 1))).label("dlq"),
        )
        .group_by(WebhookEvent.endpoint_id)
    )
    result = await session.execute(stmt)
    stats_map = {}
    for row in result.all():
        stats_map[row.endpoint_id] = EndpointStats(
            total_events=row.total,
            pending_count=row.pending,
            delivered_count=row.delivered,
            retrying_count=row.retrying,
            dlq_count=row.dlq,
        )
    return stats_map


@router.get("", response_model=List[EndpointRead])
async def list_endpoints(
    session: AsyncSession = Depends(get_db_session),
) -> List[EndpointRead]:
    """
    List all configured endpoints/tunnels along with their current event statistics.
    """
    endpoints_stmt = select(Endpoint).order_by(Endpoint.created_at.desc())
    endpoints_res = await session.execute(endpoints_stmt)
    endpoints = endpoints_res.scalars().all()

    stats_map = await get_stats_map(session)

    results: List[EndpointRead] = []
    for ep in endpoints:
        ep_read = EndpointRead.model_validate(ep)
        ep_read.stats = stats_map.get(ep.id, EndpointStats())
        results.append(ep_read)

    return results


@router.post("", response_model=EndpointRead, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    endpoint_in: EndpointCreate,
    session: AsyncSession = Depends(get_db_session),
) -> EndpointRead:
    """
    Creates a new webhook endpoint.
    If slug or signing_secret are not provided, they are securely generated.
    """
    slug = endpoint_in.slug.strip() if endpoint_in.slug else generate_endpoint_slug(endpoint_in.name)
    signing_secret = (
        endpoint_in.signing_secret.strip()
        if endpoint_in.signing_secret
        else generate_signing_secret()
    )

    # Check for slug collision
    existing_stmt = select(Endpoint).where(Endpoint.slug == slug)
    existing_res = await session.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Endpoint with slug '{slug}' already exists.",
        )

    endpoint = Endpoint(
        slug=slug,
        name=endpoint_in.name,
        target_url=str(endpoint_in.target_url),
        signing_secret=signing_secret,
        is_active=True,
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)

    ep_read = EndpointRead.model_validate(endpoint)
    ep_read.stats = EndpointStats()
    return ep_read


@router.get("/{slug}", response_model=EndpointRead)
async def get_endpoint(
    slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> EndpointRead:
    """
    Retrieve single endpoint details and stats by slug.
    """
    stmt = select(Endpoint).where(Endpoint.slug == slug)
    res = await session.execute(stmt)
    endpoint = res.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint '{slug}' not found.",
        )

    stats_map = await get_stats_map(session)
    ep_read = EndpointRead.model_validate(endpoint)
    ep_read.stats = stats_map.get(endpoint.id, EndpointStats())
    return ep_read


@router.patch("/{slug}", response_model=EndpointRead)
async def update_endpoint(
    slug: str,
    update_in: EndpointUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> EndpointRead:
    """
    Update endpoint settings (name, target_url, active status).
    """
    stmt = select(Endpoint).where(Endpoint.slug == slug)
    res = await session.execute(stmt)
    endpoint = res.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint '{slug}' not found.",
        )

    if update_in.name is not None:
        endpoint.name = update_in.name
    if update_in.target_url is not None:
        endpoint.target_url = str(update_in.target_url)
    if update_in.is_active is not None:
        endpoint.is_active = update_in.is_active

    await session.commit()
    await session.refresh(endpoint)

    stats_map = await get_stats_map(session)
    ep_read = EndpointRead.model_validate(endpoint)
    ep_read.stats = stats_map.get(endpoint.id, EndpointStats())
    return ep_read
