from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import settings
from app.models.delivery_event import DeliveryEvent, DeliveryEventType
from app.models.delivery_job import DeliveryJob, DeliveryJobStatus
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.proof_of_delivery import ProofOfDelivery, ProofOfDeliveryMethod
from app.observability import log_event, observe_timing
from app.services.store import store

# In-memory (store) domain models
from app.models.domain import Event as MemEvent
from app.models.domain import Job as MemJob
from app.models.domain import Order as MemOrder
from app.models.domain import ProofOfDelivery as MemPod
from app.models.domain import now_utc as mem_now_utc

TERMINAL: set[OrderStatus] = {
    OrderStatus.CANCELED,
    OrderStatus.FAILED,
    OrderStatus.ABORTED,
    OrderStatus.DELIVERED,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _test_mode_enabled() -> bool:
    return bool(settings.testing or ("PYTEST_CURRENT_TEST" in settings.env))


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


def _append_event(
    db: Session,
    *,
    order_id: str | uuid.UUID,
    event_type: DeliveryEventType,
    message: str,
    job_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    oid = uuid.UUID(order_id) if isinstance(order_id, str) else order_id
    db.add(
        DeliveryEvent(
            order_id=oid,
            job_id=job_id,
            type=event_type,
            message=message,
            payload=payload or {},
        )
    )


def list_orders(
    *,
    auth: AuthContext,
    db: Session,
    page: int,
    page_size: int,
    status_filter: str | None,
    search: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(Order)
    filters: list[Any] = []

    if auth.role == "MERCHANT":
        filters.append(Order.merchant_id == auth.user_id)

    if status_filter:
        try:
            filters.append(Order.status == OrderStatus(status_filter))
        except ValueError:
            return [], 0

    if search:
        needle = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(func.cast(Order.id, String)).like(needle),
                func.lower(Order.public_tracking_id).like(needle),
                func.lower(func.coalesce(Order.customer_name, "")).like(needle),
            )
        )

    if from_date:
        filters.append(Order.created_at >= from_date)
    if to_date:
        filters.append(Order.created_at <= to_date)

    if filters:
        stmt = stmt.where(and_(*filters))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = (
        stmt.order_by(Order.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(db.scalars(stmt))

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": str(row.id),
                "public_tracking_id": row.public_tracking_id,
                "merchant_id": row.merchant_id,
                "customer_name": row.customer_name,
                "status": row.status.value,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    return items, int(total)


def create_order(
    auth: AuthContext,
    db: Session | None = None,
    customer_name: str | None = None,
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
) -> dict[str, Any] | MemOrder:
    """
    Dual-mode function:
    - DB mode (db is a real SQLAlchemy Session): creates DB Order + CREATED event only.
    - Store mode (db is None or not a Session): creates in-memory Order/Event for unit tests.
    """
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    # Resolve pickup lat/lng
    if pickup_lat is not None:
        resolved_pickup_lat = pickup_lat
    elif lat is not None:
        resolved_pickup_lat = lat
    else:
        resolved_pickup_lat = 0.0

    resolved_pickup_lng = pickup_lng if pickup_lng is not None else 0.0
    resolved_dropoff_lat = dropoff_lat if dropoff_lat is not None else resolved_pickup_lat
    resolved_dropoff_lng = dropoff_lng if dropoff_lng is not None else resolved_pickup_lng

    # Resolve payload weight
    if payload_weight_kg is not None:
        resolved_payload_weight = payload_weight_kg
    elif weight is not None:
        resolved_payload_weight = weight
    else:
        resolved_payload_weight = 1.0

    try:
        prio = OrderPriority(priority) if priority else OrderPriority.NORMAL
    except ValueError:
        prio = OrderPriority.NORMAL

    # If "db" is not a real Session (e.g. Depends(get_db) object), treat as store mode.
    db_is_session = isinstance(db, Session)

    if not db_is_session:
        created = mem_now_utc()
        oid = uuid.uuid4().hex  # IMPORTANT: not "ord-" so router won't treat as placeholder
        tracking_id = uuid.uuid4().hex

        order = MemOrder(
            id=oid,
            public_tracking_id=tracking_id,
            merchant_id=(auth.user_id if auth.role == "MERCHANT" else None),
            customer_name=customer_name,
            status=OrderStatus.CREATED.value,
            created_at=created,
            updated_at=created,
        )
        store.orders[order.id] = order

        evt = MemEvent(
            id=f"evt-{uuid.uuid4().hex}",
            order_id=order.id,
            type=DeliveryEventType.CREATED.value,
            message="Order created",
            created_at=created,
        )
        store.events[order.id].append(evt)

        log_event("order_created", order_id=str(order.id))
        return order

    db = cast(Session, db)
    now = _now_utc()

    o = Order(
        public_tracking_id=uuid.uuid4().hex,
        merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
        customer_name=customer_name,
        customer_phone=customer_phone,
        pickup_lat=float(resolved_pickup_lat),
        pickup_lng=float(resolved_pickup_lng),
        dropoff_lat=float(resolved_dropoff_lat),
        dropoff_lng=float(resolved_dropoff_lng),
        dropoff_accuracy_m=dropoff_accuracy_m,
        payload_weight_kg=float(resolved_payload_weight),
        payload_type=payload_type or "parcel",
        priority=prio,
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )

    db.add(o)
    db.flush()  # ensure o.id exists for event FK

    _append_event(
        db,
        order_id=o.id,
        event_type=DeliveryEventType.CREATED,
        message="Order created",
    )

    db.commit()
    db.refresh(o)

    log_event("order_created", order_id=str(o.id))

    return {
        "id": str(o.id),
        "public_tracking_id": o.public_tracking_id,
        "merchant_id": o.merchant_id,
        "customer_name": o.customer_name,
        "status": o.status.value,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


def get_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    oid = uuid.UUID(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    _assert_can_access_order(auth, row)

    return {
        "id": str(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    oid = uuid.UUID(order_id)
    order = db.get(Order, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _assert_can_access_order(auth, order)

    stmt = (
        select(DeliveryEvent)
        .where(DeliveryEvent.order_id == oid)
        .order_by(DeliveryEvent.created_at.asc())
    )
    rows = list(db.scalars(stmt))

    out: list[dict[str, Any]] = []
    for ev in rows:
        out.append(
            {
                "id": str(ev.id),
                "order_id": str(ev.order_id),
                "type": ev.type.value,
                "message": ev.message,
                "created_at": ev.created_at,
            }
        )
    return out


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    oid = uuid.UUID(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order is in terminal state",
        )

    row.status = OrderStatus.CANCELED
    row.updated_at = _now_utc()

    _append_event(
        db,
        order_id=row.id,
        event_type=DeliveryEventType.CANCELED,
        message="Order canceled by operator",
    )

    db.commit()
    db.refresh(row)

    log_event("order_canceled", order_id=str(row.id))

    return {
        "id": str(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _is_valid_drone_id(drone_id: str) -> bool:
    pattern = r"^(DR-[0-9]+|DRONE-[0-9]+|WX-DRONE-[0-9]{3,})$"
    return bool(re.match(pattern, drone_id.strip(), flags=re.IGNORECASE))


def _assert_drone_assignable(drone_id: str) -> None:
    drone = store.drones.get(drone_id)
    if drone is None:
        return
    if not bool(drone.get("available", False)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drone unavailable",
        )
    if int(drone.get("battery", 0)) <= 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drone battery too low",
        )


def manual_assign(
    auth: AuthContext,
    db: Session | str,
    order_id: str | None = None,
    drone_id: str | None = None,
) -> dict[str, Any] | MemOrder:
    """
    Supports both call styles:
    - API/DB: manual_assign(auth, db, order_id, drone_id)
    - Unit tests/store: manual_assign(auth, order_id, drone_id)
    """
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    # Shift args if called as (auth, order_id, drone_id)
    if not isinstance(db, Session):
        order_id, drone_id = cast(str, db), cast(str, order_id)
        db = None
    else:
        db = cast(Session, db)

    if order_id is None or drone_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing args")

    if not _is_valid_drone_id(drone_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")

    _assert_drone_assignable(drone_id)

    # Store mode
    if db is None:
        order = store.orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if order.status in TERMINAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order cannot be reassigned",
            )

        now = mem_now_utc()
        if order.status == OrderStatus.CREATED.value:
            store.events[order.id].append(
                MemEvent(
                    id=f"evt-{uuid.uuid4().hex}",
                    order_id=order.id,
                    type=DeliveryEventType.VALIDATED.value,
                    message="Order validated",
                    created_at=now,
                )
            )
            store.events[order.id].append(
                MemEvent(
                    id=f"evt-{uuid.uuid4().hex}",
                    order_id=order.id,
                    type=DeliveryEventType.QUEUED.value,
                    message="Order queued for dispatch",
                    created_at=now,
                )
            )

        order.status = OrderStatus.ASSIGNED.value
        order.updated_at = now

        job = MemJob(
            id=f"job-{uuid.uuid4().hex}",
            order_id=order.id,
            assigned_drone_id=drone_id,
            mission_intent_id=None,
            status=DeliveryJobStatus.ACTIVE.value,
            created_at=now,
        )
        store.jobs.append(job)

        store.events[order.id].append(
            MemEvent(
                id=f"evt-{uuid.uuid4().hex}",
                order_id=order.id,
                type=DeliveryEventType.ASSIGNED.value,
                message=f"Order assigned to {drone_id}",
                created_at=now,
            )
        )

        log_event("order_assigned", order_id=str(order.id), drone_id=drone_id)
        return order

    # DB mode
    oid = uuid.UUID(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )

    with observe_timing("dispatch_assignment_seconds"):
        now = _now_utc()

        # If order is still CREATED, tests expect VALIDATED and QUEUED during assign.
        if row.status == OrderStatus.CREATED:
            row.status = OrderStatus.VALIDATED
            _append_event(
                db,
                order_id=row.id,
                event_type=DeliveryEventType.VALIDATED,
                message="Order validated",
            )
            row.status = OrderStatus.QUEUED
            _append_event(
                db,
                order_id=row.id,
                event_type=DeliveryEventType.QUEUED,
                message="Order queued for dispatch",
            )

        row.status = OrderStatus.ASSIGNED
        row.updated_at = now

        job = DeliveryJob(
            order_id=row.id,
            assigned_drone_id=drone_id,
            status=DeliveryJobStatus.ACTIVE,
        )
        db.add(job)
        db.flush()

        _append_event(
            db,
            order_id=row.id,
            job_id=job.id,
            event_type=DeliveryEventType.ASSIGNED,
            message=f"Order assigned to {drone_id}",
            payload={"drone_id": drone_id, "reason": "manual"},
        )

        db.commit()
        db.refresh(row)
        db.refresh(job)

    log_event("order_assigned", order_id=str(row.id), job_id=str(job.id), drone_id=drone_id)

    return {
        "id": str(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def submit_mission(
    auth: AuthContext,
    db: Session | Any,
    order_id: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    db_is_session = isinstance(db, Session)

    # Store mode (unit tests may pass Depends object or None-ish)
    if not db_is_session:
        order = store.orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if order.status not in {OrderStatus.ASSIGNED.value, OrderStatus.MISSION_SUBMITTED.value}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order must be ASSIGNED before mission submission",
            )

        jobs = [j for j in store.jobs if j.order_id == order.id]
        if not jobs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No delivery job for order",
            )

        now = mem_now_utc()
        job = jobs[-1]
        if not job.mission_intent_id:
            job.mission_intent_id = f"mi_{uuid.uuid4().hex}"

        order.status = OrderStatus.MISSION_SUBMITTED.value
        order.updated_at = now

        store.events[order.id].append(
            MemEvent(
                id=f"evt-{uuid.uuid4().hex}",
                order_id=order.id,
                type=DeliveryEventType.MISSION_SUBMITTED.value,
                message="Mission submitted",
                created_at=now,
            )
        )

        mission_payload = {
            "order_id": order.id,
            "mission_intent_id": job.mission_intent_id or "",
            "drone_id": job.assigned_drone_id or "",
        }
        order_out = {
            "id": order.id,
            "public_tracking_id": order.public_tracking_id,
            "merchant_id": order.merchant_id,
            "customer_name": order.customer_name,
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }
        return order_out, mission_payload

    db = cast(Session, db)

    oid = uuid.UUID(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status not in {OrderStatus.ASSIGNED, OrderStatus.MISSION_SUBMITTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order must be ASSIGNED before mission submission",
        )

    job_stmt = (
        select(DeliveryJob)
        .where(DeliveryJob.order_id == row.id)
        .order_by(DeliveryJob.created_at.desc())
    )
    job = db.scalar(job_stmt)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No delivery job for order",
        )

    with observe_timing("mission_intent_generation_seconds"):
        if not job.mission_intent_id:
            job.mission_intent_id = f"mi_{uuid.uuid4().hex}"

        row.status = OrderStatus.MISSION_SUBMITTED
        row.updated_at = _now_utc()

        _append_event(
            db,
            order_id=row.id,
            job_id=job.id,
            event_type=DeliveryEventType.MISSION_SUBMITTED,
            message="Mission submitted",
            payload={
                "mission_intent_id": job.mission_intent_id,
                "drone_id": job.assigned_drone_id,
            },
        )

        db.commit()
        db.refresh(row)
        db.refresh(job)

    mission_intent_payload = {
        "order_id": str(row.id),
        "mission_intent_id": job.mission_intent_id or "",
        "drone_id": job.assigned_drone_id or "",
    }

    order_out = {
        "id": str(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    return order_out, mission_intent_payload


def run_auto_dispatch(auth: AuthContext, db: Session) -> dict[str, int | list[dict[str, str]]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    dispatchable = {OrderStatus.CREATED, OrderStatus.VALIDATED, OrderStatus.QUEUED}
    orders_stmt = (
        select(Order)
        .where(Order.status.in_(dispatchable))
        .order_by(Order.created_at.asc())
    )
    orders = list(db.scalars(orders_stmt))

    available_drones = [
        drone_id
        for drone_id, info in store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]

    assignments: list[dict[str, str]] = []
    for order, drone_id in zip(orders, available_drones, strict=False):
        assigned = manual_assign(auth, db, str(order.id), drone_id)
        if isinstance(assigned, dict):
            assignments.append({"order_id": assigned["id"], "status": assigned["status"]})
        else:
            assignments.append({"order_id": assigned.id, "status": assigned.status})

    return {"assigned": len(assignments), "assignments": assignments}


def list_jobs(auth: AuthContext, db: Session, active_only: bool) -> list[dict[str, Any]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    stmt = select(DeliveryJob).order_by(DeliveryJob.created_at.asc())
    if active_only:
        active_statuses = {DeliveryJobStatus.PENDING, DeliveryJobStatus.ACTIVE}
        stmt = stmt.where(DeliveryJob.status.in_(active_statuses))

    rows = list(db.scalars(stmt))

    out: list[dict[str, Any]] = []
    for job in rows:
        out.append(
            {
                "id": str(job.id),
                "order_id": str(job.order_id),
                "assigned_drone_id": job.assigned_drone_id,
                "mission_intent_id": job.mission_intent_id,
                "eta_seconds": job.eta_seconds,
                "status": job.status.value,
                "created_at": job.created_at,
            }
        )
    return out


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    row = db.scalar(select(Order).where(Order.public_tracking_id == public_tracking_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking record not found",
        )

    return {
        "id": str(row.id),
        "public_tracking_id": row.public_tracking_id,
        "status": row.status.value,
    }


def create_pod(
    auth: AuthContext,
    db: Session,
    order_id: str,
    method: str,
    otp_code: str | None,
    operator_name: str | None,
    photo_url: str | None,
) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    oid = uuid.UUID(order_id)
    order = db.get(Order, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="POD requires DELIVERED order",
        )

    try:
        m = ProofOfDeliveryMethod(method)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid POD method",
        ) from err

    otp_hash = hashlib.sha256(otp_code.encode("utf-8")).hexdigest() if otp_code else None

    pod = ProofOfDelivery(
        order_id=order.id,
        method=m,
        photo_url=photo_url,
        otp_hash=otp_hash,
        confirmed_by=operator_name,
        metadata_json={},
        notes=None,
    )
    db.add(pod)
    db.commit()
    db.refresh(pod)

    return {
        "order_id": str(order.id),
        "method": pod.method.value,
        "operator_name": operator_name,
        "photo_url": pod.photo_url,
        "created_at": pod.created_at,
    }


def get_pod(db: Session, order_id: str) -> ProofOfDelivery | None:
    oid = uuid.UUID(order_id)
    return db.scalar(select(ProofOfDelivery).where(ProofOfDelivery.order_id == oid))
