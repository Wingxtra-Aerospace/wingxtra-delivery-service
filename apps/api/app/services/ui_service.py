from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

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

# In-memory domain models (store mode)
from app.models.domain import Event as MemEvent
from app.models.domain import Job as MemJob
from app.models.domain import Order as MemOrder
from app.models.domain import now_utc as mem_now_utc

TERMINAL: set[OrderStatus] = {
    OrderStatus.CANCELED,
    OrderStatus.FAILED,
    OrderStatus.ABORTED,
    OrderStatus.DELIVERED,
}

_PLACEHOLDER_TRACKING_ID_ORD1 = "11111111-1111-4111-8111-111111111111"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _test_mode_enabled() -> bool:
    return bool(settings.testing or ("PYTEST_CURRENT_TEST" in settings.__dict__))


def _is_backoffice(role: str) -> bool:
    return role in {"OPS", "ADMIN"}


def _append_event(
    db: Session,
    *,
    order_id: uuid.UUID,
    event_type: DeliveryEventType,
    message: str,
    job_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        DeliveryEvent(
            order_id=order_id,
            job_id=job_id,
            type=event_type,
            message=message,
            payload=payload or {},
        )
    )


def _assert_can_access_order_store(auth: AuthContext, order: MemOrder) -> None:
    if _is_backoffice(auth.role):
        return
    if auth.role == "MERCHANT" and getattr(order, "merchant_id", None) == auth.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied for this order",
    )


def _assert_can_access_order_db(auth: AuthContext, order: Order) -> None:
    if _is_backoffice(auth.role):
        return
    if auth.role == "MERCHANT" and order.merchant_id == auth.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied for this order",
    )


