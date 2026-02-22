import time
from uuid import UUID

from app.auth.dependencies import reset_rate_limits
from app.config import settings
from app.integrations.fleet_api_client import FleetDroneTelemetry, get_fleet_api_client
from app.integrations.gcs_bridge_client import get_gcs_bridge_client
from app.main import app
from app.models.order import Order, OrderStatus


class FakeFleetApiClient:
    def __init__(self, drones: list[FleetDroneTelemetry]) -> None:
        self._drones = drones

    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]:
        return self._drones


def _create_order(client):
    payload = {
        "customer_name": "Jane Doe",
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
    return client.post("/api/v1/orders", json=payload)


def _set_fleet_override(drones: list[FleetDroneTelemetry]) -> None:
    app.dependency_overrides[get_fleet_api_client] = lambda: FakeFleetApiClient(drones)


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish_mission_intent(self, mission_intent: dict) -> None:
        self.published.append(mission_intent)


def test_create_get_list_cancel_tracking_and_events(client):
    create_response = _create_order(client)
    assert create_response.status_code == 201
    created = create_response.json()
    UUID(created["id"])

    get_response = client.get(f"/api/v1/orders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    list_response = client.get("/api/v1/orders")
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    tracking_response = client.get(f"/api/v1/tracking/{created['public_tracking_id']}")
    assert tracking_response.status_code == 200
    assert tracking_response.json()["order_id"] == created["id"]
    assert tracking_response.json()["milestones"] == ["CREATED"]

    events_before_cancel = client.get(f"/api/v1/orders/{created['id']}/events")
    assert events_before_cancel.status_code == 200
    assert [event["type"] for event in events_before_cancel.json()["items"]] == ["CREATED"]

    cancel_response = client.post(f"/api/v1/orders/{created['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELED"

    events_after_cancel = client.get(f"/api/v1/orders/{created['id']}/events")
    assert events_after_cancel.status_code == 200
    assert [event["type"] for event in events_after_cancel.json()["items"]] == [
        "CREATED",
        "CANCELED",
    ]


def test_auto_dispatch_and_manual_assign(client):
    _set_fleet_override(
        [
            FleetDroneTelemetry(
                drone_id="DRONE-1", lat=6.45, lng=3.39, battery=95, is_available=True
            ),
            FleetDroneTelemetry(
                drone_id="DRONE-2", lat=8.0, lng=5.0, battery=60, is_available=True
            ),
        ]
    )

    _create_order(client)
    _create_order(client)

    auto_response = client.post("/api/v1/dispatch/run")
    assert auto_response.status_code == 200
    assignments = auto_response.json()["assignments"]
    assert len(assignments) == 2

    create_response = _create_order(client)
    order3 = create_response.json()
    manual_response = client.post(
        f"/api/v1/orders/{order3['id']}/assign",
        json={"drone_id": "DRONE-1"},
    )
    assert manual_response.status_code == 200
    assert manual_response.json()["order_id"] == order3["id"]

    events = client.get(f"/api/v1/orders/{order3['id']}/events").json()["items"]
    assert [event["type"] for event in events] == ["CREATED", "VALIDATED", "QUEUED", "ASSIGNED"]


def test_auto_dispatch_respects_max_assignments(client):
    _set_fleet_override(
        [
            FleetDroneTelemetry(
                drone_id="DRONE-1", lat=6.45, lng=3.39, battery=95, is_available=True
            ),
            FleetDroneTelemetry(
                drone_id="DRONE-2", lat=6.46, lng=3.40, battery=94, is_available=True
            ),
        ]
    )

    _create_order(client)
    _create_order(client)

    auto_response = client.post("/api/v1/dispatch/run", json={"max_assignments": 1})
    assert auto_response.status_code == 200
    assignments = auto_response.json()["assignments"]
    assert auto_response.json()["assigned"] == 1
    assert len(assignments) == 1


def test_dispatch_run_request_validation_bounds(client):
    too_low = client.post("/api/v1/dispatch/run", json={"max_assignments": 0})
    too_high = client.post("/api/v1/dispatch/run", json={"max_assignments": 101})

    assert too_low.status_code == 422
    assert too_high.status_code == 422


def test_dispatch_run_accepts_empty_body(client):
    response = client.post("/api/v1/dispatch/run", json={})
    assert response.status_code == 200
    assert "assigned" in response.json()


def test_manual_assign_rejects_invalid_drone(client):
    _set_fleet_override(
        [
            FleetDroneTelemetry(
                drone_id="DRONE-LOW", lat=6.45, lng=3.39, battery=10, is_available=True
            ),
        ]
    )

    order = _create_order(client).json()
    response = client.post(f"/api/v1/orders/{order['id']}/assign", json={"drone_id": "DRONE-LOW"})
    assert response.status_code == 400


def test_submit_mission_intent_for_assigned_order(client):
    _set_fleet_override(
        [FleetDroneTelemetry(drone_id="DRONE-1", lat=6.45, lng=3.39, battery=95, is_available=True)]
    )
    publisher = FakePublisher()
    app.dependency_overrides[get_gcs_bridge_client] = lambda: publisher

    order = _create_order(client).json()
    assign = client.post(f"/api/v1/orders/{order['id']}/assign", json={"drone_id": "DRONE-1"})
    assert assign.status_code == 200

    submit = client.post(f"/api/v1/orders/{order['id']}/submit-mission-intent")
    assert submit.status_code == 200
    payload = submit.json()
    assert payload["order_id"] == order["id"]
    assert payload["status"] == "MISSION_SUBMITTED"
    assert payload["mission_intent_id"].startswith("mi_")
    assert len(publisher.published) == 1


def test_submit_mission_intent_rejected_when_not_assigned(client):
    order = _create_order(client).json()
    response = client.post(f"/api/v1/orders/{order['id']}/submit-mission-intent")
    assert response.status_code == 409


def test_create_pod_and_tracking_summary(client, db_session):
    order = _create_order(client).json()

    db_order = db_session.get(Order, UUID(order["id"]))
    db_order.status = OrderStatus.DELIVERED
    db_session.commit()

    pod_response = client.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={
            "method": "PHOTO",
            "photo_url": "https://cdn.example/pod.jpg",
            "metadata": {"camera": "ops-device"},
        },
    )
    assert pod_response.status_code == 200
    assert pod_response.json()["method"] == "PHOTO"

    tracking = client.get(f"/api/v1/tracking/{order['public_tracking_id']}")
    assert tracking.status_code == 200
    assert tracking.json()["pod_summary"]["method"] == "PHOTO"


def test_create_pod_rejected_for_non_delivered_order(client):
    order = _create_order(client).json()
    response = client.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={"method": "OPERATOR_CONFIRM", "confirmed_by": "ops"},
    )
    assert response.status_code == 409


def test_cancel_rejected_for_terminal_state(client, db_session):
    create_response = _create_order(client)
    created = create_response.json()

    order = db_session.get(Order, UUID(created["id"]))
    order.status = OrderStatus.DELIVERED
    db_session.commit()

    response = client.post(f"/api/v1/orders/{created['id']}/cancel")
    assert response.status_code == 409


def test_get_order_not_found(client):
    response = client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_create_order_validation_error(client):
    response = client.post(
        "/api/v1/orders",
        json={
            "pickup_lat": 100,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "payload_weight_kg": -1,
            "payload_type": "",
        },
    )
    assert response.status_code == 422


def test_update_order_patch_updates_allowed_fields(client, db_session):
    order = _create_order(client).json()

    response = client.patch(
        f"/api/v1/orders/{order['id']}",
        json={
            "customer_phone": "+1987654321",
            "dropoff_lat": 6.7,
            "dropoff_lng": 3.6,
            "priority": "URGENT",
        },
    )
    assert response.status_code == 200
    assert response.json()["id"] == order["id"]

    db_order = db_session.get(Order, UUID(order["id"]))
    assert db_order.customer_phone == "+1987654321"
    assert db_order.dropoff_lat == 6.7
    assert db_order.dropoff_lng == 3.6
    assert db_order.priority.value == "URGENT"


def test_update_order_patch_rejects_partial_dropoff_coordinates(client):
    order = _create_order(client).json()

    response = client.patch(
        f"/api/v1/orders/{order['id']}",
        json={"dropoff_lat": 6.8},
    )
    assert response.status_code == 400
    assert "must be provided together" in response.json()["detail"]


def test_submit_placeholder_mission_intent_publishes(client):
    publisher = FakePublisher()
    app.dependency_overrides[get_gcs_bridge_client] = lambda: publisher

    response = client.post("/api/v1/orders/ord-1/submit-mission-intent")
    assert response.status_code == 200
    assert len(publisher.published) == 1
    assert publisher.published[0]["order_id"] == "ord-1"
    assert publisher.published[0]["mission_intent_id"] == "mi_ord-1"


def test_public_tracking_placeholder_without_pod_still_returns_200(client):
    response = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "ord-1"
    assert body["public_tracking_id"] == "11111111-1111-4111-8111-111111111111"


def test_create_order_rejects_empty_idempotency_key(client):
    response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "   "},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key must not be empty"


