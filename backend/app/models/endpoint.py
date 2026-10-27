from datetime import datetime
from typing import TYPE_CHECKING, List
import uuid

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.webhook_event import WebhookEvent


class Endpoint(Base):
    """
    SQLAlchemy 2.0 model representing a Webhook Ingestion Endpoint / Tunnel.
    """
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    target_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    signing_secret: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to incoming webhook events
    events: Mapped[List["WebhookEvent"]] = relationship(
        "WebhookEvent",
        back_populates="endpoint",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Endpoint slug={self.slug} name={self.name} active={self.is_active}>"
