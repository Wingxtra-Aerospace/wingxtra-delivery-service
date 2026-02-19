import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.order import OrderStatus
from app.schemas.order import OrderCancelResponse, OrderCreate, OrderListResponse, OrderResponse
from app.services.orders_service import cancel_order, create_order, get_order, list_orders

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
    order_id: uuid.UUID, db: Session = Depends(get_db)
) -> OrderCancelResponse:
    order = cancel_order(db, order_id)
    return OrderCancelResponse(id=order.id, status=order.status)
