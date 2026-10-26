from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.delivery_attempt import DeliveryAttempt
    from app.models.endpoint import Endpoint


class WebhookEvent(Base):
    """
    SQLAlchemy 2.0 model representing an incoming webhook event.
    Tracks payload, verification status, and retry state machine.
    """
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("endpoints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    headers: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    signature_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        index=True,
        default="PENDING",
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    # Relationships
    endpoint: Mapped["Endpoint"] = relationship(
        "Endpoint",
        back_populates="events",
    )
    attempts: Mapped[List["DeliveryAttempt"]] = relationship(
        "DeliveryAttempt",
        back_populates="event",
        cascade="all, delete-cascade",
        order_by="DeliveryAttempt.attempt_number",
    )

    def __repr__(self) -> str:
        return f"<WebhookEvent id={self.id} type={self.event_type} status={self.status} retries={self.retry_count}>"
