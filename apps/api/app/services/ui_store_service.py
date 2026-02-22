from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status

from app.auth.dependencies import AuthContext
from app.models.domain import Event as MemEvent
from app.models.domain import Job as MemJob
from app.models.domain import Order as MemOrder
from app.models.domain import new_id as mem_new_id
from app.models.domain import now_utc as mem_now_utc
from app.services.store import store

_PLACEHOLDER_TRACKING_ID_ORD1 = "11111111-1111-4111-8111-111111111111"


def seed_placeholders_in_store_if_needed() -> None:
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


def _order_to_dict(order: MemOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "public_tracking_id": order.public_tracking_id,
        "merchant_id": order.merchant_id,
        "customer_name": order.customer_name,
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def create_order(auth: AuthContext, customer_name: str | None = None, **_: Any) -> dict[str, Any]:
    if auth.role not in {"MERCHANT", "OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    seed_placeholders_in_store_if_needed()
    order_obj = MemOrder(
        id=mem_new_id("ord-"),
        public_tracking_id=uuid.uuid4().hex,
        merchant_id=auth.user_id if auth.role == "MERCHANT" else None,
        customer_name=customer_name,
        status="CREATED",
        created_at=mem_now_utc(),
        updated_at=mem_now_utc(),
    )
    store.orders[order_obj.id] = order_obj
    store.events[order_obj.id].append(
        MemEvent(
            id=mem_new_id("evt-"),
            order_id=order_obj.id,
            type="CREATED",
            message="Order created",
            created_at=mem_now_utc(),
        )
    )
    return _order_to_dict(order_obj)


def manual_assign(auth: AuthContext, order_id: str, drone_id: str) -> dict[str, Any]:
    if auth.role not in {"OPS", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    seed_placeholders_in_store_if_needed()
    mem = store.orders.get(order_id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if mem.status in {"DELIVERED", "FAILED", "ABORTED", "CANCELED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Order cannot be reassigned"
        )
    if mem.status == "CREATED":
        mem.status = "VALIDATED"
        store.events[order_id].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id=order_id,
                type="VALIDATED",
                message="Order validated",
                created_at=mem_now_utc(),
            )
        )
        mem.status = "QUEUED"
        store.events[order_id].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id=order_id,
                type="QUEUED",
                message="Order queued for dispatch",
                created_at=mem_now_utc(),
            )
        )
    elif mem.status == "VALIDATED":
        mem.status = "QUEUED"
        store.events[order_id].append(
            MemEvent(
                id=mem_new_id("evt-"),
                order_id=order_id,
                type="QUEUED",
                message="Order queued for dispatch",
                created_at=mem_now_utc(),
            )
        )
    mem.status = "ASSIGNED"
    mem.updated_at = mem_now_utc()
    store.events[order_id].append(
        MemEvent(
            id=mem_new_id("evt-"),
            order_id=order_id,
            type="ASSIGNED",
            message=f"Order assigned to {drone_id}",
            created_at=mem_now_utc(),
        )
    )
    store.jobs.append(
        MemJob(
            id=mem_new_id("job-"),
            order_id=order_id,
            assigned_drone_id=drone_id,
            status="ACTIVE",
            created_at=mem_now_utc(),
        )
    )
    return _order_to_dict(mem)


def get_order(auth: AuthContext, order_id: str) -> dict[str, Any]:
    seed_placeholders_in_store_if_needed()
    mem = store.orders.get(order_id)
    if mem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if auth.role not in {"OPS", "ADMIN"} and not (
        auth.role == "MERCHANT" and mem.merchant_id == auth.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this order"
        )
    return _order_to_dict(mem)


def list_events(auth: AuthContext, order_id: str) -> list[dict[str, Any]]:
    _ = get_order(auth, order_id)
    return [
        {
            "id": ev.id,
            "order_id": ev.order_id,
            "type": ev.type,
            "message": ev.message,
            "created_at": ev.created_at,
        }
        for ev in store.events.get(order_id, [])
    ]


def tracking_view(public_tracking_id: str) -> dict[str, Any]:
    seed_placeholders_in_store_if_needed()
    for order in store.orders.values():
        if order.public_tracking_id == public_tracking_id:
            return {
                "id": order.id,
                "order_id": order.id,
                "public_tracking_id": order.public_tracking_id,
                "status": order.status,
            }
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracking record not found")


def run_auto_dispatch(
    available_drones: list[str],
    max_assignments: int | None = None,
) -> dict[str, int | list[dict[str, str]]]:
    seed_placeholders_in_store_if_needed()
    assignments: list[dict[str, str]] = []
    ord2 = store.orders.get("ord-2")
    can_assign = max_assignments is None or max_assignments > 0
    if ord2 is not None and ord2.status == "QUEUED" and available_drones and can_assign:
        drone_id = available_drones[0]
        manual_assign(AuthContext(user_id="ops-auto", role="OPS"), "ord-2", drone_id)
        assignments.append({"order_id": "ord-2", "status": "ASSIGNED"})
    return {"assigned": len(assignments), "assignments": assignments}