def test_create_order_rejects_oversized_idempotency_key(client):
    response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "x" * 256},
    )
    assert response.status_code == 400
    assert "Idempotency-Key exceeds max length" in response.json()["detail"]


def test_assign_rejects_empty_idempotency_key(client):
    _set_fleet_override(
        [
            FleetDroneTelemetry(
                drone_id="DRONE-1", lat=6.45, lng=3.39, battery=95, is_available=True
            ),
        ]
    )
    order = _create_order(client).json()

    response = client.post(
        f"/api/v1/orders/{order['id']}/assign",
        json={"drone_id": "DRONE-1"},
        headers={"Idempotency-Key": "   "},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key must not be empty"


def test_submit_mission_rejects_oversized_idempotency_key(client):
    _set_fleet_override(
        [
            FleetDroneTelemetry(
                drone_id="DRONE-1", lat=6.45, lng=3.39, battery=95, is_available=True
            ),
        ]
    )
    order = _create_order(client).json()

    assign = client.post(f"/api/v1/orders/{order['id']}/assign", json={"drone_id": "DRONE-1"})
    assert assign.status_code == 200

    response = client.post(
        f"/api/v1/orders/{order['id']}/submit-mission-intent",
        headers={"Idempotency-Key": "x" * 256},
    )
    assert response.status_code == 400
    assert "Idempotency-Key exceeds max length" in response.json()["detail"]


def test_create_pod_rejects_empty_idempotency_key(client, db_session):
    order = _create_order(client).json()

    db_order = db_session.get(Order, UUID(order["id"]))
    db_order.status = OrderStatus.DELIVERED
    db_session.commit()

    response = client.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={
            "method": "PHOTO",
            "photo_url": "https://cdn.example/pod.jpg",
            "metadata": {"camera": "ops-device"},
        },
        headers={"Idempotency-Key": "   "},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Idempotency-Key must not be empty"


def test_cancel_rejects_oversized_idempotency_key(client):
    order = _create_order(client).json()

    response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers={"Idempotency-Key": "x" * 256},
    )
    assert response.status_code == 400
    assert "Idempotency-Key exceeds max length" in response.json()["detail"]


