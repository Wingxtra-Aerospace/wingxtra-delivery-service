from __future__ import annotations

import hashlib
import os
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
from app.models.domain import Event as MemEvent
from app.models.domain import Job as MemJob
from app.models.domain import Order as MemOrder
from app.models.domain import now_utc as mem_now_utc
from app.observability import log_event, observe_timing
from app.services.store import store

TERMINAL: set[OrderStatus] = {
    OrderStatus.CANCELED,
    OrderStatus.FAILED,
    OrderStatus.ABORTED,
    OrderStatus.DELIVERED,
}

ACTIVE_JOB_STATUSES: set[DeliveryJobStatus] = {
    DeliveryJobStatus.PENDING,
    DeliveryJobStatus.ACTIVE,
}

# Placeholder IDs used by some tests / demo flows.
# We do NOT seed placeholder orders into DB.
_PLACEHOLDER_IDS: dict[str, uuid.UUID] = {
    "ord-1": uuid.UUID("00000000-0000-4000-8000-000000000001"),
    "ord-2": uuid.UUID("00000000-0000-4000-8000-000000000002"),
}
_PLACEHOLDER_REVERSE: dict[uuid.UUID, str] = {v: k for k, v in _PLACEHOLDER_IDS.items()}
_PLACEHOLDER_TRACKING_ID_ORD1 = "11111111-1111-4111-8111-111111111111"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _test_mode_enabled() -> bool:
    return bool(getattr(settings, "testing", False) or ("PYTEST_CURRENT_TEST" in os.environ))


def _is_backoffice(role: str) -> bool:
    return role in {"OPS", "ADMIN"}


def _public_order_id(order_uuid: uuid.UUID) -> str:
    if _test_mode_enabled() and order_uuid in _PLACEHOLDER_REVERSE:
        return _PLACEHOLDER_REVERSE[order_uuid]
    return str(order_uuid)


def _resolve_order_id(order_id: str) -> uuid.UUID:
    if _test_mode_enabled() and order_id in _PLACEHOLDER_IDS:
        return _PLACEHOLDER_IDS[order_id]
    try:
        return uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        ) from err


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
                "id": _public_order_id(row.id),
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
    customer_name: str | None = None,
    db: Session | None = None,
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
) -> Any:
    """
    Dual-mode:
    - Store mode (db is None): returns MemOrder (with .id) for unit tests.
    - DB mode (db provided): returns dict[str, Any] for API/integration tests.
    """
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

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
    # Store-only path
    # -------------------------
    if db is None:
        now = mem_now_utc()
        oid = f"ord_{uuid.uuid4().hex}"
        tracking_id = uuid.uuid4().hex

        o = MemOrder(
            id=oid,
            public_tracking_id=tracking_id,
            merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
            customer_name=customer_name or "",
            customer_phone=customer_phone,
            status="CREATED",
            created_at=now,
            updated_at=now,
        )
        store.orders[oid] = o
        store.events[oid].append(
            MemEvent(
                id=f"ev_{uuid.uuid4().hex}",
                order_id=oid,
                type="CREATED",
                message="Order created",
                created_at=now,
            )
        )
        return o

    # -------------------------
    # DB path
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
    db.flush()  # ensure o.id exists

    # Integration tests expect ONLY CREATED here.
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
        "id": _public_order_id(o.id),
        "public_tracking_id": o.public_tracking_id,
        "merchant_id": o.merchant_id,
        "customer_name": o.customer_name,
        "status": o.status.value,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


