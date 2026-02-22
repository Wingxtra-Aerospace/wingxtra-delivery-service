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


def test_rate_limit_headers_documented_in_openapi(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]

    create_order_201_headers = paths["/api/v1/orders"]["post"]["responses"]["201"]["headers"]
    assert "X-RateLimit-Limit" in create_order_201_headers
    assert "X-RateLimit-Remaining" in create_order_201_headers
    assert "X-RateLimit-Reset" in create_order_201_headers
    assert create_order_201_headers["X-RateLimit-Limit"]["schema"]["type"] == "string"
    assert create_order_201_headers["X-RateLimit-Remaining"]["schema"]["type"] == "string"
    assert create_order_201_headers["X-RateLimit-Reset"]["schema"]["type"] == "string"
    assert create_order_201_headers["X-RateLimit-Limit"]["schema"]["pattern"] == r"^\d+$"

    tracking_429_headers = paths["/api/v1/tracking/{public_tracking_id}"]["get"]["responses"][
        "429"
    ]["headers"]
    assert "Retry-After" in tracking_429_headers
    assert "X-RateLimit-Limit" in tracking_429_headers
    assert tracking_429_headers["Retry-After"]["schema"]["type"] == "string"
    assert tracking_429_headers["Retry-After"]["schema"]["pattern"] == r"^\d+$"
