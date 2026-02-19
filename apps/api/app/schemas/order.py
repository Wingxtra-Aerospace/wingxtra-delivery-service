import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import OrderPriority, OrderStatus


class OrderCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=50)

    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lng: float = Field(ge=-180, le=180)
    dropoff_lat: float = Field(ge=-90, le=90)
    dropoff_lng: float = Field(ge=-180, le=180)
    dropoff_accuracy_m: float | None = Field(default=None, ge=0)

    payload_weight_kg: float = Field(gt=0)
    payload_type: str = Field(min_length=1, max_length=100)
    priority: OrderPriority = OrderPriority.NORMAL

    @field_validator("customer_name", "customer_phone", "payload_type")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    public_tracking_id: str
    customer_name: str | None
    customer_phone: str | None
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    dropoff_accuracy_m: float | None
    payload_weight_kg: float
    payload_type: str
    priority: OrderPriority
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderResponse]


class OrderCancelResponse(BaseModel):
    id: uuid.UUID
    status: OrderStatus
