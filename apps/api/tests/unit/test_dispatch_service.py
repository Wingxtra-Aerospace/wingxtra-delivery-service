import pytest
from fastapi import HTTPException

from app.config import settings
from app.integrations.fleet_api_client import FleetDroneTelemetry, FleetServiceArea
from app.schemas.order import OrderCreate
from app.services.dispatch_service import manual_assign_order, run_auto_dispatch
from app.services.orders_service import create_order


class FakeFleetApiClient:
    def __init__(self, drones: list[FleetDroneTelemetry]) -> None:
        self._drones = drones

    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]:
        return self._drones


def _payload() -> OrderCreate:
    return OrderCreate(
        pickup_lat=1,
        pickup_lng=2,
        dropoff_lat=3,
        dropoff_lng=4,
        payload_weight_kg=1.5,
        payload_type="BOX",
    )


def test_auto_dispatch_assigns_best_available_drone(db_session):
    order = create_order(db_session, _payload())

    client = FakeFleetApiClient(
        [
            FleetDroneTelemetry(drone_id="far", lat=50, lng=50, battery=90, is_available=True),
            FleetDroneTelemetry(drone_id="near", lat=1.01, lng=2.01, battery=80, is_available=True),
        ]
    )

    assignments = run_auto_dispatch(db_session, client)

    assert len(assignments) == 1
    assigned_order, job = assignments[0]
    assert assigned_order.id == order.id
    assert job.assigned_drone_id == "near"


def test_manual_assign_creates_assignment_job(db_session):
    order = create_order(db_session, _payload())
    client = FakeFleetApiClient(
        [FleetDroneTelemetry(drone_id="D1", lat=1, lng=2, battery=95, is_available=True)]
    )

    job = manual_assign_order(db_session, client, order.id, "D1")

    assert job.assigned_drone_id == "D1"


def test_auto_dispatch_can_assign_multiple_orders_when_max_assignments_increased(db_session):
    first_order = create_order(db_session, _payload())
    second_order = create_order(db_session, _payload())

    client = FakeFleetApiClient(
        [
            FleetDroneTelemetry(drone_id="D1", lat=1, lng=2, battery=95, is_available=True),
            FleetDroneTelemetry(drone_id="D2", lat=1, lng=2.1, battery=90, is_available=True),
        ]
    )

    assignments = run_auto_dispatch(db_session, client, max_assignments=2)

    assert len(assignments) == 2
    assert {assignment[0].id for assignment in assignments} == {first_order.id, second_order.id}


def test_auto_dispatch_filters_incompatible_drones_before_scoring(db_session):
    order = create_order(db_session, _payload())
    client = FakeFleetApiClient(
        [
            FleetDroneTelemetry(drone_id="bad-weight", lat=1, lng=2, battery=95, max_payload_kg=1),
            FleetDroneTelemetry(
                drone_id="bad-type", lat=1, lng=2, battery=95, payload_type="MEDICAL"
            ),
            FleetDroneTelemetry(
                drone_id="bad-area",
                lat=1,
                lng=2,
                battery=95,
                service_area=FleetServiceArea(min_lat=10, max_lat=20, min_lng=10, max_lng=20),
            ),
            FleetDroneTelemetry(drone_id="good", lat=1.01, lng=2.01, battery=80, max_payload_kg=2),
        ]
    )

    assignments = run_auto_dispatch(db_session, client)

    assert len(assignments) == 1
    _, job = assignments[0]
    assert job.assigned_drone_id == "good"
    assert order.status.value == "ASSIGNED"


def test_manual_assign_rejects_incompatible_drone_with_clear_reason(db_session):
    order = create_order(db_session, _payload())
    client = FakeFleetApiClient(
        [FleetDroneTelemetry(drone_id="D1", lat=1, lng=2, battery=95, max_payload_kg=1)]
    )

    with pytest.raises(HTTPException) as exc:
        manual_assign_order(db_session, client, order.id, "D1")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Drone payload capacity exceeded"


def test_auto_dispatch_tie_break_prefers_higher_battery_when_scores_match(db_session):
    order = create_order(db_session, _payload())

    old_distance = settings.dispatch_score_distance_weight
    old_battery = settings.dispatch_score_battery_weight
    settings.dispatch_score_distance_weight = 0
    settings.dispatch_score_battery_weight = 0
    try:
        client = FakeFleetApiClient(
            [
                FleetDroneTelemetry(drone_id="low-battery", lat=1.5, lng=2.5, battery=60),
                FleetDroneTelemetry(drone_id="high-battery", lat=1, lng=2, battery=80),
            ]
        )

        assignments = run_auto_dispatch(db_session, client)
    finally:
        settings.dispatch_score_distance_weight = old_distance
        settings.dispatch_score_battery_weight = old_battery

    assert len(assignments) == 1
    _, job = assignments[0]
    assert job.assigned_drone_id == "high-battery"
    assert order.status.value == "ASSIGNED"
