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
    customer_phone: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    weight: float | None = Field(default=None, gt=0)
    pickup_lat: float | None = Field(default=None, ge=-90, le=90)
    pickup_lng: float | None = Field(default=None, ge=-180, le=180)
    dropoff_lat: float | None = Field(default=None, ge=-90, le=90)
    dropoff_lng: float | None = Field(default=None, ge=-180, le=180)
    dropoff_accuracy_m: float | None = Field(default=None, ge=0)
    payload_weight_kg: float | None = Field(default=None, gt=0)
    payload_type: str | None = Field(default=None, min_length=1)
    priority: str | None = None


class OrderUpdateRequest(BaseModel):
    customer_phone: str | None = None
    dropoff_lat: float | None = Field(default=None, ge=-90, le=90)
    dropoff_lng: float | None = Field(default=None, ge=-180, le=180)
    priority: str | None = None


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


class TrackingPodSummary(ResponseModel):
    method: str
    photo_url: str | None = None
    created_at: datetime


class TrackingViewResponse(ResponseModel):
    order_id: str
    public_tracking_id: str
    status: str
    pod_summary: TrackingPodSummary | None = None


class MissionSubmitResponse(ResponseModel):
    order_id: str
    mission_intent_id: str
    status: str




class DispatchRunRequest(BaseModel):
    max_assignments: int | None = Field(default=None, ge=1, le=100)


class DispatchRunResponse(ResponseModel):
    assigned: int
    assignments: list[OrderActionResponse]


class PodCreateRequest(BaseModel):
    method: str
    otp_code: str | None = None
    operator_name: str | None = None
    photo_url: str | None = None


class PodResponse(ResponseModel):
    order_id: str
    method: str | None = None
    otp_code: str | None = None
    operator_name: str | None = None
    photo_url: str | None = None
