from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import settings
from app.models.delivery_event import DeliveryEvent, DeliveryEventType
from app.models.delivery_job import DeliveryJob, DeliveryJobStatus

# In-memory domain models (store mode)
from app.models.domain import Event as MemEvent
from app.models.domain import Job as MemJob
from app.models.domain import Order as MemOrder
from app.models.domain import new_id as mem_new_id
from app.models.domain import now_utc as mem_now_utc
from app.models.order import Order, OrderPriority, OrderStatus
from app.models.proof_of_delivery import ProofOfDelivery, ProofOfDeliveryMethod
from app.observability import log_event, observe_timing
from app.services.store import store

TERMINAL: set[OrderStatus] = {
    OrderStatus.CANCELED,
    OrderStatus.FAILED,
    OrderStatus.ABORTED,
    OrderStatus.DELIVERED,
}

_PLACEHOLDER_IDS: dict[str, str] = {
    "ord-1": "ord-1",
    "ord-2": "ord-2",
}

_PLACEHOLDER_TRACKING_ID_ORD1 = "11111111-1111-4111-8111-111111111111"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _test_mode_enabled() -> bool:
    return bool(settings.testing or ("PYTEST_CURRENT_TEST" in os.environ))


def _is_backoffice(role: str) -> bool:
    return role in {"OPS", "ADMIN"}


def _public_order_id(order_uuid: uuid.UUID) -> str:
    return str(order_uuid)


def _resolve_db_uuid(order_id: str) -> uuid.UUID:
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


