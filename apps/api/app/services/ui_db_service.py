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
from app.models.delivery_event import DeliveryEvent, DeliveryEventType
from app.models.delivery_job import DeliveryJob, DeliveryJobStatus
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.proof_of_delivery import ProofOfDelivery, ProofOfDeliveryMethod
from app.observability import log_event, observe_timing

TERMINAL: set[OrderStatus] = {
    OrderStatus.CANCELED,
    OrderStatus.FAILED,
    OrderStatus.ABORTED,
    OrderStatus.DELIVERED,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_backoffice(role: str) -> bool:
    return role in {"OPS", "ADMIN"}


def _public_order_id(order_uuid: uuid.UUID) -> str:
    return str(order_uuid)


def _resolve_db_uuid(order_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(order_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        ) from err


def _assert_can_access_order(auth: AuthContext, order: Order) -> None:
    if _is_backoffice(auth.role):
        return
    if auth.role == "MERCHANT" and order.merchant_id == auth.user_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this order"
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


def _order_to_dict(row: Order) -> dict[str, Any]:
    return {
        "id": _public_order_id(row.id),
        "public_tracking_id": row.public_tracking_id,
        "merchant_id": row.merchant_id,
        "customer_name": row.customer_name,
        "status": row.status.value,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


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
    rows = list(
        db.scalars(
            stmt.order_by(Order.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return [_order_to_dict(r) for r in rows], int(total)


def create_order(
    auth: AuthContext,
    db: Session,
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    try:
        prio = OrderPriority(priority) if priority else OrderPriority.NORMAL
    except ValueError:
        prio = OrderPriority.NORMAL
    resolved_pickup_lat = (
        pickup_lat if pickup_lat is not None else (lat if lat is not None else 0.0)
    )
    resolved_pickup_lng = pickup_lng if pickup_lng is not None else 0.0
    resolved_dropoff_lat = dropoff_lat if dropoff_lat is not None else resolved_pickup_lat
    resolved_dropoff_lng = dropoff_lng if dropoff_lng is not None else resolved_pickup_lng
    resolved_payload_weight = (
        payload_weight_kg
        if payload_weight_kg is not None
        else (weight if weight is not None else 1.0)
    )
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
    _append_event(db, order_id=o.id, event_type=DeliveryEventType.CREATED, message="Order created")
    db.commit()
    db.refresh(o)
    log_event("order_created", order_id=str(o.id))
    return _order_to_dict(o)


def get_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    row = db.get(Order, _resolve_db_uuid(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _assert_can_access_order(auth, row)
    return _order_to_dict(row)


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    oid = _resolve_db_uuid(order_id)
    order = db.get(Order, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _assert_can_access_order(auth, order)
    rows = list(
        db.scalars(
            select(DeliveryEvent)
            .where(DeliveryEvent.order_id == oid)
            .order_by(DeliveryEvent.created_at.asc())
        )
    )
    return [
        {
            "id": str(ev.id),
            "order_id": _public_order_id(ev.order_id),
            "type": ev.type.value,
            "message": ev.message,
            "created_at": ev.created_at,
        }
        for ev in rows
    ]


def manual_assign(auth: AuthContext, db: Session, order_id: str, drone_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    if not re.match(
        r"^(DR-[0-9]+|DRONE-[0-9]+|WX-DRONE-[0-9]{3,})$", drone_id.strip(), flags=re.IGNORECASE
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid drone_id")
    row = db.get(Order, _resolve_db_uuid(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Order cannot be reassigned"
        )
    with observe_timing("dispatch_assignment_seconds"):
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
            order_id=row.id, assigned_drone_id=drone_id, status=DeliveryJobStatus.ACTIVE
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
    log_event("order_assigned", order_id=str(row.id), drone_id=drone_id)
    return _order_to_dict(row)


def submit_mission(
    auth: AuthContext, db: Session, order_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    row = db.get(Order, _resolve_db_uuid(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if row.status not in {OrderStatus.ASSIGNED, OrderStatus.MISSION_SUBMITTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order must be ASSIGNED before mission submission",
        )
    job = db.scalar(
        select(DeliveryJob)
        .where(DeliveryJob.order_id == row.id)
        .order_by(DeliveryJob.created_at.desc())
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No delivery job for order"
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
            payload={"mission_intent_id": job.mission_intent_id, "drone_id": job.assigned_drone_id},
        )
        db.commit()
        db.refresh(row)
        db.refresh(job)
    return _order_to_dict(row), {
        "order_id": _public_order_id(row.id),
        "mission_intent_id": job.mission_intent_id or "",
        "drone_id": job.assigned_drone_id or "",
    }


def run_auto_dispatch(
    auth: AuthContext,
    db: Session,
    available_drones: list[str],
    max_assignments: int | None = None,
) -> dict[str, int | list[dict[str, str]]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    orders = list(
        db.scalars(
            select(Order)
            .where(
                Order.status.in_({OrderStatus.CREATED, OrderStatus.VALIDATED, OrderStatus.QUEUED})
            )
            .order_by(Order.created_at.asc())
        )
    )
    assignments: list[dict[str, str]] = []
    remaining = list(available_drones)
    for order in orders:
        if not remaining:
            break
        if max_assignments is not None and len(assignments) >= max_assignments:
            break
        assigned = manual_assign(auth, db, str(order.id), remaining.pop(0))
        assignments.append({"order_id": assigned["id"], "status": assigned["status"]})
    return {"assigned": len(assignments), "assignments": assignments}


def list_jobs(auth: AuthContext, db: Session, active_only: bool) -> list[dict[str, Any]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    stmt = select(DeliveryJob).order_by(DeliveryJob.created_at.asc())
    if active_only:
        stmt = stmt.where(
            DeliveryJob.status.in_({DeliveryJobStatus.PENDING, DeliveryJobStatus.ACTIVE})
        )
    rows = list(db.scalars(stmt))
    return [
        {
            "id": str(job.id),
            "order_id": _public_order_id(job.order_id),
            "assigned_drone_id": job.assigned_drone_id,
            "mission_intent_id": job.mission_intent_id,
            "eta_seconds": job.eta_seconds,
            "status": job.status.value,
            "created_at": job.created_at,
        }
        for job in rows
    ]


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    row = db.scalar(select(Order).where(Order.public_tracking_id == public_tracking_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found"
        )

    timeline_rows = list(
        db.scalars(
            select(DeliveryEvent)
            .where(DeliveryEvent.order_id == row.id)
            .order_by(DeliveryEvent.created_at.asc())
        )
    )
    milestones = [event.type.value for event in timeline_rows]

    order_public_id = _public_order_id(row.id)
    return {
        "id": order_public_id,
        "order_id": order_public_id,
        "public_tracking_id": row.public_tracking_id,
        "status": row.status.value,
        "milestones": milestones or None,
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
    order = db.get(Order, _resolve_db_uuid(order_id))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="POD requires DELIVERED order"
        )
    try:
        m = ProofOfDeliveryMethod(method)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid POD method"
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
    try:
        oid = _resolve_db_uuid(order_id)
    except HTTPException:
        return None
    return db.scalar(select(ProofOfDelivery).where(ProofOfDelivery.order_id == oid))


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    row = db.get(Order, _resolve_db_uuid(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Order is in terminal state"
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
    return _order_to_dict(row)


def update_order(
    auth: AuthContext,
    db: Session,
    order_id: str,
    customer_phone: str | None,
    dropoff_lat: float | None,
    dropoff_lng: float | None,
    priority: str | None,
) -> dict[str, Any]:
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    row = db.get(Order, _resolve_db_uuid(order_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    _assert_can_access_order(auth, row)

    if row.status in TERMINAL:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order cannot be updated")

    if customer_phone is None and dropoff_lat is None and dropoff_lng is None and priority is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided"
        )

    if (dropoff_lat is None) ^ (dropoff_lng is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dropoff_lat and dropoff_lng must be provided together",
        )

    changed = False
    if customer_phone is not None:
        row.customer_phone = customer_phone
        changed = True

    if dropoff_lat is not None and dropoff_lng is not None:
        row.dropoff_lat = dropoff_lat
        row.dropoff_lng = dropoff_lng
        changed = True

    if priority is not None:
        try:
            row.priority = OrderPriority(priority)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid priority",
            ) from err
        changed = True

    if changed:
        row.updated_at = _now_utc()
        db.commit()
        db.refresh(row)

    return _order_to_dict(row)
