def test_orders_tracking_and_pod_read_expose_response_schemas(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    payload = openapi.json()

    tracking_get = payload["paths"]["/api/v1/orders/track/{public_tracking_id}"]["get"]
    pod_get = payload["paths"]["/api/v1/orders/{order_id}/pod"]["get"]

    assert tracking_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/TrackingViewResponse"
    )
    assert pod_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/PodResponse"
    )
