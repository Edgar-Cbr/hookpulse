from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DeliveryAttemptRead(BaseModel):
    id: int
    event_id: uuid.UUID
    attempt_number: int
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    latency_ms: float
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookEventRead(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    headers: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    signature_valid: bool
    status: str
    retry_count: int
    next_retry_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookEventDetail(WebhookEventRead):
    attempts: List[DeliveryAttemptRead] = Field(default_factory=list)


class IngestResponse(BaseModel):
    event_id: uuid.UUID
    status: str
    signature_valid: bool
    message: str = "Webhook accepted for processing"


class ReplayResponse(BaseModel):
    event_id: uuid.UUID
    status: str
    attempt_number: int
    message: str
    event: Optional[WebhookEventDetail] = None