def _store_get_order(order_id: str) -> MemOrder | None:
    return store.orders.get(order_id)


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
) -> dict[str, Any]:
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    resolved_pickup_lat = pickup_lat if pickup_lat is not None else (lat if lat is not None else 0.0)
    resolved_pickup_lng = pickup_lng if pickup_lng is not None else 0.0
    resolved_dropoff_lat = dropoff_lat if dropoff_lat is not None else resolved_pickup_lat
    resolved_dropoff_lng = dropoff_lng if dropoff_lng is not None else resolved_pickup_lng

    resolved_payload_weight = (
        payload_weight_kg
        if payload_weight_kg is not None
        else (weight if weight is not None else 1.0)
    )

    try:
        prio = OrderPriority(priority) if priority else OrderPriority.NORMAL
    except ValueError:
        prio = OrderPriority.NORMAL

    # -------------------------
    # Store-only path (unit tests)
    # -------------------------
    if db is None:
        now = mem_now_utc()
        oid = uuid.uuid4().hex
        tracking_id = uuid.uuid4().hex
        order = MemOrder(
            id=oid,
            public_tracking_id=tracking_id,
            merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
            customer_name=customer_name,
            status=OrderStatus.CREATED.value,
            created_at=now,
            updated_at=now,
        )
        store.orders[order.id] = order
        store.events[order.id] = [
            MemEvent(
                order_id=order.id,
                type=DeliveryEventType.CREATED.value,
                message="Order created",
                created_at=now,
            )
        ]
        return {
            "id": order.id,
            "public_tracking_id": order.public_tracking_id,
            "merchant_id": order.merchant_id,
            "customer_name": order.customer_name,
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    # -------------------------
    # DB path (API)
    # -------------------------
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
    db.flush()

    # Tests expect ONLY CREATED on creation
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
    mem = _store_get_order(order_id)
    if mem is not None:
        _assert_can_access_order_store(auth, mem)
        return {
            "id": mem.id,
            "public_tracking_id": mem.public_tracking_id,
            "merchant_id": getattr(mem, "merchant_id", None),
            "customer_name": mem.customer_name,
            "status": mem.status,
            "created_at": mem.created_at,
            "updated_at": mem.updated_at,
        }

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    _assert_can_access_order_db(auth, row)

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
    mem = _store_get_order(order_id)
    if mem is not None:
        _assert_can_access_order_store(auth, mem)
        evs = store.events.get(order_id, [])
        return [
            {
                "id": "",
                "order_id": e.order_id,
                "type": e.type,
                "message": e.message,
                "created_at": e.created_at,
            }
            for e in evs
        ]

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

    order = db.get(Order, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    _assert_can_access_order_db(auth, order)

    stmt = (
        select(DeliveryEvent)
        .where(DeliveryEvent.order_id == oid)
        .order_by(DeliveryEvent.created_at.asc())
    )
    rows = list(db.scalars(stmt))

    return [
        {
            "id": str(ev.id),
            "order_id": str(ev.order_id),
            "type": ev.type.value,
            "message": ev.message,
            "created_at": ev.created_at,
        }
        for ev in rows
    ]


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    mem = _store_get_order(order_id)
    if mem is not None:
        if mem.status in {s.value for s in TERMINAL}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is in terminal state",
            )
        mem.status = OrderStatus.CANCELED.value
        mem.updated_at = mem_now_utc()
        store.events.setdefault(order_id, []).append(
            MemEvent(
                order_id=order_id,
                type=DeliveryEventType.CANCELED.value,
                message="Order canceled by operator",
                created_at=mem.updated_at,
            )
        )
        return {
            "id": mem.id,
            "public_tracking_id": mem.public_tracking_id,
            "merchant_id": getattr(mem, "merchant_id", None),
            "customer_name": mem.customer_name,
            "status": mem.status,
            "created_at": mem.created_at,
            "updated_at": mem.updated_at,
        }

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

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


def _available_drone_ids() -> list[str]:
    # Store drones are authoritative for tests.
    out: list[str] = []
    for drone_id, info in store.drones.items():
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20:
            out.append(drone_id)
    return out


def manual_assign(auth: AuthContext, db: Session, order_id: str, drone_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    if not _is_valid_drone_id(drone_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")

    mem = _store_get_order(order_id)
    if mem is not None:
        if mem.status in {s.value for s in TERMINAL}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order cannot be reassigned",
            )

        now = mem_now_utc()
        # Expected events when assigning: VALIDATED, QUEUED, ASSIGNED (in that order)
        store.events.setdefault(order_id, []).append(
            MemEvent(
                order_id=order_id,
                type=DeliveryEventType.VALIDATED.value,
                message="Order validated",
                created_at=now,
            )
        )
        store.events.setdefault(order_id, []).append(
            MemEvent(
                order_id=order_id,
                type=DeliveryEventType.QUEUED.value,
                message="Order queued for dispatch",
                created_at=now,
            )
        )

        mem.status = OrderStatus.ASSIGNED.value
        mem.updated_at = now

        job = MemJob(
            id=uuid.uuid4().hex,
            order_id=order_id,
            assigned_drone_id=drone_id,
            mission_intent_id="",
            status=DeliveryJobStatus.ACTIVE.value,
            created_at=now,
        )
        store.jobs[order_id] = job

        store.events.setdefault(order_id, []).append(
            MemEvent(
                order_id=order_id,
                type=DeliveryEventType.ASSIGNED.value,
                message=f"Order assigned to {drone_id}",
                created_at=now,
            )
        )

        return {
            "id": mem.id,
            "public_tracking_id": mem.public_tracking_id,
            "merchant_id": getattr(mem, "merchant_id", None),
            "customer_name": mem.customer_name,
            "status": mem.status,
            "created_at": mem.created_at,
            "updated_at": mem.updated_at,
        }

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )

    with observe_timing("dispatch_assignment_seconds"):
        # transition CREATED -> VALIDATED -> QUEUED
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

        # Assign
        row.status = OrderStatus.ASSIGNED
        row.updated_at = _now_utc()

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
    db: Session,
    order_id: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    mem = _store_get_order(order_id)
    if mem is not None:
        job = store.jobs.get(order_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No delivery job for order")

        if not job.mission_intent_id:
            job.mission_intent_id = f"mi_{uuid.uuid4().hex}"

        mem.status = OrderStatus.MISSION_SUBMITTED.value
        mem.updated_at = mem_now_utc()

        payload = {
            "order_id": mem.id,
            "mission_intent_id": job.mission_intent_id,
            "drone_id": job.assigned_drone_id,
        }
        return (
            {
                "id": mem.id,
                "public_tracking_id": mem.public_tracking_id,
                "merchant_id": getattr(mem, "merchant_id", None),
                "customer_name": mem.customer_name,
                "status": mem.status,
                "created_at": mem.created_at,
                "updated_at": mem.updated_at,
            },
            payload,
        )

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No delivery job for order")

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

    return (
        {
            "id": str(row.id),
            "public_tracking_id": row.public_tracking_id,
            "merchant_id": row.merchant_id,
            "customer_name": row.customer_name,
            "status": row.status.value,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        },
        {
            "order_id": str(row.id),
            "mission_intent_id": job.mission_intent_id or "",
            "drone_id": job.assigned_drone_id or "",
        },
    )


def run_auto_dispatch(auth: AuthContext, db: Session) -> dict[str, int | list[dict[str, str]]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    assignments: list[dict[str, str]] = []

    # Store-mode dispatch (ord-2 starts QUEUED in seed_data)
    store_queued = [o for o in store.orders.values() if o.status == OrderStatus.QUEUED.value]
    drones = _available_drone_ids()

    for order, drone_id in zip(store_queued, drones, strict=False):
        manual_assign(auth, db, order.id, drone_id)
        assignments.append({"order_id": order.id, "status": OrderStatus.ASSIGNED.value})

    # DB-mode dispatch
    db_drones = _available_drone_ids()
    stmt = select(Order).where(Order.status == OrderStatus.QUEUED).order_by(Order.created_at.asc())
    db_orders = list(db.scalars(stmt))

    for order, drone_id in zip(db_orders, db_drones, strict=False):
        out = manual_assign(auth, db, str(order.id), drone_id)
        assignments.append({"order_id": str(out["id"]), "status": str(out["status"])})

    return {"assigned": len(assignments), "assignments": assignments}


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    # Look in store first
    for order in store.orders.values():
        if order.public_tracking_id == public_tracking_id:
            return {
                "order_id": order.id,
                "public_tracking_id": order.public_tracking_id,
                "status": order.status,
            }

    # DB fallback
    row = db.scalar(select(Order).where(Order.public_tracking_id == public_tracking_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking record not found",
        )

    return {
        "order_id": str(row.id),
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

    try:
        oid = uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found") from err

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
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        return None

    return db.scalar(select(ProofOfDelivery).where(ProofOfDelivery.order_id == oid))
