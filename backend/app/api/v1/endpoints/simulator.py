"""
Traffic Simulator and Mock Target Receiver for HookPulse.
Provides realistic TaxGuard webhook generator and configurable destination mock (200 OK / 500 Error).
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Literal, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.crypto import compute_hmac_signature, verify_hmac_signature
from app.core.redis import publish_endpoint_event
from app.models.endpoint import Endpoint
from app.models.webhook_event import WebhookEvent
from app.schemas.simulator import MockTargetResponse, SimulatorTriggerRequest, SimulatorTriggerResponse
from app.services.delivery_engine import dispatch_webhook_event

logger = logging.getLogger("hookpulse.simulator")

router = APIRouter()


def generate_taxguard_payload() -> Dict[str, Any]:
    """Generates realistic tax_id.batch.completed payload from TaxGuard API."""
    unique_suffix = uuid.uuid4().hex[:8]
    return {
        "specversion": "1.0",
        "id": f"evt_taxguard_{unique_suffix}",
        "source": "https://api.taxguard.io/v1/batches",
        "type": "tax_id.batch.completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "batch_id": f"batch_fiscal_{unique_suffix}",
            "jurisdiction": "MX-SAT",
            "total_records": 1500,
            "processed_records": 1500,
            "valid_count": 1492,
            "invalid_count": 8,
            "blacklisted_rfc_detected": 1,
            "checksum": f"sha256:{uuid.uuid4().hex}",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "report_url": f"https://reports.taxguard.io/exports/batch_fiscal_{unique_suffix}.csv",
        },
    }


@router.post(
    "/trigger",
    response_model=SimulatorTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger simulated webhook traffic",
)
async def trigger_simulated_webhook(
    req: SimulatorTriggerRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> SimulatorTriggerResponse:
    """
    Simulates incoming webhook traffic:
    1. Fetches target endpoint by slug.
    2. Builds TaxGuard fiscal verification payload or uses custom payload.
    3. Dynamically syncs behavior ('success' or 'fail') with mock-target URL.
    4. Computes constant-time HMAC-SHA256 signature if requested.
    5. Persists WebhookEvent, publishes real-time WebSocket notice, and triggers background dispatch.
    """
    stmt = select(Endpoint).where(Endpoint.slug == req.endpoint_slug, Endpoint.is_active.is_(True))
    result = await session.execute(stmt)
    endpoint = result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target endpoint '{req.endpoint_slug}' not found.",
        )

    # If endpoint points to mock-target, adjust behavior param accordingly
    if "mock-target" in endpoint.target_url:
        base_url = endpoint.target_url.split("?")[0]
        endpoint.target_url = f"{base_url}?behavior={req.behavior}"
        session.add(endpoint)
        await session.commit()
        await session.refresh(endpoint)

    # Generate payload
    payload_dict = req.custom_payload or generate_taxguard_payload()
    raw_payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")

    # Compute or forge signature
    if req.sign_hmac:
        sig_hex = compute_hmac_signature(endpoint.signing_secret, raw_payload_bytes)
        signature_header = f"sha256={sig_hex}"
        signature_valid = True
    else:
        signature_header = "sha256=invalid_simulated_signature_0000000000000000"
        signature_valid = False

    # Persist event
    headers = {
        "content-type": "application/json",
        "user-agent": "HookPulse-Simulator/1.0",
        "x-webhook-signature": signature_header,
        "x-hub-signature-256": signature_header,
        "x-event-type": req.event_type,
    }

    event = WebhookEvent(
        endpoint_id=endpoint.id,
        event_type=req.event_type,
        headers=headers,
        payload=payload_dict,
        signature_valid=signature_valid,
        status="PENDING",
        retry_count=0,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    # Broadcast event.created to Redis Pub/Sub
    ws_notice = {
        "type": "event.created",
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
            "next_retry_at": None,
            "created_at": event.created_at.isoformat(),
            "attempts": [],
        },
    }
    await publish_endpoint_event(endpoint.slug, ws_notice)
    logger.info(f"Simulated webhook event created: {event.id} ({req.behavior})")

    # Schedule immediate delivery attempt
    background_tasks.add_task(dispatch_webhook_event, event.id)

    return SimulatorTriggerResponse(
        event_id=event.id,
        status=event.status,
        event_type=event.event_type,
        behavior=req.behavior,
        target_url=endpoint.target_url,
        signature_header=signature_header,
        message=f"Simulated webhook triggered successfully in '{req.behavior}' mode.",
    )


@router.post(
    "/mock-target",
    summary="Configurable mock receiver for webhook delivery testing",
)
async def mock_target_receiver(
    request: Request,
    behavior: Literal["success", "fail"] = Query(default="success", description="Expected mock behavior"),
    body: Optional[Dict[str, Any]] = Body(default=None),
) -> JSONResponse:
    """
    Mock destination server for HookPulse webhook dispatches.
    - If ?behavior=success: responds with 200 OK.
    - If ?behavior=fail: responds with 500 Internal Server Error (triggers HookPulse exponential backoff).
    """
    now = datetime.now(timezone.utc)

    if behavior == "fail":
        logger.warning("MockTarget received webhook and returned simulated HTTP 500 error.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "received": False,
                "behavior": "fail",
                "status_code": 500,
                "timestamp": now.isoformat(),
                "message": "Simulated downstream internal server failure. Retrying expected.",
                "body_received": body,
            },
        )

    logger.info("MockTarget received webhook and returned HTTP 200 OK.")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "received": True,
            "behavior": "success",
            "status_code": 200,
            "timestamp": now.isoformat(),
            "message": "Webhook delivered successfully to mock destination.",
            "body_received": body,
        },
    )
