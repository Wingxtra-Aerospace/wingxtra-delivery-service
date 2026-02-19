import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.gcs_bridge_client import MissionPublisherProtocol
from app.models.delivery_job import DeliveryJob, DeliveryJobStatus
from app.models.order import Order, OrderStatus
from app.services.orders_service import get_order, transition_order_status


def _build_mission_intent(order: Order, job: DeliveryJob) -> dict:
    if not job.assigned_drone_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order has no assigned drone",
        )

    intent_id = f"mi_{uuid.uuid4().hex}"
    return {
        "intent_id": intent_id,
        "order_id": str(order.id),
        "drone_id": job.assigned_drone_id,
        "pickup": {"lat": order.pickup_lat, "lng": order.pickup_lng, "alt_m": 20},
        "dropoff": {
            "lat": order.dropoff_lat,
            "lng": order.dropoff_lng,
            "alt_m": 20,
            "delivery_alt_m": 8,
        },
        "actions": ["TAKEOFF", "CRUISE", "DESCEND", "DROP_OR_WINCH", "ASCEND", "RTL"],
        "constraints": {"battery_min_pct": 30, "service_area_id": "default"},
        "safety": {
            "abort_rtl_on_fail": True,
            "loiter_timeout_s": 60,
            "lost_link_behavior": "RTL",
        },
        "metadata": {
            "payload_type": order.payload_type,
            "payload_weight_kg": order.payload_weight_kg,
            "priority": order.priority.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _get_active_job(db: Session, order_id: uuid.UUID) -> DeliveryJob:
    job = db.scalar(
        select(DeliveryJob)
        .where(DeliveryJob.order_id == order_id, DeliveryJob.status == DeliveryJobStatus.ACTIVE)
        .order_by(DeliveryJob.created_at.desc())
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active delivery job found for order",
        )
    return job


def submit_mission_intent(
    db: Session,
    publisher: MissionPublisherProtocol,
    order_id: uuid.UUID,
) -> tuple[Order, DeliveryJob, dict]:
    order = get_order(db, order_id)
    if order.status != OrderStatus.ASSIGNED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mission intent can only be submitted from {OrderStatus.ASSIGNED.value}",
        )

    job = _get_active_job(db, order_id)
    intent = _build_mission_intent(order, job)

    publisher.publish_mission_intent(intent)

    job.mission_intent_id = intent["intent_id"]
    transition_order_status(
        db,
        order,
        OrderStatus.MISSION_SUBMITTED,
        "Mission intent submitted",
        payload={"mission_intent_id": intent["intent_id"]},
    )

    db.commit()
    db.refresh(order)
    db.refresh(job)
    return order, job, intent
