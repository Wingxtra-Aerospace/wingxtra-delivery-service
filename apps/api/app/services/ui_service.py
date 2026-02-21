from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import settings
from app.services import ui_db_service, ui_store_service


def _mode() -> str:
    mode = settings.ui_service_mode.lower().strip()
    if mode in {"store", "db", "hybrid"}:
        return mode
    return "hybrid"


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

    if mode != "hybrid":
        return db_items, db_total

    store_items = [
        ui_store_service.get_order(auth, oid)
        for oid in sorted(ui_store_service.store.orders.keys())
        if not status_filter or ui_store_service.store.orders[oid].status == status_filter
    ]
    combined = [*store_items, *db_items]
    return combined[(page - 1) * page_size : page * page_size], len(combined)


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
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        return ui_store_service.get_order(auth, order_id)
    return ui_db_service.get_order(auth, db, order_id)


def list_events(auth: AuthContext, db: Session, order_id: str) -> list[dict[str, Any]]:
    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        return ui_store_service.list_events(auth, order_id)
    return ui_db_service.list_events(auth, db, order_id)


def cancel_order(auth: AuthContext, db: Session, order_id: str) -> dict[str, Any]:
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
    if isinstance(db, str):
        # Legacy call signature: manual_assign(auth, order_id, drone_id)
        return ui_store_service.manual_assign(auth, db, order_id)

    mode = _mode()
    if mode == "store" or (mode == "hybrid" and _is_placeholder_order_id(order_id)):
        if drone_id is None:
            raise ValueError("drone_id is required")
        return ui_store_service.manual_assign(auth, order_id, drone_id)

    if drone_id is None:
        raise ValueError("drone_id is required")
    return ui_db_service.manual_assign(auth, db, order_id, drone_id)


def submit_mission(
    auth: AuthContext, db: Session, order_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    return ui_db_service.submit_mission(auth, db, order_id)


def run_auto_dispatch(auth: AuthContext, db: Session) -> dict[str, int | list[dict[str, str]]]:
    drones = [
        drone_id
        for drone_id, info in ui_store_service.store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]

    mode = _mode()
    if mode == "store":
        return ui_store_service.run_auto_dispatch(drones)

    result = ui_db_service.run_auto_dispatch(auth, db, drones)
    if mode == "hybrid":
        store_result = ui_store_service.run_auto_dispatch(drones)
        combined = [*result["assignments"], *store_result["assignments"]]
        return {"assigned": len(combined), "assignments": combined}
    return result


def list_jobs(auth: AuthContext, db: Session, active_only: bool) -> list[dict[str, Any]]:
    return ui_db_service.list_jobs(auth, db, active_only)


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    mode = _mode()
    if mode in {"store", "hybrid"}:
        try:
            return ui_store_service.tracking_view(public_tracking_id)
        except Exception:
            if mode == "store":
                raise
    return ui_db_service.tracking_view(db, public_tracking_id)


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