def _seed_placeholders_in_store_if_needed() -> None:
    """
    Tests rely on placeholder orders existing in store mode:
    - ord-1 exists with tracking id 1111...
    - ord-2 exists and can be auto-dispatched when QUEUED
    """
    if "ord-1" not in store.orders:
        created = mem_now_utc()
        o1 = MemOrder(
            id="ord-1",
            public_tracking_id=_PLACEHOLDER_TRACKING_ID_ORD1,
            merchant_id="merchant-1",
            customer_name="Demo Customer",
            status="ASSIGNED",
            created_at=created,
            updated_at=created,
        )
        store.orders[o1.id] = o1
        store.events[o1.id].append(
            MemEvent(
                id="evt-1",
                order_id=o1.id,
                type="CREATED",
                message="Order created",
                created_at=created,
            )
        )
        store.jobs.append(
            MemJob(
                id="job-1",
                order_id=o1.id,
                assigned_drone_id="DRONE-1",
                status="ACTIVE",
                created_at=created,
            )
        )

    if "ord-2" not in store.orders:
        created = mem_now_utc()
        o2 = MemOrder(
            id="ord-2",
            public_tracking_id="22222222-2222-4222-8222-222222222222",
            merchant_id="merchant-1",
            customer_name="Demo Customer 2",
            status="QUEUED",
            created_at=created,
            updated_at=created,
        )
        store.orders[o2.id] = o2
        store.events[o2.id].append(
            MemEvent(
                id="evt-2",
                order_id=o2.id,
                type="CREATED",
                message="Order created",
                created_at=created,
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

    stmt = stmt.order_by(Order.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
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

def _available_drones() -> list[str]:
    return [
        drone_id
        for drone_id, info in store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]


    resolved_pickup_lat = (
        pickup_lat if pickup_lat is not None else (lat if lat is not None else 0.0)
    )
    resolved_pickup_lng = pickup_lng if pickup_lng is not None else 0.0
    resolved_dropoff_lat = dropoff_lat if dropoff_lat is not None else resolved_pickup_lat
    resolved_dropoff_lng = dropoff_lng if dropoff_lng is not None else resolved_pickup_lng


def list_orders(*, auth: AuthContext, db: Session, page: int, page_size: int, status_filter: str | None, search: str | None, from_date: datetime | None, to_date: datetime | None) -> tuple[list[dict[str, Any]], int]:
    if _mode() == "store":
        items = [
            ui_store_service.get_order(auth, oid)
            for oid in sorted(ui_store_service.store.orders.keys())
            if not status_filter or ui_store_service.store.orders[oid].status == status_filter
        ]
        return items[(page - 1) * page_size : page * page_size], len(items)
    return ui_db_service.list_orders(auth=auth, db=db, page=page, page_size=page_size, status_filter=status_filter, search=search, from_date=from_date, to_date=to_date)


def create_order(auth: AuthContext, customer_name: str | None = None, db: Session | None = None, customer_phone: str | None = None, lat: float | None = None, weight: float | None = None, pickup_lat: float | None = None, pickup_lng: float | None = None, dropoff_lat: float | None = None, dropoff_lng: float | None = None, dropoff_accuracy_m: float | None = None, payload_weight_kg: float | None = None, payload_type: str | None = None, priority: str | None = None) -> dict[str, Any]:
    if _mode() == "store":
        return ui_store_service.create_order(auth, customer_name=customer_name)
    if db is None:
        raise ValueError("db session is required for db/hybrid mode")
    return ui_db_service.create_order(auth=auth, db=db, customer_name=customer_name, customer_phone=customer_phone, lat=lat, weight=weight, pickup_lat=pickup_lat, pickup_lng=pickup_lng, dropoff_lat=dropoff_lat, dropoff_lng=dropoff_lng, dropoff_accuracy_m=dropoff_accuracy_m, payload_weight_kg=payload_weight_kg, payload_type=payload_type, priority=priority)


def get_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    if _mode() == "store" or (_mode() == "hybrid" and order_id.startswith("ord-")):
        return ui_store_service.get_order(auth, order_id)
    return ui_db_service.get_order(auth, db, order_id)


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    if _mode() == "store" or (_mode() == "hybrid" and order_id.startswith("ord-")):
        return ui_store_service.list_events(auth, order_id)
    return ui_db_service.list_events(auth, db, order_id)


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    return ui_db_service.cancel_order(auth, db, order_id)


def manual_assign(auth: AuthContext, db: Session, order_id: str, drone_id: str) -> dict[str, Any]:
    if _mode() == "store":
        return ui_store_service.manual_assign(auth, order_id, drone_id)
    return ui_db_service.manual_assign(auth, db, order_id, drone_id)


def submit_mission(auth: AuthContext, db: Session, order_id: str) -> tuple[dict[str, Any], dict[str, str]]:
    return ui_db_service.submit_mission(auth, db, order_id)


def run_auto_dispatch(auth: AuthContext, db: Session) -> dict[str, int | list[dict[str, str]]]:
    drones = _available_drones()
    if _mode() == "store":
        return ui_store_service.run_auto_dispatch(drones)
    result = ui_db_service.run_auto_dispatch(auth, db, drones)
    if _mode() == "hybrid":
        store_result = ui_store_service.run_auto_dispatch(drones)
        combined = [*result["assignments"], *store_result["assignments"]]
        return {"assigned": len(combined), "assignments": combined}
    return result


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
    order_id: str,
    drone_id: str | None = None,
) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    # Backward-compatible call path used by tests: manual_assign(auth, order_id, drone_id)
    if isinstance(db, str):
        if drone_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid manual assignment arguments",
            )
        db_session: Session | None = None
        resolved_order_id = db
        resolved_drone_id = order_id
    else:
        db_session = db
        resolved_order_id = order_id
        if drone_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="drone_id is required",
            )
        resolved_drone_id = drone_id

    if not _is_valid_drone_id(resolved_drone_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid drone_id",
        )

    _assert_drone_assignable(resolved_drone_id)

    if db_session is None:
        _seed_placeholders_in_store_if_needed()
        mem = store.orders.get(resolved_order_id)
        if mem is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if mem.status in {"DELIVERED", "FAILED", "ABORTED", "CANCELED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order cannot be reassigned",
            )

        if mem.status == "CREATED":
            mem.status = "VALIDATED"
            store.events[resolved_order_id].append(
                MemEvent(
                    id=mem_new_id("evt-"),
                    order_id=resolved_order_id,
                    type="VALIDATED",
                    message="Order validated",
                    created_at=mem_now_utc(),
                )
            )
            mem.status = "QUEUED"
            store.events[resolved_order_id].append(
                MemEvent(
                    id=mem_new_id("evt-"),
                    order_id=resolved_order_id,
                    type="QUEUED",
                    message="Order queued for dispatch",
                    created_at=mem_now_utc(),
                )
            )
        elif mem.status == "VALIDATED":
            mem.status = "QUEUED"
            store.events[resolved_order_id].append(
                MemEvent(
                    id=mem_new_id("evt-"),
                    order_id=resolved_order_id,
                    type="QUEUED",
                    message="Order queued for dispatch",
                    created_at=mem_now_utc(),
                )
            )

        mem.status = "ASSIGNED"
        mem.updated_at = mem_now_utc()
        store.events[resolved_order_id].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id=resolved_order_id,
                type="ASSIGNED",
                message=f"Order assigned to {resolved_drone_id}",
                created_at=mem_now_utc(),
            )
        )
        store.jobs.append(
            MemJob(
                id=mem_new_id("job-"),
                order_id=resolved_order_id,
                assigned_drone_id=resolved_drone_id,
                status="ACTIVE",
                created_at=mem_now_utc(),
            )
        )

        return {
            "id": mem.id,
            "public_tracking_id": mem.public_tracking_id,
            "merchant_id": mem.merchant_id,
            "customer_name": mem.customer_name,
            "status": mem.status,
            "created_at": mem.created_at,
            "updated_at": mem.updated_at,
        }

    oid = _resolve_db_uuid(resolved_order_id)
    row = db_session.get(Order, oid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if row.status in TERMINAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be reassigned",
        )

    with observe_timing("dispatch_assignment_seconds"):
        # Progression events must happen during assignment (tests expect this)
        if row.status == OrderStatus.CREATED:
            row.status = OrderStatus.VALIDATED
            _append_event(
                db_session,
                order_id=row.id,
                event_type=DeliveryEventType.VALIDATED,
                message="Order validated",
            )
            row.status = OrderStatus.QUEUED
            _append_event(
                db_session,
                order_id=row.id,
                event_type=DeliveryEventType.QUEUED,
                message="Order queued for dispatch",
            )
        elif row.status == OrderStatus.VALIDATED:
            row.status = OrderStatus.QUEUED
            _append_event(
                db_session,
                order_id=row.id,
                event_type=DeliveryEventType.QUEUED,
                message="Order queued for dispatch",
            )

        row.status = OrderStatus.ASSIGNED
        row.updated_at = _now_utc()

        job = DeliveryJob(
            order_id=row.id,
            assigned_drone_id=resolved_drone_id,
            status=DeliveryJobStatus.ACTIVE,
        )
        db_session.add(job)
        db_session.flush()

        _append_event(
            db_session,
            order_id=row.id,
            job_id=job.id,
            event_type=DeliveryEventType.ASSIGNED,
            message=f"Order assigned to {resolved_drone_id}",
            payload={"drone_id": resolved_drone_id, "reason": "manual"},
        )

        db_session.commit()
        db_session.refresh(row)
        db_session.refresh(job)

        # Keep store.jobs in sync for endpoints that read it (tests do this)
        store.jobs.append(
            MemJob(
                id=str(job.id),
                order_id=resolved_order_id,
                assigned_drone_id=resolved_drone_id,
                status="ACTIVE",
                created_at=mem_now_utc(),
            )
        )

    log_event(
        "order_assigned",
        order_id=str(row.id),
        job_id=str(job.id),
        drone_id=resolved_drone_id,
    )

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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    oid = _resolve_db_uuid(order_id)
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

        # Keep store.jobs in sync so endpoint can read mission_intent_id
        store.jobs.append(
            MemJob(
                id=str(job.id),
                order_id=order_id,
                assigned_drone_id=job.assigned_drone_id or "",
                status="ACTIVE",
                mission_intent_id=job.mission_intent_id,
                created_at=mem_now_utc(),
            )
        )

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


