from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

OrderStatus = Literal[
    "CREATED",
    "VALIDATED",
    "QUEUED",
    "ASSIGNED",
    "MISSION_SUBMITTED",
    "LAUNCHED",
    "ENROUTE",
    "ARRIVED",
    "DELIVERING",
    "DELIVERED",
    "CANCELED",
    "FAILED",
    "ABORTED",
]


class Order(BaseModel):
    id: str
    public_tracking_id: str
    merchant_id: str | None
    customer_name: str | None
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class Job(BaseModel):
    id: str
    order_id: str
    assigned_drone_id: str
    status: str
    mission_intent_id: str | None = None
    created_at: datetime


class Event(BaseModel):
    id: str
    order_id: str
    type: str
    message: str
    created_at: datetime


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid4()}"


class ProofOfDelivery(BaseModel):
    order_id: str
    method: str
    otp_code: str | None = None
    operator_name: str | None = None
    photo_url: str | None = None
    created_at: datetime
