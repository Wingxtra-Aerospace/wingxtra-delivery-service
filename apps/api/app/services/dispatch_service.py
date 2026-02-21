import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.fleet_api_client import FleetApiClientProtocol, FleetDroneTelemetry
from app.models.delivery_job import DeliveryJob, DeliveryJobStatus
from app.models.order import Order, OrderStatus
from app.services.orders_service import get_order, transition_order_status

_MIN_BATTERY_FOR_ASSIGNMENT = 30.0


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_rad, lng1_rad, lat2_rad, lng2_rad = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _score_drone(order: Order, drone: FleetDroneTelemetry) -> float:
    distance = _distance_km(order.pickup_lat, order.pickup_lng, drone.lat, drone.lng)
    battery_bonus = drone.battery / 100
    return distance - battery_bonus


def _prepare_order_for_assignment(db: Session, order: Order) -> None:
    if order.status == OrderStatus.CREATED:
        transition_order_status(db, order, OrderStatus.VALIDATED, "Order validated")
        transition_order_status(db, order, OrderStatus.QUEUED, "Order queued for dispatch")
    elif order.status == OrderStatus.VALIDATED:
        transition_order_status(db, order, OrderStatus.QUEUED, "Order queued for dispatch")


def _assign_order_to_drone(db: Session, order: Order, drone_id: str, reason: str) -> DeliveryJob:
    transition_order_status(
        db,
        order,
        OrderStatus.ASSIGNED,
        "Order assigned",
        payload={"drone_id": drone_id, "reason": reason},
    )
    job = DeliveryJob(
        order_id=order.id,
        assigned_drone_id=drone_id,
        status=DeliveryJobStatus.ACTIVE,
    )
    db.add(job)
    return job


def run_auto_dispatch(
    db: Session,
    fleet_client: FleetApiClientProtocol,
    max_assignments: int = 1,
) -> list[tuple[Order, DeliveryJob]]:
    dispatchable_statuses = [OrderStatus.CREATED, OrderStatus.VALIDATED, OrderStatus.QUEUED]
    orders = list(
        db.scalars(
            select(Order)
            .where(Order.status.in_(dispatchable_statuses))
            .order_by(Order.created_at.asc())
        )
    )

    drones = [
        drone
        for drone in fleet_client.get_latest_telemetry()
        if drone.is_available and drone.battery >= _MIN_BATTERY_FOR_ASSIGNMENT
    ]

    assignments: list[tuple[Order, DeliveryJob]] = []
    used_drones: set[str] = set()

    for order in orders:
        if len(assignments) >= max_assignments:
            break

        _prepare_order_for_assignment(db, order)
        if order.status != OrderStatus.QUEUED:
            continue

        available = [drone for drone in drones if drone.drone_id not in used_drones]
        if not available:
            continue

        selected = min(available, key=lambda drone: _score_drone(order, drone))
        job = _assign_order_to_drone(db, order, selected.drone_id, reason="auto")
        assignments.append((order, job))
        used_drones.add(selected.drone_id)

    db.commit()
    for order, job in assignments:
        db.refresh(order)
        db.refresh(job)
    return assignments


def manual_assign_order(
    db: Session,
    fleet_client: FleetApiClientProtocol,
    order_id: uuid.UUID,
    drone_id: str,
) -> DeliveryJob:
    order = get_order(db, order_id)
    _prepare_order_for_assignment(db, order)

    if order.status != OrderStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order cannot be assigned from status {order.status.value}",
        )

    drone = next(
        (d for d in fleet_client.get_latest_telemetry() if d.drone_id == drone_id),
        None,
    )
    if not drone or not drone.is_available or drone.battery < _MIN_BATTERY_FOR_ASSIGNMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drone not assignable")

    job = _assign_order_to_drone(db, order, drone_id, reason="manual")
    db.commit()
    db.refresh(job)
    return job