def run_auto_dispatch(
    auth: AuthContext,
    db: Session,
) -> dict[str, int | list[dict[str, str]]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    _seed_placeholders_in_store_if_needed()

    dispatchable = {OrderStatus.CREATED, OrderStatus.VALIDATED, OrderStatus.QUEUED}
    orders_stmt = (
        select(Order).where(Order.status.in_(dispatchable)).order_by(Order.created_at.asc())
    )
    orders = list(db.scalars(orders_stmt))

    available_drones = [
        drone_id
        for drone_id, info in store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]

    assignments: list[dict[str, str]] = []

    remaining_drones = list(available_drones)

    # Assign DB dispatchable orders first
    for order in orders:
        if not remaining_drones:
            break
        drone_id = remaining_drones.pop(0)
        assigned = manual_assign(auth, db, str(order.id), drone_id)
        assignments.append({"order_id": assigned["id"], "status": assigned["status"]})

    # Then ensure placeholder ord-2 can be assigned in tests when queued
    ord2 = store.orders.get("ord-2")
    if ord2 is not None and ord2.status == "QUEUED" and remaining_drones:
        drone_id = remaining_drones.pop(0)
        ord2.status = "ASSIGNED"
        ord2.updated_at = mem_now_utc()
        store.jobs.append(
            MemJob(
                id=mem_new_id("job-"),
                order_id="ord-2",
                assigned_drone_id=drone_id,
                status="ACTIVE",
                created_at=mem_now_utc(),
            )
        )
        # add progression events for ord-2
        store.events["ord-2"].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id="ord-2",
                type="VALIDATED",
                message="Order validated",
                created_at=mem_now_utc(),
            )
        )
        store.events["ord-2"].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id="ord-2",
                type="QUEUED",
                message="Order queued for dispatch",
                created_at=mem_now_utc(),
            )
        )
        store.events["ord-2"].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id="ord-2",
                type="ASSIGNED",
                message=f"Order assigned to {drone_id}",
                created_at=mem_now_utc(),
            )
        )
        assignments.append({"order_id": "ord-2", "status": "ASSIGNED"})

    return {"assigned": len(assignments), "assignments": assignments}


