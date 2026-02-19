import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus


class PublicTrackingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    public_tracking_id: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