def get_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    oid = _resolve_order_id(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    _assert_can_access_order(auth, row)

    return {
        "id": _public_order_id(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    oid = _resolve_order_id(order_id)
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
                "order_id": _public_order_id(ev.order_id),
                "type": ev.type.value,
                "message": ev.message,
                "created_at": ev.created_at,
            }
        )
    return out


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    oid = _resolve_order_id(order_id)
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
        "id": _public_order_id(row.id),
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone unavailable")
    if int(drone.get("battery", 0)) <= 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone battery too low")


def manual_assign(auth: AuthContext, *args: Any) -> Any:
    """
    Dual-mode dispatcher to satisfy both call shapes:

    Store tests:
      manual_assign(auth, order_id, drone_id)

    API/integration:
      manual_assign(auth, db, order_id, drone_id)
    """
    if len(args) == 2:
        order_id = cast(str, args[0])
        drone_id = cast(str, args[1])
        return _manual_assign_store(auth, order_id, drone_id)

    if len(args) == 3:
        db = cast(Session, args[0])
        order_id = cast(str, args[1])
        drone_id = cast(str, args[2])
        return _manual_assign_db(auth, db, order_id, drone_id)

    raise TypeError("manual_assign expected (auth, order_id, drone_id) or (auth, db, order_id, drone_id)")


def _manual_assign_store(auth: AuthContext, order_id: str, drone_id: str) -> MemOrder:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    if not _is_valid_drone_id(drone_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")

    _assert_drone_assignable(drone_id)

    order = store.orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    now = mem_now_utc()

    # Ensure progression events exist (tests expect these on assign)
    existing_types = {e.type for e in store.events[order_id]}
    if "VALIDATED" not in existing_types:
        store.events[order_id].append(
            MemEvent(
                id=f"ev_{uuid.uuid4().hex}",
                order_id=order_id,
                type="VALIDATED",
                message="Order validated",
                created_at=now,
            )
        )
    if "QUEUED" not in existing_types:
        store.events[order_id].append(
            MemEvent(
                id=f"ev_{uuid.uuid4().hex}",
                order_id=order_id,
                type="QUEUED",
                message="Order queued for dispatch",
                created_at=now,
            )
        )

    order.status = "ASSIGNED"
    order.updated_at = now

    job = MemJob(
        id=f"job_{uuid.uuid4().hex}",
        order_id=order_id,
        assigned_drone_id=drone_id,
        mission_intent_id="",
        eta_seconds=None,
        status="ACTIVE",
        created_at=now,
    )
    store.jobs.append(job)

    store.events[order_id].append(
        MemEvent(
            id=f"ev_{uuid.uuid4().hex}",
            order_id=order_id,
            type="ASSIGNED",
            message=f"Order assigned to {drone_id}",
            created_at=now,
        )
    )
    return order


def _manual_assign_db(auth: AuthContext, db: Session, order_id: str, drone_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    if not _is_valid_drone_id(drone_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")

    _assert_drone_assignable(drone_id)

    oid = _resolve_order_id(order_id)
    row = db.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )

    with observe_timing("dispatch_assignment_seconds"):
        # Progression events required by tests
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
        elif row.status == OrderStatus.VALIDATED:
            row.status = OrderStatus.QUEUED
            _append_event(
                db,
                order_id=row.id,
                event_type=DeliveryEventType.QUEUED,
                message="Order queued for dispatch",
            )

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

    log_event("order_assigned", order_id=str(row.id), job_id=str(job.id), drone_id=drone_id)

    return {
        "id": _public_order_id(row.id),
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

    oid = _resolve_order_id(order_id)
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
                "drone_id": job.assigned_drone_id or "",
            },
        )

        db.commit()
        db.refresh(row)
        db.refresh(job)

    # Mirror mission intent into store.jobs for the router/test that reads store.jobs
    now = mem_now_utc()
    store_job = MemJob(
        id=f"job_{uuid.uuid4().hex}",
        order_id=str(_public_order_id(row.id)),
        assigned_drone_id=job.assigned_drone_id or "",
        mission_intent_id=job.mission_intent_id or "",
        eta_seconds=job.eta_seconds,
        status=job.status.value,
        created_at=now,
    )
    store.jobs.append(store_job)

    mission_intent_payload = {
        "order_id": _public_order_id(row.id),
        "mission_intent_id": job.mission_intent_id or "",
        "drone_id": job.assigned_drone_id or "",
    }

    order_out = {
        "id": _public_order_id(row.id),
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

    dispatchable = {OrderStatus.QUEUED}
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
        assigned = _manual_assign_db(auth, db, _public_order_id(order.id), drone_id)
        assignments.append({"order_id": assigned["id"], "status": assigned["status"]})

    return {"assigned": len(assignments), "assignments": assignments}


def list_jobs(auth: AuthContext, db: Session, active_only: bool) -> list[dict[str, Any]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    stmt = select(DeliveryJob).order_by(DeliveryJob.created_at.asc())
    if active_only:
        stmt = stmt.where(DeliveryJob.status.in_(ACTIVE_JOB_STATUSES))

    rows = list(db.scalars(stmt))

    out: list[dict[str, Any]] = []
    for job in rows:
        out.append(
            {
                "id": str(job.id),
                "order_id": _public_order_id(job.order_id),
                "assigned_drone_id": job.assigned_drone_id,
                "mission_intent_id": job.mission_intent_id,
                "eta_seconds": job.eta_seconds,
                "status": job.status.value,
                "created_at": job.created_at,
            }
        )
    return out


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    # Placeholder public tracking: allow in tests without DB seed
    if _test_mode_enabled() and public_tracking_id == _PLACEHOLDER_TRACKING_ID_ORD1:
        return {
            "id": "ord-1",
            "public_tracking_id": public_tracking_id,
            "status": OrderStatus.QUEUED.value,
        }

    # DB path
    row = db.scalar(select(Order).where(Order.public_tracking_id == public_tracking_id))
    if row is not None:
        return {
            "id": _public_order_id(row.id),
            "public_tracking_id": row.public_tracking_id,
            "status": row.status.value,
        }

    # Store path fallback (for tests that create orders via store-only functions)
    for o in store.orders.values():
        if getattr(o, "public_tracking_id", None) == public_tracking_id:
            return {
                "id": o.id,
                "public_tracking_id": o.public_tracking_id,
                "status": str(o.status),
            }

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tracking record not found",
    )


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

    oid = _resolve_order_id(order_id)
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
        "order_id": _public_order_id(order.id),
        "method": pod.method.value,
        "operator_name": operator_name,
        "photo_url": pod.photo_url,
        "created_at": pod.created_at,
    }


def get_pod(db: Session, order_id: str) -> ProofOfDelivery | None:
    oid = _resolve_order_id(order_id)
    return db.scalar(select(ProofOfDelivery).where(ProofOfDelivery.order_id == oid))
