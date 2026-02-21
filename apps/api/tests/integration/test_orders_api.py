from uuid import UUID

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
