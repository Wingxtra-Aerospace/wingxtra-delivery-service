def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": {"fleet_api": "down", "gcs_bridge": "down"},
    }


def test_health_reports_dependency_states_without_failing(monkeypatch, client):
    from app.routers import health

    monkeypatch.setattr(health, "fleet_dependency_health_status", lambda *_a, **_k: "degraded")
    monkeypatch.setattr(health, "gcs_bridge_dependency_health_status", lambda *_a, **_k: "down")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["dependencies"] == {"fleet_api": "degraded", "gcs_bridge": "down"}


def test_readiness_check(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": [{"name": "database", "status": "ok"}],
    }


def test_readiness_check_includes_fleet_when_configured(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "fleet_api_base_url", "http://fleet")
    monkeypatch.setattr(health, "fleet_dependency_status", lambda *_args, **_kwargs: "ok")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": [
            {"name": "database", "status": "ok"},
            {"name": "fleet_api", "status": "ok"},
        ],
    }


def test_readiness_check_includes_redis_when_configured(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(health, "redis_dependency_status", lambda *_args, **_kwargs: "ok")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": [
            {"name": "database", "status": "ok"},
            {"name": "redis", "status": "ok"},
        ],
    }


def test_health_endpoint_exposes_explicit_response_schema(client):
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200

    payload = openapi.json()
    health_get = payload["paths"]["/health"]["get"]
    ready_get = payload["paths"]["/ready"]["get"]

    assert health_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/HealthResponse"
    )
    assert ready_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ReadinessResponse"
    )
    assert ready_get["responses"]["503"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ReadinessResponse"
    )


def test_readiness_check_degraded_when_database_unavailable(client, monkeypatch):
    from app.routers import health

    def _broken_db(*args, **kwargs):
        return "error"

    monkeypatch.setattr(health, "database_dependency_status", _broken_db)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [{"name": "database", "status": "error"}],
    }


def test_readiness_check_degraded_when_dependency_check_raises(client, monkeypatch):
    from app.routers import health

    def _broken_db(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(health, "database_dependency_status", _broken_db)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [{"name": "database", "status": "error"}],
    }


def test_readiness_check_degraded_when_redis_unavailable(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(health, "redis_dependency_status", lambda *_args, **_kwargs: "error")

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [
            {"name": "database", "status": "ok"},
            {"name": "redis", "status": "error"},
        ],
    }


def test_readiness_check_degraded_when_fleet_unavailable(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "fleet_api_base_url", "http://fleet")
    monkeypatch.setattr(health, "fleet_dependency_status", lambda *_args, **_kwargs: "error")

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [
            {"name": "database", "status": "ok"},
            {"name": "fleet_api", "status": "error"},
        ],
    }
