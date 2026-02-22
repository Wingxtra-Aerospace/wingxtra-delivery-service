from __future__ import annotations

import json
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import resolved_ui_service_mode
from app.services import ui_db_service, ui_store_service
from app.services.safety import assert_production_safe


def _mode() -> str:
    mode = resolved_ui_service_mode()
    assert_production_safe()
    return mode


def _is_placeholder_order_id(order_id: str) -> bool:
    return order_id.startswith("ord-")


def list_orders(
    *,
    auth: AuthContext,
    db: Session,
    page: int,
    page_size: int,
    status_filter: str | None,
    search: str | None,
    from_date,
    to_date,
) -> tuple[list[dict[str, Any]], int]:
    mode = _mode()
    if mode == "store":
        items = [
            ui_store_service.get_order(auth, oid)
            for oid in sorted(ui_store_service.store.orders.keys())
            if not status_filter or ui_store_service.store.orders[oid].status == status_filter
        ]
        return items[(page - 1) * page_size : page * page_size], len(items)

    db_items, db_total = ui_db_service.list_orders(
        auth=auth,
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )

    # In hybrid mode, list endpoint should remain DB-backed to avoid leaking
    # placeholder store orders into normal operational listing flows.
    return db_items, db_total


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
    mode = _mode()
    if mode == "store" or db is None:
        order = ui_store_service.create_order(auth, customer_name=customer_name)
        return SimpleNamespace(**order)

    return ui_db_service.create_order(
        auth=auth,
        db=db,
        customer_name=customer_name,
        customer_phone=customer_phone,
        lat=lat,
        weight=weight,
        pickup_lat=pickup_lat,
        pickup_lng=pickup_lng,
        dropoff_lat=dropoff_lat,
        dropoff_lng=dropoff_lng,
        dropoff_accuracy_m=dropoff_accuracy_m,
        payload_weight_kg=payload_weight_kg,
        payload_type=payload_type,
        priority=priority,
    )


def get_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    assert_production_safe(order_id=order_id)
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        return ui_store_service.get_order(auth, order_id)
    return ui_db_service.get_order(auth, db, order_id)


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    assert_production_safe(order_id=order_id)
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        return ui_store_service.list_events(auth, order_id)
    return ui_db_service.list_events(auth, db, order_id)


def ingest_order_event(
    auth: AuthContext,
    db: Session,
    order_id: str,
    event_type: str,
    occurred_at,
    source: str = "ops_event_ingest",
    event_id: str | None = None,
) -> dict[str, Any]:
    assert_production_safe(order_id=order_id)
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Placeholder orders do not support event ingestion",
        )
    return ui_db_service.ingest_order_event(
        auth,
        db,
        order_id,
        event_type,
        occurred_at,
        source,
        event_id,
    )


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
    assert_production_safe(order_id=order_id)
    if _mode() == "store" or _is_placeholder_order_id(order_id):
        order = ui_store_service.get_order(auth, order_id)
        ui_store_service.store.orders[order_id].status = "CANCELED"
        return {**order, "status": "CANCELED"}
    return ui_db_service.cancel_order(auth, db, order_id)


def manual_assign(
    auth: AuthContext,
    db: Session | str,
    order_id: str,
    drone_id: str | None = None,
) -> dict[str, Any]:
    assert_production_safe(order_id=order_id)
    if drone_id is not None:
        _assert_drone_assignable(drone_id)

    if isinstance(db, str):
        # Legacy call signature: manual_assign(auth, order_id, drone_id)
        _assert_drone_assignable(order_id)
        return ui_store_service.manual_assign(auth, db, order_id)

    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        if drone_id is None:
            raise ValueError("drone_id is required")
        return ui_store_service.manual_assign(auth, order_id, drone_id)

    if drone_id is None:
        raise ValueError("drone_id is required")
    return ui_db_service.manual_assign(auth, db, order_id, drone_id)


def update_order(
    auth: AuthContext,
    db: Session,
    order_id: str,
    customer_phone: str | None,
    dropoff_lat: float | None,
    dropoff_lng: float | None,
    priority: str | None,
) -> dict[str, Any]:
    assert_production_safe(order_id=order_id)
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Placeholder orders cannot be updated"
        )
    return ui_db_service.update_order(
        auth,
        db,
        order_id,
        customer_phone,
        dropoff_lat,
        dropoff_lng,
        priority,
    )


