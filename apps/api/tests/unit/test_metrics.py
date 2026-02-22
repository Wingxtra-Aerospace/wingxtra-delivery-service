from app.auth.jwt import issue_jwt
from app.config import settings


def test_metrics_endpoint_returns_typed_payload(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["counters"], dict)
    assert isinstance(payload["timings"], dict)


def test_metrics_endpoint_exposes_explicit_response_schema(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    payload = openapi.json()
    metrics_get = payload["paths"]["/metrics"]["get"]

    assert metrics_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/MetricsResponse"
    )


def test_metrics_endpoint_requires_auth_when_test_bypass_disabled(client):
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = False
    try:
        response = client.get("/metrics")
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing bearer token"
    finally:
        settings.enable_test_auth_bypass = original


def test_metrics_endpoint_rejects_non_backoffice_role(client):
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = False
    try:
        merchant_token = issue_jwt(
            {"sub": "merchant-1", "role": "MERCHANT"},
            settings.jwt_secret,
        )
        response = client.get("/metrics", headers={"Authorization": f"Bearer {merchant_token}"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient role"
    finally:
        settings.enable_test_auth_bypass = original


def test_metrics_endpoint_accepts_ops_role_jwt(client):
    original = settings.enable_test_auth_bypass
    settings.enable_test_auth_bypass = False
    try:
        ops_token = issue_jwt(
            {"sub": "ops-1", "role": "OPS"},
            settings.jwt_secret,
        )
        response = client.get("/metrics", headers={"Authorization": f"Bearer {ops_token}"})
        assert response.status_code == 200
    finally:
        settings.enable_test_auth_bypass = original


def test_metrics_capture_readiness_check_counters(client):
    ready = client.get("/ready")
    assert ready.status_code == 200

    metrics = client.get("/metrics")
    assert metrics.status_code == 200

    counters = metrics.json().get("counters", {})
    assert int(counters.get("readiness_dependency_checked_total", 0)) >= 1
    assert int(counters.get("readiness_dependency_error_total", 0)) == 0


def test_metrics_capture_readiness_error_counter_on_degraded_check(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health, "database_dependency_status", lambda *_a, **_k: "error")

    ready = client.get("/ready")
    assert ready.status_code == 503

    metrics = client.get("/metrics")
    assert metrics.status_code == 200

    counters = metrics.json().get("counters", {})
    assert int(counters.get("readiness_dependency_checked_total", 0)) >= 1
    assert int(counters.get("readiness_dependency_error_total", 0)) >= 1
