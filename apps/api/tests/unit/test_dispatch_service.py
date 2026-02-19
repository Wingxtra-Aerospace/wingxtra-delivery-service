from app.integrations.fleet_api_client import FleetDroneTelemetry
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
