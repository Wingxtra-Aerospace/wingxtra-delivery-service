import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProofOfDeliveryMethod(str, enum.Enum):
    PHOTO = "PHOTO"
    OTP = "OTP"
    OPERATOR_CONFIRM = "OPERATOR_CONFIRM"


class ProofOfDelivery(Base):
    __tablename__ = "proof_of_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[ProofOfDeliveryMethod] = mapped_column(
        Enum(ProofOfDeliveryMethod, name="proof_of_delivery_method"), nullable=False
    )
    photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
