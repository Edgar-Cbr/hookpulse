from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EndpointStats(BaseModel):
    """Aggregated statistics for an endpoint."""
    total_events: int = 0
    pending_count: int = 0
    delivered_count: int = 0
    retrying_count: int = 0
    dlq_count: int = 0


class EndpointBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Human-readable name")
    target_url: str = Field(..., max_length=500, description="Destination URL to forward webhooks")


class EndpointCreate(EndpointBase):
    slug: Optional[str] = Field(None, min_length=3, max_length=40, description="Custom unique slug or auto-generated")
    signing_secret: Optional[str] = Field(None, max_length=128, description="Custom secret or auto-generated whsec_...")


class EndpointUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    target_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class EndpointRead(EndpointBase):
    id: uuid.UUID
    slug: str
    signing_secret: str
    is_active: bool
    created_at: datetime
    stats: Optional[EndpointStats] = None

    model_config = ConfigDict(from_attributes=True)
