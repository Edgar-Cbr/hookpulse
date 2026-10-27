from datetime import datetime
from typing import Any, Dict, Literal, Optional
import uuid
from pydantic import BaseModel, Field


class SimulatorTriggerRequest(BaseModel):
    """Payload to trigger simulated webhook traffic."""
    endpoint_slug: str = Field(default="ep_taxguard_prod", description="Target endpoint slug")
    behavior: Literal["success", "fail"] = Field(
        default="success",
        description="Delivery behavior: 'success' returns 200, 'fail' returns 500 triggers retries/DLQ",
    )
    event_type: str = Field(
        default="tax_id.batch.completed",
        description="Event type name",
    )
    custom_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional custom JSON payload, defaults to TaxGuard fiscal verification batch",
    )
    sign_hmac: bool = Field(
        default=True,
        description="Whether to generate and include a valid HMAC-SHA256 signature header",
    )


class SimulatorTriggerResponse(BaseModel):
    event_id: uuid.UUID
    status: str
    event_type: str
    behavior: str
    target_url: str
    signature_header: Optional[str] = None
    message: str = "Simulated webhook triggered successfully"


class MockTargetResponse(BaseModel):
    received: bool = True
    behavior: str
    status_code: int
    timestamp: datetime
    message: str
    body_received: Optional[Dict[str, Any]] = None
