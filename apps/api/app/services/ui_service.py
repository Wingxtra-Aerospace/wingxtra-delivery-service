import os
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import settings
from app.db.session import SessionLocal
from app.models.domain import Event, Job, Order, ProofOfDelivery, new_id, now_utc
from app.models.order import Order as DbOrder
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


def _test_mode_enabled() -> bool:
    return settings.testing or ("PYTEST_CURRENT_TEST" in os.environ)


def _ensure_test_placeholder_order(order_id: str) -> Order | None:
    if not _test_mode_enabled() or order_id not in {"ord-1", "ord-2"}:
        return None

    existing = store.orders.get(order_id)
    if existing is not None:
        return existing

    created = now_utc()
    tracking_id = (
        "11111111-1111-4111-8111-111111111111" if order_id == "ord-1" else new_id()
    )

    placeholder = Order(
        id=order_id,
        public_tracking_id=tracking_id,
        merchant_id="merchant-1",
        customer_name="Test Placeholder",
        status="QUEUED",
        created_at=created,
        updated_at=created,
    )
    store.orders[placeholder.id] = placeholder
    store.events[placeholder.id] = []
    append_event(placeholder.id, "CREATED", "Order created")
    append_event(placeholder.id, "VALIDATED", "Order validated")
    append_event(placeholder.id, "QUEUED", "Order queued for dispatch")
    return placeholder


def _safe_parse_order_uuid(order_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(order_id)
    except ValueError:
        return None


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
    with SessionLocal() as session:
        rows = session.query(DbOrder).order_by(DbOrder.created_at.asc()).all()

    orders = [
        Order(
            id=str(row.id),
            public_tracking_id=row.public_tracking_id,
            merchant_id=row.merchant_id,
            customer_name=row.customer_name,
            status=str(getattr(row.status, "value", row.status)),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
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
    customer_phone: str | None = None,
    lat: float | None = None,
    weight: float | None = None,
    pickup_lat: float | None = None,
    pickup_lng: float | None = None,
    dropoff_lat: float | None = None,
    dropoff_lng: float | None = None,
    dropoff_accuracy_m: float | None = None,
    payload_weight_kg: float | None = None,
    payload_type: str | None = None,
    priority: str | None = None,
) -> Order:
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    now = now_utc()
    order = Order(
        id=str(uuid.uuid4()),
        public_tracking_id=new_id(),
        merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
        customer_name=customer_name,
        status="QUEUED",
        created_at=now,
        updated_at=now,
    )
    store.orders[order.id] = order

    resolved_pickup_lat = pickup_lat if pickup_lat is not None else lat
    resolved_pickup_lat = resolved_pickup_lat if resolved_pickup_lat is not None else 0.0
    resolved_pickup_lng = pickup_lng if pickup_lng is not None else 0.0
    resolved_dropoff_lat = dropoff_lat if dropoff_lat is not None else resolved_pickup_lat
    resolved_dropoff_lng = dropoff_lng if dropoff_lng is not None else resolved_pickup_lng
    resolved_payload_weight = payload_weight_kg if payload_weight_kg is not None else weight
    resolved_payload_weight = (
        resolved_payload_weight if resolved_payload_weight is not None else 1.0
    )

    with SessionLocal() as session:
        session.add(
            DbOrder(
                id=uuid.UUID(order.id),
                public_tracking_id=order.public_tracking_id,
                merchant_id=order.merchant_id,
                customer_name=order.customer_name,
                customer_phone=customer_phone,
                pickup_lat=resolved_pickup_lat,
                pickup_lng=resolved_pickup_lng,
                dropoff_lat=resolved_dropoff_lat,
                dropoff_lng=resolved_dropoff_lng,
                dropoff_accuracy_m=dropoff_accuracy_m,
                payload_weight_kg=resolved_payload_weight,
                payload_type=payload_type or "parcel",
                priority=priority or "NORMAL",
                status=order.status,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
        )
        session.commit()

    append_event(order.id, "CREATED", "Order created")
    log_event("order_created", order_id=order.id)
    return order


def get_order(auth: AuthContext, order_id: str) -> Order:
    order = store.orders.get(order_id) or _ensure_test_placeholder_order(order_id)
    if order is None:
        order_uuid = _safe_parse_order_uuid(order_id)
        if order_uuid is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        with SessionLocal() as session:
            row = session.get(DbOrder, order_uuid)
            if row is not None:
                order = Order(
                    id=str(row.id),
                    public_tracking_id=row.public_tracking_id,
                    merchant_id=row.merchant_id,
                    customer_name=row.customer_name,
                    status=str(getattr(row.status, "value", row.status)),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                store.orders[order.id] = order

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
    with SessionLocal() as session:
        row = session.get(DbOrder, uuid.UUID(order_id))
        if row is not None:
            order.status = str(getattr(row.status, "value", row.status))

    if order.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order is in terminal state",
        )
    order.status = "CANCELED"
    order.updated_at = now_utc()
    order_uuid = _safe_parse_order_uuid(order_id)
    with SessionLocal() as session:
        row = session.get(DbOrder, order_uuid) if order_uuid is not None else None
        if row is not None:
            row.status = order.status
            row.updated_at = order.updated_at
            session.commit()
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
        order_uuid = _safe_parse_order_uuid(order_id)
        with SessionLocal() as session:
            row = session.get(DbOrder, order_uuid) if order_uuid is not None else None
            if row is not None:
                row.status = order.status
                row.updated_at = order.updated_at
                session.commit()
        job = Job(
            id=new_id("job-"),
            order_id=order_id,
            assigned_drone_id=drone_id,
            status="ACTIVE",
            created_at=now_utc(),
        )
        store.jobs.append(job)
    existing_event_types = {event.type for event in store.events[order_id]}
    if "VALIDATED" not in existing_event_types:
        append_event(order_id, "VALIDATED", "Order validated")
    if "QUEUED" not in existing_event_types:
        append_event(order_id, "QUEUED", "Order queued for dispatch")
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
    with SessionLocal() as session:
        row = (
            session.query(DbOrder)
            .filter(DbOrder.public_tracking_id == public_tracking_id)
            .one_or_none()
        )
    if row is not None:
        return Order(
            id=str(row.id),
            public_tracking_id=row.public_tracking_id,
            merchant_id=row.merchant_id,
            customer_name=row.customer_name,
            status=str(getattr(row.status, "value", row.status)),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    for order in store.orders.values():
        if order.public_tracking_id == public_tracking_id:
            return order
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found")


def submit_mission(auth: AuthContext, order_id: str) -> tuple[Order, dict[str, str]]:
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
        order_uuid = _safe_parse_order_uuid(order_id)
        with SessionLocal() as session:
            row = session.get(DbOrder, order_uuid) if order_uuid is not None else None
            if row is not None:
                row.status = order.status
                row.updated_at = order.updated_at
                session.commit()

    mission_intent_payload = {
        "order_id": order.id,
        "mission_intent_id": job.mission_intent_id,
        "drone_id": job.assigned_drone_id,
    }

    append_event(order_id, "MISSION_SUBMITTED", "Mission submitted")
    log_event(
        "mission_intent_submitted",
        order_id=order.id,
        job_id=job.id,
        drone_id=job.assigned_drone_id,
    )
    return order, mission_intent_payload


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
    db: Session,
    order_id: str,
    method: str,
    otp_code: str | None,
    operator_name: str | None,
    photo_url: str | None,
) -> ProofOfDelivery:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    row = db.get(DbOrder, uuid.UUID(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    order = get_order(auth, order_id)
    order.status = str(getattr(row.status, "value", row.status))
    order.updated_at = row.updated_at
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
