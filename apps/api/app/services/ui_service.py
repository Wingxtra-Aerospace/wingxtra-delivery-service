from datetime import datetime

from fastapi import HTTPException, status

from app.models.domain import Event, Job, Order, new_id, now_utc
from app.services.store import store

TERMINAL = {"CANCELED", "FAILED", "ABORTED", "DELIVERED"}
ACTIVE_JOB_STATUSES = {
    "ACTIVE",
    "LAUNCHED",
    "ENROUTE",
    "ARRIVED",
    "DELIVERING",
    "MISSION_SUBMITTED",
}


def list_orders(
    *,
    page: int,
    page_size: int,
    status_filter: str | None,
    search: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[list[Order], int]:
    orders = list(store.orders.values())
    if status_filter:
        orders = [order for order in orders if order.status == status_filter]
    if search:
        needle = search.lower()
        orders = [
            order
            for order in orders
            if needle in order.id.lower()
            or needle in order.public_tracking_id.lower()
            or needle in (order.customer_name or "").lower()
        ]
    if from_date:
        orders = [order for order in orders if order.created_at >= from_date]
    if to_date:
        orders = [order for order in orders if order.created_at <= to_date]

    total = len(orders)
    start = (page - 1) * page_size
    end = start + page_size
    return orders[start:end], total


def get_order(order_id: str) -> Order:
    order = store.orders.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def append_event(order_id: str, event_type: str, message: str) -> None:
    store.events[order_id].append(
        Event(
            id=new_id("evt-"),
            order_id=order_id,
            type=event_type,
            message=message,
            created_at=now_utc(),
        )
    )


def cancel_order(order_id: str) -> Order:
    order = get_order(order_id)
    if order.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order is in terminal state",
        )
    order.status = "CANCELED"
    order.updated_at = now_utc()
    append_event(order_id, "CANCELED", "Order canceled by operator")
    return order


def manual_assign(order_id: str, drone_id: str) -> Order:
    order = get_order(order_id)
    if order.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )
    order.status = "ASSIGNED"
    order.updated_at = now_utc()
    store.jobs.append(
        Job(
            id=new_id("job-"),
            order_id=order_id,
            assigned_drone_id=drone_id,
            status="ACTIVE",
            created_at=now_utc(),
        )
    )
    append_event(order_id, "ASSIGNED", f"Order assigned to {drone_id}")
    return order


def list_jobs(active_only: bool) -> list[Job]:
    if not active_only:
        return list(store.jobs)
    return [job for job in store.jobs if job.status in ACTIVE_JOB_STATUSES]


def list_events(order_id: str) -> list[Event]:
    get_order(order_id)
    return store.events[order_id]


def tracking_view(public_tracking_id: str) -> Order:
    for order in store.orders.values():
        if order.public_tracking_id == public_tracking_id:
            return order
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found")
