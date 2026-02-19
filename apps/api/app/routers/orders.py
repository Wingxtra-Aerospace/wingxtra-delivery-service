from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import AuthContext, require_roles
from app.schemas.ui import (
    EventResponse,
    EventsTimelineResponse,
    ManualAssignRequest,
    OrderActionResponse,
    OrderCreateRequest,
    OrderDetailResponse,
    OrdersListResponse,
    PaginationMeta,
)
from app.services.ui_service import (
    cancel_order,
    create_order,
    get_order,
    list_events,
    list_orders,
    manual_assign,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("", response_model=OrderDetailResponse, summary="Create order")
def create_order_endpoint(
    payload: OrderCreateRequest,
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrderDetailResponse:
    return OrderDetailResponse.model_validate(create_order(auth, payload.customer_name))


@router.get("", response_model=OrdersListResponse, summary="List orders for Ops UI")
def list_orders_endpoint(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrdersListResponse:
    items, total = list_orders(
        auth=auth,
        page=page,
        page_size=page_size,
        status_filter=status,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )
    return OrdersListResponse(
        items=[OrderDetailResponse.model_validate(order) for order in items],
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/{order_id}", response_model=OrderDetailResponse, summary="Get order detail")
def get_order_endpoint(
    order_id: str,
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> OrderDetailResponse:
    return OrderDetailResponse.model_validate(get_order(auth, order_id))


@router.get(
    "/{order_id}/events",
    response_model=EventsTimelineResponse,
    summary="Get order timeline",
)
def get_events_endpoint(
    order_id: str,
    auth: AuthContext = Depends(require_roles("MERCHANT", "OPS", "ADMIN")),
) -> EventsTimelineResponse:
    events = [EventResponse.model_validate(event) for event in list_events(auth, order_id)]
    return EventsTimelineResponse(items=events)


@router.post("/{order_id}/assign", response_model=OrderActionResponse, summary="Manual assignment")
def assign_endpoint(
    order_id: str,
    payload: ManualAssignRequest,
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> OrderActionResponse:
    order = manual_assign(auth, order_id, payload.drone_id)
    return OrderActionResponse(order_id=order.id, status=order.status)


@router.post("/{order_id}/cancel", response_model=OrderActionResponse, summary="Cancel order")
def cancel_endpoint(
    order_id: str,
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> OrderActionResponse:
    order = cancel_order(auth, order_id)
    return OrderActionResponse(order_id=order.id, status=order.status)
