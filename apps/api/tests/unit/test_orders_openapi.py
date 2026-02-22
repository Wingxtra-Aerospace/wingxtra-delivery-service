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


def test_dispatch_run_request_schema_in_openapi(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    dispatch_post = openapi.json()["paths"]["/api/v1/dispatch/run"]["post"]
    assert dispatch_post["requestBody"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/DispatchRunRequest"
    )


def test_tracking_response_schema_includes_milestones(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    tracking_schema = openapi.json()["components"]["schemas"]["TrackingViewResponse"]
    assert "milestones" in tracking_schema["properties"]


def test_list_endpoints_use_consistent_paging_schema(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    payload = openapi.json()
    orders_get = payload["paths"]["/api/v1/orders"]["get"]
    jobs_get = payload["paths"]["/api/v1/jobs"]["get"]
    events_get = payload["paths"]["/api/v1/orders/{order_id}/events"]["get"]

    assert orders_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/OrdersListResponse"
    )
    assert jobs_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/JobsListResponse"
    )
    assert events_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/EventsTimelineResponse"
    )

    for name in ["OrdersListResponse", "JobsListResponse", "EventsTimelineResponse"]:
        schema = payload["components"]["schemas"][name]
        assert {"items", "page", "page_size", "total", "pagination"}.issubset(
            schema["properties"].keys()
        )


def test_jobs_list_query_params_documented(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    params = openapi.json()["paths"]["/api/v1/jobs"]["get"]["parameters"]
    by_name = {p["name"]: p for p in params}

    assert {"active", "page", "page_size", "order_id"}.issubset(by_name.keys())
    assert by_name["page"]["schema"]["minimum"] == 1
    assert by_name["page_size"]["schema"]["minimum"] == 1
    assert by_name["page_size"]["schema"]["maximum"] == 100


def test_jobs_item_schema_exposes_nullable_eta_seconds(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    job_schema = openapi.json()["components"]["schemas"]["JobResponse"]
    eta_schema = job_schema["properties"]["eta_seconds"]

    assert eta_schema["anyOf"][0]["type"] == "integer"
    assert eta_schema["anyOf"][1]["type"] == "null"


def test_jobs_detail_response_schema_in_openapi(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    jobs_detail = openapi.json()["paths"]["/api/v1/jobs/{job_id}"]["get"]
    assert jobs_detail["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/JobResponse"
    )


def test_jobs_detail_endpoint_documents_auth_errors(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    jobs_detail_responses = openapi.json()["paths"]["/api/v1/jobs/{job_id}"]["get"]["responses"]
    # FastAPI always includes 422 for path/query validation.
    assert "422" in jobs_detail_responses


def test_tracking_endpoints_document_etag_and_304_in_openapi(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    paths = openapi.json()["paths"]
    direct_get = paths["/api/v1/tracking/{public_tracking_id}"]["get"]
    legacy_get = paths["/api/v1/orders/track/{public_tracking_id}"]["get"]

    for endpoint in (direct_get, legacy_get):
        headers_200 = endpoint["responses"]["200"]["headers"]
        assert "ETag" in headers_200
        assert headers_200["ETag"]["schema"]["type"] == "string"
        assert "Cache-Control" in headers_200
        assert headers_200["Cache-Control"]["schema"]["type"] == "string"

        response_304 = endpoint["responses"]["304"]
        assert response_304["description"] == "Not Modified"
        assert "ETag" in response_304["headers"]
        assert "Cache-Control" in response_304["headers"]
