import pytest

pytestmark = pytest.mark.usefixtures("db_backed_mode")


def test_merchant_a_cannot_read_cancel_or_submit_events_for_merchant_b_order(
    client, auth_headers, tenant_orders
):
    b_order_id = tenant_orders["b"]["id"]

    read_other = client.get(f"/api/v1/orders/{b_order_id}", headers=auth_headers["merchant_a"])
    assert read_other.status_code == 403

    cancel_other = client.post(
        f"/api/v1/orders/{b_order_id}/cancel", headers=auth_headers["merchant_a"]
    )
    assert cancel_other.status_code == 403

    ingest_other = client.post(
        f"/api/v1/orders/{b_order_id}/events",
        json={"event_type": "ENROUTE"},
        headers=auth_headers["merchant_a"],
    )
    assert ingest_other.status_code == 403


def test_customer_cannot_access_ops_only_endpoints(client, auth_headers, tenant_orders):
    b_order_id = tenant_orders["b"]["id"]

    dispatch = client.post("/api/v1/dispatch/run", headers=auth_headers["customer"])
    assert dispatch.status_code == 403

    assign = client.post(
        f"/api/v1/orders/{b_order_id}/assign",
        json={"drone_id": "DR-1"},
        headers=auth_headers["customer"],
    )
    assert assign.status_code == 403

    ingest = client.post(
        f"/api/v1/orders/{b_order_id}/events",
        json={"event_type": "ENROUTE"},
        headers=auth_headers["customer"],
    )
    assert ingest.status_code == 403

    jobs = client.get("/api/v1/jobs", headers=auth_headers["customer"])
    assert jobs.status_code == 403

    metrics = client.get("/metrics", headers=auth_headers["customer"])
    assert metrics.status_code == 403


def test_public_tracking_endpoints_never_return_pii(client, tenant_orders):
    tracking_id = tenant_orders["a"]["public_tracking_id"]

    direct = client.get(f"/api/v1/tracking/{tracking_id}")
    alias = client.get(f"/api/v1/orders/track/{tracking_id}")

    assert direct.status_code == 200
    assert alias.status_code == 200

    forbidden_keys = {
        "customer_phone",
        "customer_email",
        "customer_address",
        "merchant_id",
        "merchant_name",
        "photo_url",
    }
    for payload in (direct.json(), alias.json()):
        assert forbidden_keys.isdisjoint(payload.keys())
        assert set(payload.keys()).issubset(
            {"order_id", "public_tracking_id", "status", "milestones", "pod_summary"}
        )


def test_public_tracking_token_cannot_access_authenticated_endpoints(client, tenant_orders):
    tracking_token = tenant_orders["a"]["public_tracking_id"]
    headers = {"Authorization": f"Bearer {tracking_token}"}

    list_orders = client.get("/api/v1/orders", headers=headers)
    assert list_orders.status_code == 401

    dispatch = client.post("/api/v1/dispatch/run", headers=headers)
    assert dispatch.status_code == 401
