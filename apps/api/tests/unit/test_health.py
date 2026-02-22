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


def test_readiness_check_includes_redis_when_configured(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(health, "_redis_dependency_status", lambda *_args, **_kwargs: "ok")

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

    monkeypatch.setattr(health, "_database_dependency_status", _broken_db)

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

    monkeypatch.setattr(health, "_database_dependency_status", _broken_db)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [{"name": "database", "status": "error"}],
    }


def test_readiness_check_degraded_when_redis_unavailable(client, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health.settings, "redis_url", "redis://localhost:6379/0")
    monkeypatch.setattr(health, "_redis_dependency_status", lambda *_args, **_kwargs: "error")

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": [
            {"name": "database", "status": "ok"},
            {"name": "redis", "status": "error"},
        ],
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


def test_redis_dependency_status_with_invalid_url_scheme():
    from app.routers.health import _redis_dependency_status

    assert _redis_dependency_status("rediss://localhost:6379/0") == "error"


def test_redis_dependency_status_handles_connection_error(monkeypatch):
    from app.routers import health

    def _raise(*args, **kwargs):
        raise OSError("no route")

    monkeypatch.setattr(health.socket, "create_connection", _raise)

    assert health._redis_dependency_status("redis://localhost:6379/0") == "error"


def test_redis_dependency_status_returns_ok_when_ping_pong(monkeypatch):
    from app.routers import health

    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def sendall(self, payload):
            assert payload == b"*1\r\n$4\r\nPING\r\n"

        def recv(self, _size):
            return b"+PONG\r\n"

    monkeypatch.setattr(health.socket, "create_connection", lambda *args, **kwargs: _FakeSocket())

    assert health._redis_dependency_status("redis://localhost:6379/0") == "ok"


def test_safe_dependency_status_logs_unexpected_exception(monkeypatch):
    from app.routers import health

    events: list[tuple[str, str | None]] = []

    def _record_event(message: str, *, order_id: str | None = None, **kwargs):
        events.append((message, order_id))

    def _raises():
        raise RuntimeError("boom")

    monkeypatch.setattr(health, "log_event", _record_event)

    result = health._safe_dependency_status("database", _raises)

    assert result == "error"
    assert events == [("readiness_dependency_check_failed", "database:RuntimeError")]
