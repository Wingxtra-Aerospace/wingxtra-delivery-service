from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(ResponseModel):
    page: int
    page_size: int
    total: int


class OrderCreateRequest(BaseModel):
    customer_name: str | None = None


class OrderSummary(ResponseModel):
    id: str
    public_tracking_id: str
    merchant_id: str | None
    customer_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class OrdersListResponse(ResponseModel):
    items: list[OrderSummary]
    pagination: PaginationMeta


class OrderDetailResponse(OrderSummary):
    pass


class EventResponse(ResponseModel):
    id: str
    order_id: str
    type: str
    message: str
    created_at: datetime


class EventsTimelineResponse(ResponseModel):
    items: list[EventResponse]


class ManualAssignRequest(BaseModel):
    drone_id: str = Field(min_length=1)


class OrderActionResponse(ResponseModel):
    order_id: str
    status: str


class JobResponse(ResponseModel):
    id: str
    order_id: str
    assigned_drone_id: str
    status: str
    mission_intent_id: str | None
    created_at: datetime


class JobsListResponse(ResponseModel):
    items: list[JobResponse]


class TrackingViewResponse(ResponseModel):
    order_id: str
    public_tracking_id: str
    status: str


class MissionSubmitResponse(ResponseModel):
    order_id: str
    mission_intent_id: str
    status: str


class DispatchRunResponse(ResponseModel):
    assigned: int
