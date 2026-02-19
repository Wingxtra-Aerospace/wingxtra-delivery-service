from app.models.order import OrderStatus
from app.schemas.order import OrderCreate
from app.services.orders_service import cancel_order, create_order, list_orders


def test_create_order_generates_tracking_id(db_session):
    order = create_order(
        db_session,
        OrderCreate(
            pickup_lat=1,
            pickup_lng=2,
            dropoff_lat=3,
            dropoff_lng=4,
            payload_weight_kg=1.5,
            payload_type="MEDICAL_BOX",
        ),
    )

    assert len(order.public_tracking_id) == 10
    assert order.status == OrderStatus.CREATED


def test_cancel_order_marks_canceled(db_session):
    order = create_order(
        db_session,
        OrderCreate(
            pickup_lat=1,
            pickup_lng=2,
            dropoff_lat=3,
            dropoff_lng=4,
            payload_weight_kg=1.5,
            payload_type="MEDICAL_BOX",
        ),
    )

    canceled = cancel_order(db_session, order.id)

    assert canceled.status == OrderStatus.CANCELED


def test_list_orders_filters_status(db_session):
    created = create_order(
        db_session,
        OrderCreate(
            pickup_lat=1,
            pickup_lng=2,
            dropoff_lat=3,
            dropoff_lng=4,
            payload_weight_kg=1.5,
            payload_type="A",
        ),
    )
    canceled = cancel_order(db_session, created.id)

    canceled_orders = list_orders(db_session, OrderStatus.CANCELED)
    assert len(canceled_orders) == 1
    assert canceled_orders[0].id == canceled.id
