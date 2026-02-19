import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DeliveryJob(Base):
    __tablename__ = "delivery_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_drone_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mission_intent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eta_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[DeliveryJobStatus] = mapped_column(
        Enum(DeliveryJobStatus, name="delivery_job_status"),
        nullable=False,
        default=DeliveryJobStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
