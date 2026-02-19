from datetime import datetime

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int


class OrderCreateRequest(BaseModel):
    customer_name: str | None = None


class OrderSummary(BaseModel):
    id: str
    public_tracking_id: str
    merchant_id: str | None
    customer_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class OrdersListResponse(BaseModel):
    items: list[OrderSummary]
    pagination: PaginationMeta


class OrderDetailResponse(OrderSummary):
    pass


class EventResponse(BaseModel):
    id: str
    order_id: str
    type: str
    message: str
    created_at: datetime


class EventsTimelineResponse(BaseModel):
    items: list[EventResponse]


class ManualAssignRequest(BaseModel):
    drone_id: str = Field(min_length=1)


class OrderActionResponse(BaseModel):
    order_id: str
    status: str


class JobResponse(BaseModel):
    id: str
    order_id: str
    assigned_drone_id: str
    status: str
    mission_intent_id: str | None
    created_at: datetime


class JobsListResponse(BaseModel):
    items: list[JobResponse]


class TrackingViewResponse(BaseModel):
    order_id: str
    public_tracking_id: str
    status: str


class MissionSubmitResponse(BaseModel):
    order_id: str
    mission_intent_id: str
    status: str
