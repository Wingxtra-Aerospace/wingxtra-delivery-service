from datetime import datetime

from fastapi import HTTPException, status

from app.auth.dependencies import AuthContext
from app.models.domain import Event, Job, Order, ProofOfDelivery, new_id, now_utc
from app.observability import log_event, observe_timing
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


def _is_backoffice(role: str) -> bool:
    return role in {"OPS", "ADMIN"}


def _assert_can_access_order(auth: AuthContext, order: Order) -> None:
    if _is_backoffice(auth.role):
        return
    if auth.role == "MERCHANT" and order.merchant_id == auth.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied for this order",
    )


def list_orders(
    *,
    auth: AuthContext,
    page: int,
    page_size: int,
    status_filter: str | None,
    search: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[list[Order], int]:
    orders = list(store.orders.values())
    if auth.role == "MERCHANT":
        orders = [order for order in orders if order.merchant_id == auth.user_id]

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


def create_order(
    auth: AuthContext,
    customer_name: str | None,
    lat: float | None = None,
    weight: float | None = None,
    payload_type: str | None = None,
) -> Order:
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    now = now_utc()
    order = Order(
        id=new_id(),
        public_tracking_id=new_id(),
        merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
        customer_name=customer_name,
        status="QUEUED",
        created_at=now,
        updated_at=now,
    )
    store.orders[order.id] = order
    append_event(order.id, "CREATED", "Order created")
    append_event(order.id, "VALIDATED", "Order validated")
    append_event(order.id, "QUEUED", "Order queued for dispatch")
    log_event("order_created", order_id=order.id)
    return order


def get_order(auth: AuthContext, order_id: str) -> Order:
    order = store.orders.get(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _assert_can_access_order(auth, order)
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


def cancel_order(auth: AuthContext, order_id: str) -> Order:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    order = get_order(auth, order_id)
    if order.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order is in terminal state",
        )
    order.status = "CANCELED"
    order.updated_at = now_utc()
    append_event(order_id, "CANCELED", "Order canceled by operator")
    log_event("order_canceled", order_id=order.id)
    return order




def _is_valid_drone_id(drone_id: str) -> bool:
    import re

    return bool(re.match(r"^(DR|DRONE)-[0-9]+$", drone_id))


def _assert_drone_assignable(drone_id: str) -> None:
    drone = store.drones.get(drone_id)
    if drone is None:
        return
    if not bool(drone.get("available", False)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone unavailable")
    if int(drone.get("battery", 0)) <= 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone battery too low")


def manual_assign(auth: AuthContext, order_id: str, drone_id: str) -> Order:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    if not _is_valid_drone_id(drone_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")
    _assert_drone_assignable(drone_id)
    order = get_order(auth, order_id)
    if order.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )
    with observe_timing("dispatch_assignment_seconds"):
        order.status = "ASSIGNED"
        order.updated_at = now_utc()
        job = Job(
            id=new_id("job-"),
            order_id=order_id,
            assigned_drone_id=drone_id,
            status="ACTIVE",
            created_at=now_utc(),
        )
        store.jobs.append(job)
    append_event(order_id, "ASSIGNED", f"Order assigned to {drone_id}")
    log_event("order_assigned", order_id=order.id, job_id=job.id, drone_id=drone_id)
    return order


def list_jobs(auth: AuthContext, active_only: bool) -> list[Job]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    if not active_only:
        return list(store.jobs)
    return [job for job in store.jobs if job.status in ACTIVE_JOB_STATUSES]


def list_events(auth: AuthContext, order_id: str) -> list[Event]:
    get_order(auth, order_id)
    return store.events[order_id]


def tracking_view(public_tracking_id: str) -> Order:
    for order in store.orders.values():
        if order.public_tracking_id == public_tracking_id:
            return order
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found")


def submit_mission(auth: AuthContext, order_id: str, publisher) -> Order:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    order = get_order(auth, order_id)
    if order.status not in {"ASSIGNED", "MISSION_SUBMITTED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order must be ASSIGNED before mission submission",
        )

    active_jobs = [job for job in store.jobs if job.order_id == order_id]
    if not active_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No delivery job for order",
        )

    job = active_jobs[-1]
    with observe_timing("mission_intent_generation_seconds"):
        if not job.mission_intent_id:
            job.mission_intent_id = new_id("mi_")

        order.status = "MISSION_SUBMITTED"
        order.updated_at = now_utc()

    if publisher is not None:
        publisher.publish_mission_intent(
            {
                "order_id": order.id,
                "mission_intent_id": job.mission_intent_id,
                "drone_id": job.assigned_drone_id,
            }
        )

    append_event(order_id, "MISSION_SUBMITTED", "Mission submitted")
    log_event(
        "mission_intent_submitted",
        order_id=order.id,
        job_id=job.id,
        drone_id=job.assigned_drone_id,
    )
    return order


def run_auto_dispatch(auth: AuthContext) -> dict[str, int | list[dict[str, str]]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    assignments: list[dict[str, str]] = []
    candidates = [
        order
        for order in store.orders.values()
        if order.status in {"CREATED", "VALIDATED", "QUEUED"}
    ]
    candidates.sort(key=lambda x: x.created_at)

    available_drones = [
        drone_id
        for drone_id, info in store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]

    for order, drone_id in zip(candidates, available_drones, strict=False):
        assigned_order = manual_assign(auth, order.id, drone_id)
        assignments.append({"order_id": assigned_order.id, "status": assigned_order.status})

    return {"assigned": len(assignments), "assignments": assignments}


def create_pod(
    auth: AuthContext,
    order_id: str,
    method: str,
    otp_code: str | None,
    operator_name: str | None,
    photo_url: str | None,
) -> ProofOfDelivery:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    order = get_order(auth, order_id)
    if order.status != "DELIVERED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="POD requires DELIVERED order",
        )

    pod = ProofOfDelivery(
        order_id=order_id,
        method=method,
        otp_code=otp_code,
        operator_name=operator_name,
        photo_url=photo_url,
        created_at=now_utc(),
    )
    store.pods[order_id] = pod
    return pod


def get_pod(order_id: str) -> ProofOfDelivery | None:
    return store.pods.get(order_id)
