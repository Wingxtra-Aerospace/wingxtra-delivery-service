from fastapi import HTTPException, status

from app.models.delivery_event import DeliveryEventType
from app.models.order import OrderStatus

ORDER_STATE_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.VALIDATED, OrderStatus.CANCELED},
    OrderStatus.VALIDATED: {OrderStatus.QUEUED, OrderStatus.CANCELED},
    OrderStatus.QUEUED: {OrderStatus.ASSIGNED, OrderStatus.CANCELED},
    OrderStatus.ASSIGNED: {OrderStatus.MISSION_SUBMITTED, OrderStatus.CANCELED},
    OrderStatus.MISSION_SUBMITTED: {OrderStatus.LAUNCHED, OrderStatus.FAILED, OrderStatus.ABORTED},
    OrderStatus.LAUNCHED: {OrderStatus.ENROUTE, OrderStatus.FAILED, OrderStatus.ABORTED},
    OrderStatus.ENROUTE: {OrderStatus.ARRIVED, OrderStatus.FAILED, OrderStatus.ABORTED},
    OrderStatus.ARRIVED: {OrderStatus.DELIVERING, OrderStatus.FAILED, OrderStatus.ABORTED},
    OrderStatus.DELIVERING: {OrderStatus.DELIVERED, OrderStatus.FAILED, OrderStatus.ABORTED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELED: set(),
    OrderStatus.FAILED: set(),
    OrderStatus.ABORTED: set(),
}


def ensure_valid_transition(current: OrderStatus, next_status: OrderStatus) -> None:
    if next_status == current:
        return

    allowed = ORDER_STATE_TRANSITIONS.get(current, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {current.value} -> {next_status.value}",
        )


def event_type_for_status(status_value: OrderStatus) -> DeliveryEventType:
    return DeliveryEventType[status_value.value]
