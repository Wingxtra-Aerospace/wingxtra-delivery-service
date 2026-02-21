import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MissionAction = Literal["TAKEOFF", "CRUISE", "DESCEND", "DROP_OR_WINCH", "ASCEND", "RTL"]


class MissionLocation(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    alt_m: float = Field(ge=0)


class MissionDropoffLocation(MissionLocation):
    delivery_alt_m: float = Field(ge=0)


class MissionConstraints(BaseModel):
    battery_min_pct: float = Field(ge=0, le=100)
    service_area_id: str = Field(min_length=1)


class MissionSafety(BaseModel):
    abort_rtl_on_fail: bool
    loiter_timeout_s: int = Field(ge=0)
    lost_link_behavior: str = Field(min_length=1)


class MissionMetadata(BaseModel):
    payload_type: str = Field(min_length=1)
    payload_weight_kg: float = Field(ge=0)
    priority: str = Field(min_length=1)
    created_at: datetime


class MissionIntent(BaseModel):
    intent_id: str = Field(min_length=1)
    order_id: uuid.UUID
    drone_id: str = Field(min_length=1)
    pickup: MissionLocation
    dropoff: MissionDropoffLocation
    actions: list[MissionAction] = Field(min_length=1)
    constraints: MissionConstraints
    safety: MissionSafety
    metadata: MissionMetadata


class MissionIntentSubmitResponse(BaseModel):
    order_id: uuid.UUID
    mission_intent_id: str
    status: str
