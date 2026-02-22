from sqlalchemy.exc import SQLAlchemyError


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": [{"name": "database", "status": "ok"}],
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


def test_readiness_check_degraded_when_database_unavailable(client, monkeypatch):
    from app.routers import health

    def _broken_db(*args, **kwargs):
        return "error"

    monkeypatch.setattr(health, "_database_dependency_status", _broken_db)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": [{"name": "database", "status": "error"}],
    }


def test_readiness_check_degraded_when_dependency_check_raises(client, monkeypatch):
    from app.routers import health

    def _broken_db(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(health, "_database_dependency_status", _broken_db)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": [{"name": "database", "status": "error"}],
    }


def test_database_dependency_status_handles_sqlalchemy_error():
    from app.routers.health import _database_dependency_status

    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("db down")

    assert _database_dependency_status(BrokenSession) == "error"
