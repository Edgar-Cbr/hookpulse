from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Identity, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.webhook_event import WebhookEvent


class DeliveryAttempt(Base):
    """
    SQLAlchemy 2.0 model representing a delivery dispatch attempt to target_url.
    Stores status codes, response snippets, latency, and connection errors.
    """
    __tablename__ = "delivery_attempts"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=1, cycle=False),
        primary_key=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_events.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    response_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    response_body: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship back to the parent WebhookEvent
    event: Mapped["WebhookEvent"] = relationship(
        "WebhookEvent",
        back_populates="attempts",
    )

    def __repr__(self) -> str:
        return f"<DeliveryAttempt id={self.id} event_id={self.event_id} attempt={self.attempt_number} status={self.response_status}>"
