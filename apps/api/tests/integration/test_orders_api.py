from uuid import UUID


def _create_order(client):
    payload = {
        "customer_name": "Jane Doe",
        "customer_phone": "+123456789",
        "pickup_lat": 6.5,
        "pickup_lng": 3.4,
        "dropoff_lat": 6.6,
        "dropoff_lng": 3.5,
        "dropoff_accuracy_m": 8,
        "payload_weight_kg": 2.2,
        "payload_type": "parcel",
        "priority": "NORMAL",
    }
    return client.post("/api/v1/orders", json=payload)


def test_create_get_list_cancel_and_tracking(client):
    create_response = _create_order(client)
    assert create_response.status_code == 201
    created = create_response.json()
    UUID(created["id"])

    get_response = client.get(f"/api/v1/orders/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]

    list_response = client.get("/api/v1/orders")
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    tracking_response = client.get(f"/api/v1/tracking/{created['public_tracking_id']}")
    assert tracking_response.status_code == 200
    assert tracking_response.json()["order_id"] == created["id"]

    cancel_response = client.post(f"/api/v1/orders/{created['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELED"


def test_get_order_not_found(client):
    response = client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_create_order_validation_error(client):
    response = client.post(
        "/api/v1/orders",
        json={
            "pickup_lat": 100,
            "pickup_lng": 3.4,
            "dropoff_lat": 6.6,
            "dropoff_lng": 3.5,
            "payload_weight_kg": -1,
            "payload_type": "",
        },
    )
    assert response.status_code == 422
