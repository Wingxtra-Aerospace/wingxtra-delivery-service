import pytest
from fastapi import HTTPException

from app.integrations.fleet_api_client import FleetDroneTelemetry
from app.schemas.order import OrderCreate
from app.services.dispatch_service import manual_assign_order
from app.services.mission_intent_service import submit_mission_intent
from app.services.orders_service import create_order


class FakeFleetApiClient:
    def get_latest_telemetry(self):
        return [FleetDroneTelemetry(drone_id="D1", lat=1, lng=2, battery=90, is_available=True)]


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish_mission_intent(self, mission_intent: dict) -> None:
        self.published.append(mission_intent)


def _payload() -> OrderCreate:
    return OrderCreate(
        pickup_lat=1,
        pickup_lng=2,
        dropoff_lat=3,
        dropoff_lng=4,
        payload_weight_kg=1.5,
        payload_type="BOX",
    )


def test_submit_mission_intent_sets_job_field_and_publishes(db_session):
    order = create_order(db_session, _payload())
    job = manual_assign_order(db_session, FakeFleetApiClient(), order.id, "D1")
    publisher = FakePublisher()

    updated_order, updated_job, intent = submit_mission_intent(db_session, publisher, order.id)

    assert updated_job.id == job.id
    assert updated_job.mission_intent_id == intent["intent_id"]
    assert updated_order.status.value == "MISSION_SUBMITTED"
    assert publisher.published[0]["intent_id"] == intent["intent_id"]


def test_submit_mission_intent_requires_assigned_state(db_session):
    order = create_order(db_session, _payload())

    with pytest.raises(HTTPException) as exc:
        submit_mission_intent(db_session, FakePublisher(), order.id)

    assert exc.value.status_code == 409
