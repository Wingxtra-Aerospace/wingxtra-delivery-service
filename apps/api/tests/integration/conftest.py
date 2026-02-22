import pytest

from app.auth.jwt import issue_jwt
from app.config import settings


@pytest.fixture
def db_backed_mode():
    original_mode = settings.ui_service_mode
    original_app_mode = settings.app_mode
    settings.ui_service_mode = "db"
    settings.app_mode = "pilot"
    try:
        yield
    finally:
        settings.ui_service_mode = original_mode
        settings.app_mode = original_app_mode


@pytest.fixture
def auth_headers():
    def _headers(role: str, sub: str) -> dict[str, str]:
        token = issue_jwt({"sub": sub, "role": role}, settings.jwt_secret)
        return {"Authorization": f"Bearer {token}"}

    return {
        "merchant_a": _headers("MERCHANT", "merchant-a"),
        "merchant_b": _headers("MERCHANT", "merchant-b"),
        "ops": _headers("OPS", "ops-1"),
        "customer": _headers("CUSTOMER", "+10000000009"),
    }


@pytest.fixture
def tenant_orders(client, auth_headers):
    base_payload = {
        "pickup_lat": 6.5,
        "pickup_lng": 3.4,
        "dropoff_lat": 6.6,
        "dropoff_lng": 3.5,
        "dropoff_accuracy_m": 8,
        "payload_weight_kg": 2.2,
        "payload_type": "parcel",
        "priority": "NORMAL",
    }

    a = client.post(
        "/api/v1/orders",
        json={**base_payload, "customer_name": "Tenant A", "customer_phone": "+10000000001"},
        headers=auth_headers["merchant_a"],
    )
    b = client.post(
        "/api/v1/orders",
        json={**base_payload, "customer_name": "Tenant B", "customer_phone": "+10000000002"},
        headers=auth_headers["merchant_b"],
    )

    assert a.status_code == 201
    assert b.status_code == 201

    return {
        "a": a.json(),
        "b": b.json(),
    }
