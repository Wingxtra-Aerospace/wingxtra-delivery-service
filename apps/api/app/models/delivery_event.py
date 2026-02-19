import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryEventType(str, enum.Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    MISSION_SUBMITTED = "MISSION_SUBMITTED"
    LAUNCHED = "LAUNCHED"
    ENROUTE = "ENROUTE"
    ARRIVED = "ARRIVED"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("delivery_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[DeliveryEventType] = mapped_column(
        Enum(DeliveryEventType, name="delivery_event_type"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
