import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    MEDICAL = "MEDICAL"


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    CANCELED = "CANCELED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    public_tracking_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )

    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pickup_lat: Mapped[float] = mapped_column(Float, nullable=False)
    pickup_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dropoff_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    payload_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    payload_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[OrderPriority] = mapped_column(
        Enum(OrderPriority, name="order_priority"), nullable=False, default=OrderPriority.NORMAL
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.CREATED
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
