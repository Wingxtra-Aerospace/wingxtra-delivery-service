from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.dependencies import reset_rate_limits
from app.auth.jwt import issue_jwt
from app.config import settings
from app.main import app
from app.models.order import Order, OrderStatus

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
    assert create.status_code == 201
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
        json={"drone_id": "DR-3"},
        headers=_headers(role="CUSTOMER", sub="gcs-user", source="gcs"),
    )
    assert response.status_code == 200


def test_public_tracking_is_unauthenticated_and_sanitized():
    tracking = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
    assert tracking.status_code == 200
    payload = tracking.json()
    assert set(payload.keys()) == {"order_id", "public_tracking_id", "status"}


def test_orders_track_endpoint_is_unauthenticated_and_sanitized():
    tracking = client.get("/api/v1/orders/track/11111111-1111-4111-8111-111111111111")
    assert tracking.status_code == 200
    payload = tracking.json()
    assert set(payload.keys()) == {"order_id", "public_tracking_id", "status"}


def test_protected_endpoints_allow_test_bypass_without_jwt():
    response = client.get("/api/v1/orders")
    assert response.status_code == 200


def test_public_tracking_rate_limit_enforced():
    reset_rate_limits()
    for _ in range(settings.public_tracking_rate_limit_requests):
        ok = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        assert ok.status_code == 200

    limited = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
    assert limited.status_code == 429


