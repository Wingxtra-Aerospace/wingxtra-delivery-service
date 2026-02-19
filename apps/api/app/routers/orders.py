import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.fleet_api_client import FleetApiClientProtocol, get_fleet_api_client
from app.models.order import OrderStatus
from app.schemas.dispatch import ManualAssignRequest, ManualAssignResponse
from app.schemas.events import DeliveryEventListResponse, DeliveryEventResponse
from app.schemas.order import OrderCancelResponse, OrderCreate, OrderListResponse, OrderResponse
from app.services.dispatch_service import manual_assign_order
from app.services.orders_service import (
    cancel_order,
    create_order,
    get_order,
    list_order_events,
    list_orders,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order_endpoint(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderResponse:
    order = create_order(db, payload)
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_endpoint(order_id: uuid.UUID, db: Session = Depends(get_db)) -> OrderResponse:
    order = get_order(db, order_id)
    return OrderResponse.model_validate(order)


@router.get("", response_model=OrderListResponse)
def list_orders_endpoint(
    status: OrderStatus | None = Query(default=None), db: Session = Depends(get_db)
) -> OrderListResponse:
    items = [OrderResponse.model_validate(order) for order in list_orders(db, status)]
    return OrderListResponse(items=items)


@router.post("/{order_id}/cancel", response_model=OrderCancelResponse)
def cancel_order_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderCancelResponse:
    order = cancel_order(db, order_id)
    return OrderCancelResponse(id=order.id, status=order.status)


@router.post("/{order_id}/assign", response_model=ManualAssignResponse)
def manual_assign_order_endpoint(
    order_id: uuid.UUID,
    payload: ManualAssignRequest,
    db: Session = Depends(get_db),
    fleet_client: FleetApiClientProtocol = Depends(get_fleet_api_client),
) -> ManualAssignResponse:
    job = manual_assign_order(db, fleet_client, order_id, payload.drone_id)
    return ManualAssignResponse(
        order_id=job.order_id,
        assigned_drone_id=job.assigned_drone_id or "",
    )


@router.get("/{order_id}/events", response_model=DeliveryEventListResponse)
def list_order_events_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DeliveryEventListResponse:
    events = [
        DeliveryEventResponse.model_validate(event)
        for event in list_order_events(db, order_id)
    ]
    return DeliveryEventListResponse(items=events)