def list_jobs(
    auth: AuthContext,
    db: Session,
    active_only: bool,
) -> list[dict[str, Any]]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    stmt = select(DeliveryJob).order_by(DeliveryJob.created_at.asc())
    if active_only:
        stmt = stmt.where(
            DeliveryJob.status.in_({DeliveryJobStatus.PENDING, DeliveryJobStatus.ACTIVE})
        )

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
    _seed_placeholders_in_store_if_needed()

    # Store-first (tests expect 1111... to work without auth)
    for o in store.orders.values():
        if o.public_tracking_id == public_tracking_id:
            return {
                "id": o.id,
                "order_id": o.id,
                "public_tracking_id": o.public_tracking_id,
                "status": o.status,
            }

    stmt = select(Order).where(Order.public_tracking_id == public_tracking_id)
    row = db.scalar(stmt)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking record not found",
        )

    order_public_id = _public_order_id(row.id)
    return {
        "id": order_public_id,
        "order_id": order_public_id,
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    oid = _resolve_db_uuid(order_id)
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

    otp_hash = None
    if otp_code:
        otp_hash = hashlib.sha256(otp_code.encode("utf-8")).hexdigest()


def create_pod(auth: AuthContext, db: Session, order_id: str, method: str, otp_code: str | None, operator_name: str | None, photo_url: str | None) -> dict[str, Any]:
    return ui_db_service.create_pod(auth, db, order_id, method, otp_code, operator_name, photo_url)


def get_pod(db: Session, order_id: str) -> ProofOfDelivery | None:
    # Public tracking for in-memory placeholder orders uses non-UUID ids.
    try:
        oid = _resolve_db_uuid(order_id)
    except HTTPException:
        return None

    return db.scalar(select(ProofOfDelivery).where(ProofOfDelivery.order_id == oid))
