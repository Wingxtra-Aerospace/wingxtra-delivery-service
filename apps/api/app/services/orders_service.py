import secrets
import string
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.delivery_event import DeliveryEvent
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate
from app.services.state_machine import ensure_valid_transition, event_type_for_status

_TRACKING_ALPHABET = string.ascii_uppercase + string.digits


def _generate_tracking_id(length: int = 10) -> str:
    return "".join(secrets.choice(_TRACKING_ALPHABET) for _ in range(length))


def _generate_unique_tracking_id(db: Session) -> str:
    while True:
        tracking_id = _generate_tracking_id()
        exists = db.scalar(select(Order.id).where(Order.public_tracking_id == tracking_id))
        if not exists:
            return tracking_id


def _append_state_event(
    db: Session,
    order_id: uuid.UUID,
    state: OrderStatus,
    message: str,
    payload: dict | None = None,
) -> None:
    db.add(
        DeliveryEvent(
            order_id=order_id,
            type=event_type_for_status(state),
            message=message,
            payload=payload or {},
        )
    )


def transition_order_status(
    db: Session,
    order: Order,
    next_status: OrderStatus,
    message: str,
    payload: dict | None = None,
) -> Order:
    previous_status = order.status
    ensure_valid_transition(previous_status, next_status)

    if previous_status == next_status:
        return order

    order.status = next_status
    _append_state_event(
        db,
        order.id,
        next_status,
        message,
        {
            "from_status": previous_status.value,
            "to_status": next_status.value,
            **(payload or {}),
        },
    )
    return order


def create_order(db: Session, payload: OrderCreate) -> Order:
    order = Order(
        public_tracking_id=_generate_unique_tracking_id(db),
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lng=payload.dropoff_lng,
        dropoff_accuracy_m=payload.dropoff_accuracy_m,
        payload_weight_kg=payload.payload_weight_kg,
        payload_type=payload.payload_type,
        priority=payload.priority,
        status=OrderStatus.CREATED,
    )
    db.add(order)
    db.flush()

    _append_state_event(db, order.id, OrderStatus.CREATED, "Order created")

    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def list_orders(db: Session, status_filter: OrderStatus | None) -> list[Order]:
    query = select(Order)
    if status_filter:
        query = query.where(Order.status == status_filter)
    return list(db.scalars(query.order_by(Order.created_at.desc())))


def list_order_events(db: Session, order_id: uuid.UUID) -> list[DeliveryEvent]:
    get_order(db, order_id)
    events = db.scalars(
        select(DeliveryEvent)
        .where(DeliveryEvent.order_id == order_id)
        .order_by(DeliveryEvent.created_at.asc())
    )
    return list(events)


def cancel_order(db: Session, order_id: uuid.UUID) -> Order:
    order = get_order(db, order_id)
    if order.status == OrderStatus.CANCELED:
        return order

    transition_order_status(db, order, OrderStatus.CANCELED, "Order canceled")
    db.commit()
    db.refresh(order)
    return order


def get_order_by_tracking_id(db: Session, public_tracking_id: str) -> Order:
    order = db.scalar(select(Order).where(Order.public_tracking_id == public_tracking_id))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking ID not found")
    return order
