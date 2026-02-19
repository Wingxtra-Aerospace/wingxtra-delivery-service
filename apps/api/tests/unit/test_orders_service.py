import pytest
from fastapi import HTTPException

from app.models.order import OrderStatus
from app.schemas.order import OrderCreate
from app.services.orders_service import (
    cancel_order,
    create_order,
    list_order_events,
    list_orders,
    transition_order_status,
)


def _payload() -> OrderCreate:
    return OrderCreate(
        pickup_lat=1,
        pickup_lng=2,
        dropoff_lat=3,
        dropoff_lng=4,
        payload_weight_kg=1.5,
        payload_type="MEDICAL_BOX",
    )


def test_create_order_generates_tracking_id_and_created_event(db_session):
    order = create_order(db_session, _payload())

    assert len(order.public_tracking_id) == 10
    assert order.status == OrderStatus.CREATED

    events = list_order_events(db_session, order.id)
    assert len(events) == 1
    assert events[0].type.value == "CREATED"


def test_cancel_order_marks_canceled_and_appends_event(db_session):
    order = create_order(db_session, _payload())

    canceled = cancel_order(db_session, order.id)

    assert canceled.status == OrderStatus.CANCELED
    events = list_order_events(db_session, order.id)
    assert [event.type.value for event in events] == ["CREATED", "CANCELED"]


def test_list_orders_filters_status(db_session):
    created = create_order(db_session, _payload())
    canceled = cancel_order(db_session, created.id)

    canceled_orders = list_orders(db_session, OrderStatus.CANCELED)
    assert len(canceled_orders) == 1
    assert canceled_orders[0].id == canceled.id


def test_invalid_state_transition_is_rejected(db_session):
    order = create_order(db_session, _payload())

    with pytest.raises(HTTPException) as exc:
        transition_order_status(
            db_session,
            order,
            OrderStatus.DELIVERED,
            "Skipped state machine",
        )

    assert exc.value.status_code == 409
