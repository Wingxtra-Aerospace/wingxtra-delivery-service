from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH_HEADERS = {
    "Authorization": "Bearer wingxtra-dev-token",
    "X-Wingxtra-Source": "gcs",
}


def test_orders_list_with_pagination_filters():
    response = client.get("/api/v1/orders?page=1&page_size=10&search=TRK001", headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["total"] >= 1


def test_order_detail_events_assign_cancel_flow():
    order_id = client.get("/api/v1/orders", headers=AUTH_HEADERS).json()["items"][0]["id"]

    detail = client.get(f"/api/v1/orders/{order_id}", headers=AUTH_HEADERS)
    assert detail.status_code == 200

    events = client.get(f"/api/v1/orders/{order_id}/events", headers=AUTH_HEADERS)
    assert events.status_code == 200

    assign = client.post(
        f"/api/v1/orders/{order_id}/assign",
        json={"drone_id": "DR-2"},
        headers=AUTH_HEADERS,
    )
    assert assign.status_code == 200

    cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=AUTH_HEADERS)
    assert cancel.status_code == 200


def test_jobs_and_tracking_views():
    jobs = client.get("/api/v1/jobs?active=true", headers=AUTH_HEADERS)
    assert jobs.status_code == 200

    tracking = client.get("/api/v1/tracking/TRK001")
    assert tracking.status_code == 200
    assert tracking.json()["public_tracking_id"] == "TRK001"


def test_protected_endpoints_require_gcs_auth_headers():
    response = client.get("/api/v1/orders")
    assert response.status_code == 401


def test_cors_preflight_has_origin_header():
    response = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
