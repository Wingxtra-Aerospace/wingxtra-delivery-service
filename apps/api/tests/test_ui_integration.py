from fastapi.testclient import TestClient

from app.auth.dependencies import reset_rate_limits
from app.auth.jwt import issue_jwt
from app.config import settings
from app.main import app

client = TestClient(app)


def _jwt(sub: str, role: str, source: str | None = None) -> str:
    payload = {"sub": sub, "role": role}
    if source:
        payload["source"] = source
    return issue_jwt(payload, settings.jwt_secret)


def _headers(role: str = "OPS", sub: str = "ops-1", source: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_jwt(sub=sub, role=role, source=source)}"}
    if source == "gcs":
        headers["X-Wingxtra-Source"] = "gcs"
    return headers


def test_orders_list_with_pagination_filters_as_ops():
    response = client.get(
        "/api/v1/orders?page=1&page_size=10&search=TRK001",
        headers=_headers("OPS"),
    )
    assert response.status_code == 200


def test_merchant_can_create_and_view_own_order_only():
    create = client.post(
        "/api/v1/orders",
        json={"customer_name": "Merchant Customer"},
        headers=_headers("MERCHANT", sub="merchant-99"),
    )
    assert create.status_code == 200
    created = create.json()

    list_own = client.get("/api/v1/orders", headers=_headers("MERCHANT", sub="merchant-99"))
    assert any(item["id"] == created["id"] for item in list_own.json()["items"])

    forbidden = client.get("/api/v1/orders/ord-1", headers=_headers("MERCHANT", sub="merchant-99"))
    assert forbidden.status_code == 403


def test_jobs_forbidden_for_merchant_and_allowed_for_admin():
    merchant_jobs = client.get("/api/v1/jobs", headers=_headers("MERCHANT", sub="merchant-1"))
    assert merchant_jobs.status_code == 403

    admin_jobs = client.get("/api/v1/jobs", headers=_headers("ADMIN", sub="admin-1"))
    assert admin_jobs.status_code == 200


def test_gcs_authenticated_requests_map_to_ops_role():
    response = client.post(
        "/api/v1/orders/ord-1/assign",
        json={"drone_id": "DR-2"},
        headers=_headers(role="CUSTOMER", sub="gcs-user", source="gcs"),
    )
    assert response.status_code == 200


def test_public_tracking_is_unauthenticated_and_sanitized():
    tracking = client.get("/api/v1/tracking/TRK001")
    assert tracking.status_code == 200
    payload = tracking.json()
    assert set(payload.keys()) == {"order_id", "public_tracking_id", "status"}


def test_protected_endpoints_require_jwt():
    response = client.get("/api/v1/orders")
    assert response.status_code == 401


def test_public_tracking_rate_limit_enforced():
    reset_rate_limits()
    for _ in range(settings.public_tracking_rate_limit_requests):
        ok = client.get("/api/v1/tracking/TRK001")
        assert ok.status_code == 200

    limited = client.get("/api/v1/tracking/TRK001")
    assert limited.status_code == 429


def test_idempotency_for_create_order_replay_and_conflict():
    headers = _headers("MERCHANT", sub="merchant-22")
    headers["Idempotency-Key"] = "idem-create-1"

    first = client.post("/api/v1/orders", json={"customer_name": "A"}, headers=headers)
    second = client.post("/api/v1/orders", json={"customer_name": "A"}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conflict = client.post("/api/v1/orders", json={"customer_name": "B"}, headers=headers)
    assert conflict.status_code == 409


def test_idempotency_for_mission_submission_replay_and_conflict():
    headers = _headers("OPS", sub="ops-22")

    assign = client.post(
        "/api/v1/orders/ord-1/assign",
        json={"drone_id": "DR-4"},
        headers=headers,
    )
    assert assign.status_code == 200

    idem_headers = dict(headers)
    idem_headers["Idempotency-Key"] = "idem-mission-1"

    first = client.post("/api/v1/orders/ord-1/submit-mission-intent", headers=idem_headers)
    second = client.post("/api/v1/orders/ord-1/submit-mission-intent", headers=idem_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()

    conflict = client.post("/api/v1/orders/ord-2/submit-mission-intent", headers=idem_headers)
    assert conflict.status_code == 409


def test_order_creation_rate_limit_enforced():
    reset_rate_limits()
    original_requests = settings.order_create_rate_limit_requests
    original_window = settings.order_create_rate_limit_window_s
    settings.order_create_rate_limit_requests = 2
    settings.order_create_rate_limit_window_s = 60

    try:
        headers = _headers("MERCHANT", sub="merchant-rate")
        for i in range(2):
            ok = client.post(
                "/api/v1/orders",
                json={"customer_name": f"Rate Test {i}"},
                headers=headers,
            )
            assert ok.status_code == 200

        limited = client.post(
            "/api/v1/orders",
            json={"customer_name": "Rate Test 3"},
            headers=headers,
        )
        assert limited.status_code == 429
        assert limited.json()["detail"] == "Order creation rate limit exceeded"
    finally:
        settings.order_create_rate_limit_requests = original_requests
        settings.order_create_rate_limit_window_s = original_window
        reset_rate_limits()