def test_metrics_exposes_idempotency_counters_after_requests(client):
    before = client.get("/metrics")
    assert before.status_code == 200
    before_counters = before.json().get("counters", {})

    create_response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "idem-metrics-order-create-1"},
    )
    assert create_response.status_code == 201

    replay_response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "idem-metrics-order-create-1"},
    )
    assert replay_response.status_code == 201

    invalid_header_response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "   "},
    )
    assert invalid_header_response.status_code == 400

    after = client.get("/metrics")
    assert after.status_code == 200
    after_counters = after.json().get("counters", {})

    def delta(name: str) -> int:
        return int(after_counters.get(name, 0)) - int(before_counters.get(name, 0))

    assert delta("idempotency_store_total") >= 1
    assert delta("idempotency_replay_total") >= 1
    assert delta("idempotency_invalid_key_total") >= 1


def test_metrics_exposes_rate_limit_counters_when_limited(client):
    before = client.get("/metrics")
    assert before.status_code == 200
    before_counters = before.json().get("counters", {})

    original_requests = settings.order_create_rate_limit_requests
    original_window = settings.order_create_rate_limit_window_s
    settings.order_create_rate_limit_requests = 1
    settings.order_create_rate_limit_window_s = 60
    reset_rate_limits()

    try:
        first = _create_order(client)
        assert first.status_code == 201
        assert first.headers["X-RateLimit-Limit"] == "1"

        second = _create_order(client)
        assert second.status_code == 429
        assert second.json()["detail"] == "Order creation rate limit exceeded"
        assert second.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in second.headers
        assert int(second.headers["X-RateLimit-Reset"]) >= int(time.time())
    finally:
        settings.order_create_rate_limit_requests = original_requests
        settings.order_create_rate_limit_window_s = original_window
        reset_rate_limits()

    after = client.get("/metrics")
    assert after.status_code == 200
    after_counters = after.json().get("counters", {})

    def delta(name: str) -> int:
        return int(after_counters.get(name, 0)) - int(before_counters.get(name, 0))

    assert delta("rate_limit_checked_total") >= 2
    assert delta("rate_limit_rejected_total") >= 1


