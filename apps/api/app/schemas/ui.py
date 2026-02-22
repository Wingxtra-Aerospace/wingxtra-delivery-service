from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationMeta(ResponseModel):
    page: int
    page_size: int
    total: int


T = TypeVar("T")


class Page(ResponseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int

    @computed_field(return_type=PaginationMeta)
    @property
    def pagination(self) -> PaginationMeta:
        """Backward-compatible shim for clients still reading nested pagination."""
        return PaginationMeta(page=self.page, page_size=self.page_size, total=self.total)


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


class OrdersListResponse(Page[OrderSummary]):
    pass


class OrderDetailResponse(OrderSummary):
    pass


class EventResponse(ResponseModel):
    id: str
    order_id: str
    type: str
    message: str
    created_at: datetime


class EventsTimelineResponse(Page[EventResponse]):
    pass


class OrderEventIngestRequest(BaseModel):
    event_type: Literal["MISSION_LAUNCHED", "ENROUTE", "ARRIVED", "DELIVERED", "FAILED"] = Field(
        validation_alias=AliasChoices("event_type", "event", "type")
    )
    occurred_at: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("occurred_at", "timestamp"),
    )


class OrderEventIngestResponse(ResponseModel):
    order_id: str
    status: str
    applied_events: list[str]


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
    eta_seconds: int | None = None
    created_at: datetime


class JobsListResponse(Page[JobResponse]):
    pass


class TrackingPodSummary(ResponseModel):
    method: str
    created_at: datetime


class TrackingViewResponse(ResponseModel):
    order_id: str
    public_tracking_id: str
    status: str
    milestones: list[str] | None = None
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
    method: Literal["PHOTO", "OTP", "OPERATOR_CONFIRM"]
    otp_code: str | None = Field(default=None, min_length=4, max_length=32)
    operator_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("operator_name", "confirmed_by"),
    )
    photo_url: str | None = Field(default=None, min_length=1, max_length=1024)


class PodResponse(ResponseModel):
    order_id: str
    method: str | None = None
    otp_code: str | None = None
    operator_name: str | None = None
    photo_url: str | None = None
