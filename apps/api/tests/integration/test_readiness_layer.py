from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy import select

from app.auth.dependencies import reset_rate_limits
from app.integrations.gcs_bridge_client import get_gcs_bridge_client
from app.models.delivery_event import DeliveryEvent, DeliveryEventType
from app.models.delivery_job import DeliveryJob
from app.models.order import Order, OrderStatus
from app.services.store import store


class RecordingPublisher:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish_mission_intent(self, mission_intent: dict) -> None:
        self.published.append(mission_intent)


class FailingPublisher:
    def publish_mission_intent(self, mission_intent: dict) -> None:
        raise RuntimeError(f"gcs publish failure for {mission_intent['order_id']}")


def _order_payload(suffix: str) -> dict:
    return {
        "customer_name": f"Readiness {suffix}",
        "customer_phone": "+123456789",
        "pickup_lat": 6.5,
        "pickup_lng": 3.4,
        "dropoff_lat": 6.6,
        "dropoff_lng": 3.5,
        "dropoff_accuracy_m": 8,
        "payload_weight_kg": 2.2,
        "payload_type": "parcel",
        "priority": "NORMAL",
    }


def _create_order(client, suffix: str) -> dict:
    response = client.post("/api/v1/orders", json=_order_payload(suffix))
    assert response.status_code == 201
    return response.json()


def test_readiness_happy_path_e2e(client, db_session):
    reset_rate_limits()
    store.drones.clear()
    store.drones.update({"DR-101": {"available": True, "battery": 96}})

    publisher = RecordingPublisher()
    client.app.dependency_overrides[get_gcs_bridge_client] = lambda: publisher

    order = _create_order(client, "happy-path")

    assign = client.post(f"/api/v1/orders/{order['id']}/assign", json={"drone_id": "DR-101"})
    assert assign.status_code == 200

    submit = client.post(f"/api/v1/orders/{order['id']}/submit-mission-intent")
    assert submit.status_code == 200
    assert submit.json()["status"] == "MISSION_SUBMITTED"
    assert len(publisher.published) == 1

    order_uuid = UUID(order["id"])
    job = db_session.scalar(
        select(DeliveryJob)
        .where(DeliveryJob.order_id == order_uuid)
        .order_by(DeliveryJob.created_at.desc())
    )
    assert job is not None

    db_order = db_session.get(Order, order_uuid)
    assert db_order is not None
    db_order.status = OrderStatus.DELIVERED
    db_session.add_all(
        [
            DeliveryEvent(
                order_id=order_uuid,
                job_id=job.id,
                type=DeliveryEventType.LAUNCHED,
                message="Drone launched",
                payload={"phase": "launch"},
            ),
            DeliveryEvent(
                order_id=order_uuid,
                job_id=job.id,
                type=DeliveryEventType.ENROUTE,
                message="Drone enroute",
                payload={"phase": "cruise"},
            ),
            DeliveryEvent(
                order_id=order_uuid,
                job_id=job.id,
                type=DeliveryEventType.DELIVERED,
                message="Package delivered",
                payload={"phase": "dropoff"},
            ),
        ]
    )
    db_session.commit()

    pod = client.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={"method": "PHOTO", "photo_url": "https://cdn.example/pod-readiness.jpg"},
    )
    assert pod.status_code == 200

    timeline = client.get(f"/api/v1/orders/{order['id']}/events")
    assert timeline.status_code == 200
    assert [event["type"] for event in timeline.json()["items"]] == [
        "CREATED",
        "VALIDATED",
        "QUEUED",
        "ASSIGNED",
        "MISSION_SUBMITTED",
        "LAUNCHED",
        "ENROUTE",
        "DELIVERED",
    ]

    tracking = client.get(f"/api/v1/tracking/{order['public_tracking_id']}")
    assert tracking.status_code == 200
    assert tracking.json()["status"] == "DELIVERED"
    assert tracking.json()["pod_summary"]["method"] == "PHOTO"


def test_readiness_failure_paths(client, db_session):
    reset_rate_limits()
    store.drones.clear()
    store.drones.update(
        {
            "DR-201": {"available": False, "battery": 95},
            "DR-202": {"available": True, "battery": 15},
            "DR-203": {"available": True, "battery": 90},
        }
    )

    unavailable = _create_order(client, "drone-unavailable")
    unavailable_assign = client.post(
        f"/api/v1/orders/{unavailable['id']}/assign", json={"drone_id": "DR-201"}
    )
    assert unavailable_assign.status_code == 400
    assert unavailable_assign.json()["detail"] == "Drone unavailable"

    low_battery = _create_order(client, "low-battery")
    low_battery_assign = client.post(
        f"/api/v1/orders/{low_battery['id']}/assign", json={"drone_id": "DR-202"}
    )
    assert low_battery_assign.status_code == 400
    assert low_battery_assign.json()["detail"] == "Drone battery too low"

    duplicate = _create_order(client, "duplicate-submit")
    assign = client.post(f"/api/v1/orders/{duplicate['id']}/assign", json={"drone_id": "DR-203"})
    assert assign.status_code == 200

    publisher = RecordingPublisher()
    client.app.dependency_overrides[get_gcs_bridge_client] = lambda: publisher

    first = client.post(
        f"/api/v1/orders/{duplicate['id']}/submit-mission-intent",
        headers={"Idempotency-Key": "dup-readiness-key"},
    )
    second = client.post(
        f"/api/v1/orders/{duplicate['id']}/submit-mission-intent",
        headers={"Idempotency-Key": "dup-readiness-key"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(publisher.published) == 1

    failing = _create_order(client, "publish-failure")
    assign_fail = client.post(f"/api/v1/orders/{failing['id']}/assign", json={"drone_id": "DR-203"})
    assert assign_fail.status_code == 200

    client.app.dependency_overrides[get_gcs_bridge_client] = lambda: FailingPublisher()

    failed_submit = client.post(f"/api/v1/orders/{failing['id']}/submit-mission-intent")
    assert failed_submit.status_code == 503
    assert failed_submit.json()["detail"] == {
        "service": "gcs_bridge",
        "code": "UNAVAILABLE",
        "message": "Mission publish failed",
    }

    db_order = db_session.get(Order, UUID(failing["id"]))
    assert db_order is not None
    assert db_order.status == OrderStatus.ASSIGNED

    events = client.get(f"/api/v1/orders/{failing['id']}/events")
    assert events.status_code == 200
    assert all(item["type"] != "MISSION_SUBMITTED" for item in events.json()["items"])


def test_readiness_load_smoke_hot_endpoints(client):
    reset_rate_limits()
    store.drones.clear()
    store.drones.update(
        {f"DR-{idx:03d}": {"available": True, "battery": 95} for idx in range(1, 31)}
    )

    start_create = time.perf_counter()
    created_orders = []
    for idx in range(1, 31):
        created_orders.append(_create_order(client, f"load-{idx}"))
    create_elapsed = time.perf_counter() - start_create

    assert create_elapsed < 5

    tracked_id = created_orders[0]["public_tracking_id"]
    start_tracking = time.perf_counter()
    for _ in range(10):
        tracking = client.get(f"/api/v1/tracking/{tracked_id}")
        assert tracking.status_code == 200
    tracking_elapsed = time.perf_counter() - start_tracking
    assert tracking_elapsed < 2

    start_dispatch = time.perf_counter()
    dispatch = client.post("/api/v1/dispatch/run")
    dispatch_elapsed = time.perf_counter() - start_dispatch

    assert dispatch.status_code == 200
    assert dispatch.json()["assigned"] == 30
    assert dispatch_elapsed < 5