def submit_mission(
    auth: AuthContext,
    db: Session,
    order_id: str,
    publish: Callable[[dict[str, str]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    assert_production_safe(order_id=order_id)
    return ui_db_service.submit_mission(auth, db, order_id, publish=publish)


def run_auto_dispatch(
    auth: AuthContext,
    db: Session,
    max_assignments: int | None = None,
) -> dict[str, int | list[dict[str, str]]]:
    assert_production_safe()
    drones = [
        drone_id
        for drone_id, info in ui_store_service.store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]

    mode = _mode()
    if mode == "store":
        return ui_store_service.run_auto_dispatch(drones, max_assignments=max_assignments)

    result = ui_db_service.run_auto_dispatch(auth, db, drones, max_assignments=max_assignments)
    if mode != "hybrid":
        return result

    if max_assignments is None:
        # Preserve legacy placeholder behavior when the caller did not provide
        # an explicit assignment cap.
        if int(result["assigned"]) == 0:
            store_result = ui_store_service.run_auto_dispatch(
                drones,
                max_assignments=max_assignments,
            )
            remaining_capacity = None
            if max_assignments is not None:
                remaining_capacity = max(max_assignments - len(result["assignments"]), 0)
            store_assignments = store_result["assignments"]
            if remaining_capacity is not None:
                store_assignments = store_assignments[:remaining_capacity]
            combined = [*result["assignments"], *store_assignments]
            return {"assigned": len(combined), "assignments": combined}
        return result

    remaining_capacity = max(max_assignments - len(result["assignments"]), 0)
    if remaining_capacity == 0:
        return result

    store_result = ui_store_service.run_auto_dispatch(
        drones,
        max_assignments=remaining_capacity,
    )
    combined = [*result["assignments"], *store_result["assignments"]]
    return {"assigned": len(combined), "assignments": combined}


def list_jobs(
    auth: AuthContext,
    db: Session,
    active_only: bool,
    page: int,
    page_size: int,
    order_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    return ui_db_service.list_jobs(auth, db, active_only, page, page_size, order_id)


def get_job(auth: AuthContext, db: Session, job_id: str) -> dict[str, Any]:
    return ui_db_service.get_job(auth, db, job_id)


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    assert_production_safe(order_id=public_tracking_id)
    mode = _mode()
    if mode in {"store", "hybrid"}:
        try:
            return ui_store_service.tracking_view(public_tracking_id)
        except Exception:
            if mode == "store":
                raise
    return ui_db_service.tracking_view(db, public_tracking_id)


def build_public_tracking_etag(payload: dict[str, Any]) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = sha256(canonical_payload.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def build_public_tracking_payload(db: Session, public_tracking_id: str) -> dict[str, Any]:
    order = tracking_view(db, public_tracking_id)
    order_id = order.get("id") or order["order_id"]
    pod = get_pod(db, order_id)

    payload: dict[str, Any] = {
        "order_id": order_id,
        "public_tracking_id": order["public_tracking_id"],
        "status": order["status"],
        "milestones": order.get("milestones"),
    }
    if pod is not None:
        payload["pod_summary"] = {
            "method": pod.method.value,
            "created_at": pod.created_at,
        }

    return payload


def create_pod(
    auth: AuthContext,
    db: Session,
    order_id: str,
    method: str,
    otp_code: str | None,
    operator_name: str | None,
    photo_url: str | None,
) -> dict[str, Any]:
    return ui_db_service.create_pod(auth, db, order_id, method, otp_code, operator_name, photo_url)


def get_pod(db: Session, order_id: str):
    return ui_db_service.get_pod(db, order_id)


def _assert_drone_assignable(drone_id: str) -> None:
    drone = ui_store_service.store.drones.get(drone_id)
    if drone is None:
        return

    if not bool(drone.get("available", False)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone unavailable")

    if int(drone.get("battery", 0)) <= 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drone battery too low",
        )