def test_public_tracking_rate_limit_increments_rate_limit_metrics(client):
    before = client.get("/metrics")
    assert before.status_code == 200
    before_counters = before.json().get("counters", {})

    original_requests = settings.public_tracking_rate_limit_requests
    original_window = settings.public_tracking_rate_limit_window_s
    settings.public_tracking_rate_limit_requests = 1
    settings.public_tracking_rate_limit_window_s = 60
    reset_rate_limits()

    try:
        first = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Limit"] == "1"

        second = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        assert second.status_code == 429
        assert second.json()["detail"] == "Public tracking rate limit exceeded"
        assert second.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in second.headers
        assert int(second.headers["X-RateLimit-Reset"]) >= int(time.time())
    finally:
        settings.public_tracking_rate_limit_requests = original_requests
        settings.public_tracking_rate_limit_window_s = original_window
        reset_rate_limits()

    after = client.get("/metrics")
    assert after.status_code == 200
    after_counters = after.json().get("counters", {})

    def delta(name: str) -> int:
        return int(after_counters.get(name, 0)) - int(before_counters.get(name, 0))

    assert delta("rate_limit_checked_total") >= 2
    assert delta("rate_limit_rejected_total") >= 1


def test_metrics_exposes_idempotency_conflict_counter_after_conflict(client):
    before = client.get("/metrics")
    assert before.status_code == 200
    before_counters = before.json().get("counters", {})

    first = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 2.2,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "idem-conflict-metrics-1"},
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Jane Doe",
            "customer_phone": "+123456789",
            "pickup_lat": 6.5,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "dropoff_accuracy_m": 8,
            "payload_weight_kg": 3.4,
            "payload_type": "parcel",
            "priority": "NORMAL",
        },
        headers={"Idempotency-Key": "idem-conflict-metrics-1"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Idempotency key reused with different payload"

    after = client.get("/metrics")
    assert after.status_code == 200
    after_counters = after.json().get("counters", {})

    delta = int(after_counters.get("idempotency_conflict_total", 0)) - int(
        before_counters.get("idempotency_conflict_total", 0)
    )
    assert delta >= 1
