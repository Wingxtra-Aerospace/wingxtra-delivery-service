import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.delivery_event import DeliveryEventType


class DeliveryEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    job_id: uuid.UUID | None
    type: DeliveryEventType
    message: str
    payload: dict
    created_at: datetime


class DeliveryEventListResponse(BaseModel):
    items: list[DeliveryEventResponse]
