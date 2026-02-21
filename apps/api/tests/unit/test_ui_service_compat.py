from app.auth.dependencies import AuthContext
from app.services.store import store
from app.services.ui_store_service import create_order, manual_assign


def test_store_service_manual_assign_flow():
    store.orders.clear()
    store.events.clear()
    store.jobs.clear()

    auth = AuthContext(user_id="ops-1", role="OPS")
    order = create_order(auth, customer_name="compat-order")

    assigned = manual_assign(auth, order["id"], "DR-3")

    assert assigned["id"] == order["id"]
    assert assigned["status"] == "ASSIGNED"


def test_tracking_view_contains_id_alias_for_compatibility(client):
    create_response = client.post(
        "/api/v1/orders",
        json={"customer_name": "track-compat"},
    )
    assert create_response.status_code == 201

    created = create_response.json()
    tracking_response = client.get(f"/api/v1/tracking/{created['public_tracking_id']}")

    assert tracking_response.status_code == 200
    assert tracking_response.json()["order_id"] == created["id"]
