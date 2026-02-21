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
