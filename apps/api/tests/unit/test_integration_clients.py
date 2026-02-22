import httpx
import pytest

from app.integrations.errors import (
    IntegrationBadGatewayError,
    IntegrationTimeoutError,
    IntegrationUnavailableError,
)
from app.integrations.fleet_api_client import FleetApiClient
from app.integrations.gcs_bridge_client import GcsBridgeClient


def _valid_mission_intent() -> dict:
    return {
        "intent_id": "mi_123",
        "order_id": "11111111-1111-1111-1111-111111111111",
        "drone_id": "DR-1",
        "pickup": {"lat": 1.0, "lng": 2.0, "alt_m": 20},
        "dropoff": {"lat": 3.0, "lng": 4.0, "alt_m": 20, "delivery_alt_m": 8},
        "actions": ["TAKEOFF", "CRUISE", "DESCEND", "DROP_OR_WINCH", "ASCEND", "RTL"],
        "constraints": {"battery_min_pct": 30, "service_area_id": "default"},
        "safety": {"abort_rtl_on_fail": True, "loiter_timeout_s": 60, "lost_link_behavior": "RTL"},
        "metadata": {
            "payload_type": "BOX",
            "payload_weight_kg": 1.5,
            "priority": "NORMAL",
            "created_at": "2026-02-20T10:00:00Z",
        },
    }


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _ClientStub:
    def __init__(self, get_sequence=None, post_sequence=None):
        self._get_sequence = get_sequence or []
        self._post_sequence = post_sequence or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _url):
        value = self._get_sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def post(self, _url, json):
        _ = json
        value = self._post_sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_fleet_client_retries_then_succeeds(monkeypatch):
    sequence = [
        httpx.ReadTimeout("timeout"),
        _Response(
            200, [{"drone_id": "DR-1", "lat": 1.0, "lng": 2.0, "battery": 99, "is_available": True}]
        ),
    ]
    monkeypatch.setattr(
        "app.integrations.fleet_api_client.httpx.Client",
        lambda timeout: _ClientStub(get_sequence=sequence),
    )

    client = FleetApiClient(
        "http://fleet", timeout_s=0.1, max_retries=2, backoff_s=0, cache_ttl_s=2
    )
    telemetry = client.get_latest_telemetry()
    assert len(telemetry) == 1
    assert telemetry[0].drone_id == "DR-1"


def test_fleet_client_maps_4xx_to_bad_gateway(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.fleet_api_client.httpx.Client",
        lambda timeout: _ClientStub(get_sequence=[_Response(404, {})]),
    )

    client = FleetApiClient(
        "http://fleet", timeout_s=0.1, max_retries=0, backoff_s=0, cache_ttl_s=2
    )
    with pytest.raises(IntegrationBadGatewayError):
        client.get_latest_telemetry()


def test_gcs_client_retries_and_raises_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.integrations.gcs_bridge_client.httpx.Client",
        lambda timeout: _ClientStub(post_sequence=[httpx.ReadTimeout("timeout")]),
    )

    client = GcsBridgeClient("http://gcs", timeout_s=0.1, max_retries=0, backoff_s=0)
    with pytest.raises(IntegrationTimeoutError):
        client.publish_mission_intent(_valid_mission_intent())


def test_gcs_client_rejects_invalid_mission_intent_contract():
    client = GcsBridgeClient("http://gcs", timeout_s=0.1, max_retries=0, backoff_s=0)

    with pytest.raises(IntegrationBadGatewayError):
        client.publish_mission_intent({"order_id": "ord-1"})


def test_fleet_client_requires_base_url():
    client = FleetApiClient("", timeout_s=0.1, max_retries=0, backoff_s=0, cache_ttl_s=2)

    with pytest.raises(IntegrationUnavailableError):
        client.get_latest_telemetry()


def test_fleet_client_uses_ttl_cache(monkeypatch):
    calls = {"count": 0}

    def _client_factory(timeout):
        _ = timeout
        calls["count"] += 1
        return _ClientStub(
            get_sequence=[
                _Response(
                    200,
                    [
                        {
                            "drone_id": "DR-1",
                            "lat": 1.0,
                            "lng": 2.0,
                            "battery": 99,
                            "is_available": True,
                        }
                    ],
                )
            ]
        )

    monkeypatch.setattr("app.integrations.fleet_api_client.httpx.Client", _client_factory)

    client = FleetApiClient(
        "http://fleet", timeout_s=0.1, max_retries=0, backoff_s=0, cache_ttl_s=5
    )
    first = client.get_latest_telemetry()
    second = client.get_latest_telemetry()

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1
