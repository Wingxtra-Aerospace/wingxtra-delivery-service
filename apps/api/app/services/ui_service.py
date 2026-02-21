from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext
from app.config import settings
from app.services import ui_db_service, ui_store_service
from app.services.store import store


def _available_drones() -> list[str]:
    return [
        drone_id
        for drone_id, info in store.drones.items()
        if bool(info.get("available", False)) and int(info.get("battery", 0)) > 20
    ]


def _mode() -> str:
    return settings.ui_service_mode


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


def list_jobs(auth: AuthContext, db: Session, active_only: bool) -> list[dict[str, Any]]:
    return ui_db_service.list_jobs(auth, db, active_only)


def tracking_view(db: Session, public_tracking_id: str) -> dict[str, Any]:
    if _mode() in {"store", "hybrid"}:
        try:
            return ui_store_service.tracking_view(public_tracking_id)
        except HTTPException:
            if _mode() == "store":
                raise
    return ui_db_service.tracking_view(db, public_tracking_id)


def create_pod(auth: AuthContext, db: Session, order_id: str, method: str, otp_code: str | None, operator_name: str | None, photo_url: str | None) -> dict[str, Any]:
    return ui_db_service.create_pod(auth, db, order_id, method, otp_code, operator_name, photo_url)


def get_pod(db: Session, order_id: str):
    return ui_db_service.get_pod(db, order_id)