def test_idempotency_for_create_order_replay_and_conflict():
    headers = _headers("MERCHANT", sub="merchant-22")
    headers["Idempotency-Key"] = "idem-create-1"

    first = client.post("/api/v1/orders", json={"customer_name": "A"}, headers=headers)
    second = client.post("/api/v1/orders", json={"customer_name": "A"}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
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
            assert ok.status_code == 201

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


def test_request_id_echoed_in_response_header():
    request_id = "req-123"
    response = client.get(
        "/api/v1/orders",
        headers={**_headers("OPS"), "X-Request-ID": request_id},
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id


def test_metrics_endpoint_exposes_dispatch_and_mission_timings():
    headers = _headers("OPS", sub="ops-metrics")

    assign = client.post(
        "/api/v1/orders/ord-1/assign",
        json={"drone_id": "DR-METRICS"},
        headers=headers,
    )
    assert assign.status_code == 200

    mission = client.post("/api/v1/orders/ord-1/submit-mission-intent", headers=headers)
    assert mission.status_code == 200

    metrics = client.get("/metrics", headers=headers)
    assert metrics.status_code == 200
    payload = metrics.json()

    assert "counters" in payload
    assert "http_requests_total" in payload["counters"]
    assert "timings" in payload
    assert "dispatch_assignment_seconds" in payload["timings"]
    assert "mission_intent_generation_seconds" in payload["timings"]


def test_auto_dispatch_assigns_placeholder_ord2_when_queued():
    headers = _headers("OPS", sub="ops-dispatch-ord2")

    run = client.post("/api/v1/dispatch/run", headers=headers)
    assert run.status_code == 200

    assignments = run.json()["assignments"]
    assert any(item["order_id"] == "ord-2" for item in assignments)
    assert all("order_id" in item and "status" in item for item in assignments)


def test_auto_dispatch_and_manual_assign_routes_exist():
    headers = _headers("OPS", sub="ops-dispatch")

    run = client.post("/api/v1/dispatch/run", headers=headers)
    assert run.status_code == 200
    assert "assigned" in run.json()
    assert "assignments" in run.json()

    assign = client.post(
        "/api/v1/orders/ord-1/assign",
        json={"drone_id": "DR-ROUTE"},
        headers=headers,
    )
    assert assign.status_code == 200


def test_placeholder_order_ids_support_assign_and_submit_mission():
    headers = _headers("OPS", sub="ops-placeholders")

    assign = client.post(
        "/api/v1/orders/ord-2/assign",
        json={"drone_id": "DR-6"},
        headers=headers,
    )
    assert assign.status_code == 200

    mission = client.post(
        "/api/v1/orders/ord-2/submit-mission-intent",
        headers=headers,
    )
    assert mission.status_code == 200


def test_manual_assign_includes_validated_and_queued_events():
    create = client.post(
        "/api/v1/orders",
        json={"customer_name": "Event Sequence"},
        headers=_headers("OPS", sub="ops-events"),
    )
    assert create.status_code == 201
    order_id = create.json()["id"]

    assign = client.post(
        f"/api/v1/orders/{order_id}/assign",
        json={"drone_id": "DR-3"},
        headers=_headers("OPS", sub="ops-events"),
    )
    assert assign.status_code == 200

    events = client.get(
        f"/api/v1/orders/{order_id}/events",
        headers=_headers("OPS", sub="ops-events"),
    )
    assert events.status_code == 200
    assert [item["type"] for item in events.json()["items"]] == [
        "CREATED",
        "VALIDATED",
        "QUEUED",
        "ASSIGNED",
    ]


def test_manual_assign_requires_ops_or_admin():
    order = client.post(
        "/api/v1/orders",
        json={"customer_name": "RBAC Assign"},
        headers=_headers("MERCHANT", sub="merchant-11"),
    ).json()

    denied = client.post(
        f"/api/v1/orders/{order['id']}/assign",
        json={"drone_id": "DR-1"},
        headers=_headers("MERCHANT", sub="merchant-11"),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Write action requires OPS/ADMIN"


def test_idempotency_for_cancel_replay_and_order_scope():
    headers = _headers("OPS", sub="ops-cancel-idem")

    order_one = client.post(
        "/api/v1/orders",
        json={"customer_name": "Cancel Idem One"},
        headers=headers,
    ).json()
    order_two = client.post(
        "/api/v1/orders",
        json={"customer_name": "Cancel Idem Two"},
        headers=headers,
    ).json()

    idem_headers = dict(headers)
    idem_headers["Idempotency-Key"] = "idem-cancel-1"

    first_cancel = client.post(f"/api/v1/orders/{order_one['id']}/cancel", headers=idem_headers)
    replay_cancel = client.post(f"/api/v1/orders/{order_one['id']}/cancel", headers=idem_headers)
    second_order_cancel = client.post(
        f"/api/v1/orders/{order_two['id']}/cancel",
        headers=idem_headers,
    )

    assert first_cancel.status_code == 200
    assert replay_cancel.status_code == 200
    assert replay_cancel.json() == first_cancel.json()

    assert second_order_cancel.status_code == 200
    assert second_order_cancel.json()["order_id"] == order_two["id"]
    assert second_order_cancel.json()["status"] == "CANCELED"


def test_idempotency_for_assign_and_pod_replay_and_conflict(db_session):
    headers = _headers("OPS", sub="ops-idem")
    order = client.post("/api/v1/orders", json={"customer_name": "Idem"}, headers=headers).json()

    assign_headers = dict(headers)
    assign_headers["Idempotency-Key"] = "idem-assign-1"
    first_assign = client.post(
        f"/api/v1/orders/{order['id']}/assign",
        json={"drone_id": "DR-1"},
        headers=assign_headers,
    )
    replay_assign = client.post(
        f"/api/v1/orders/{order['id']}/assign",
        json={"drone_id": "DR-1"},
        headers=assign_headers,
    )
    conflict_assign = client.post(
        f"/api/v1/orders/{order['id']}/assign",
        json={"drone_id": "DR-2"},
        headers=assign_headers,
    )
    assert first_assign.status_code == 200
    assert replay_assign.status_code == 200
    assert replay_assign.json() == first_assign.json()
    assert conflict_assign.status_code == 409

    db_order = db_session.get(Order, UUID(order["id"]))
    db_order.status = OrderStatus.DELIVERED
    db_session.commit()

    pod_headers = dict(headers)
    pod_headers["Idempotency-Key"] = "idem-pod-1"
    pod_payload = {"method": "PHOTO", "photo_url": "https://cdn.example/pod.jpg"}
    first_pod = client.post(
        f"/api/v1/orders/{order['id']}/pod", json=pod_payload, headers=pod_headers
    )
    replay_pod = client.post(
        f"/api/v1/orders/{order['id']}/pod", json=pod_payload, headers=pod_headers
    )
    conflict_pod = client.post(
        f"/api/v1/orders/{order['id']}/pod",
        json={"method": "OPERATOR_CONFIRM", "operator_name": "ops"},
        headers=pod_headers,
    )

    assert first_pod.status_code == 200
    assert replay_pod.status_code == 200
    assert replay_pod.json() == first_pod.json()
    assert conflict_pod.status_code == 409


def test_get_pod_returns_nullable_method_when_record_missing():
    order = client.post(
        "/api/v1/orders",
        json={"customer_name": "No POD yet"},
        headers=_headers("OPS", sub="ops-pod-read"),
    ).json()

    response = client.get(
        f"/api/v1/orders/{order['id']}/pod",
        headers=_headers("OPS", sub="ops-pod-read"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_id"] == order["id"]
    assert payload["method"] is None


def test_mission_submit_translates_integration_errors():
    class FailingPublisher:
        def publish_mission_intent(self, mission_intent: dict) -> None:
            from app.integrations.errors import IntegrationUnavailableError

            raise IntegrationUnavailableError("gcs_bridge", "bridge unavailable")

    from app.integrations.gcs_bridge_client import get_gcs_bridge_client

    app.dependency_overrides[get_gcs_bridge_client] = lambda: FailingPublisher()

    headers = _headers("OPS", sub="ops-integration")
    assign = client.post(
        "/api/v1/orders/ord-1/assign",
        json={"drone_id": "DR-3"},
        headers=headers,
    )
    assert assign.status_code == 200

    response = client.post("/api/v1/orders/ord-1/submit-mission-intent", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"]["service"] == "gcs_bridge"
    app.dependency_overrides.clear()
