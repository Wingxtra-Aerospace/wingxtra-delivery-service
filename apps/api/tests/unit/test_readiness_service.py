def test_database_dependency_status_handles_sqlalchemy_error():
    from sqlalchemy.exc import SQLAlchemyError

    from app.services.readiness_service import database_dependency_status

    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("db down")

    assert database_dependency_status(BrokenSession) == "error"


def test_redis_dependency_status_with_invalid_url_scheme():
    from app.services.readiness_service import redis_dependency_status

    assert redis_dependency_status("rediss://localhost:6379/0") == "error"


def test_redis_dependency_status_handles_connection_error(monkeypatch):
    from app.services import readiness_service

    def _raise(*args, **kwargs):
        raise OSError("no route")

    monkeypatch.setattr(readiness_service.socket, "create_connection", _raise)

    assert readiness_service.redis_dependency_status("redis://localhost:6379/0") == "error"


def test_redis_dependency_status_returns_ok_when_ping_pong(monkeypatch):
    from app.services import readiness_service

    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def sendall(self, payload):
            assert payload == b"*1\r\n$4\r\nPING\r\n"

        def recv(self, _size):
            return b"+PONG\r\n"

    monkeypatch.setattr(
        readiness_service.socket,
        "create_connection",
        lambda *args, **kwargs: _FakeSocket(),
    )

    assert readiness_service.redis_dependency_status("redis://localhost:6379/0") == "ok"


def test_safe_dependency_status_logs_unexpected_exception(monkeypatch):
    from app.services import readiness_service

    events: list[tuple[str, str | None]] = []

    def _record_event(message: str, *, order_id: str | None = None, **kwargs):
        events.append((message, order_id))

    def _raises():
        raise RuntimeError("boom")

    monkeypatch.setattr(readiness_service, "log_event", _record_event)

    from app.observability import metrics_store

    metrics_store.reset()
    result = readiness_service.safe_dependency_status("database", _raises)

    snapshot = metrics_store.snapshot()
    assert result == "error"
    assert snapshot.counters.get("readiness_dependency_checked_total") == 1
    assert snapshot.counters.get("readiness_dependency_error_total") == 1
    assert events == [("readiness_dependency_check_failed", "database:RuntimeError")]


def test_redis_dependency_status_passes_configured_timeout(monkeypatch):
    from app.services import readiness_service

    observed: dict[str, float] = {}

    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def sendall(self, _payload):
            return None

        def recv(self, _size):
            return b"+PONG\r\n"

    def _create_connection(_address, timeout):
        observed["timeout"] = timeout
        return _FakeSocket()

    monkeypatch.setattr(readiness_service.socket, "create_connection", _create_connection)

    assert (
        readiness_service.redis_dependency_status("redis://localhost:6379/0", timeout_s=2.5) == "ok"
    )
    assert observed["timeout"] == 2.5


def test_safe_dependency_status_increments_metrics_for_error_status():
    from app.observability import metrics_store
    from app.services.readiness_service import safe_dependency_status

    metrics_store.reset()

    result = safe_dependency_status("redis", lambda: "error")

    snapshot = metrics_store.snapshot()
    assert result == "error"
    assert snapshot.counters.get("readiness_dependency_checked_total") == 1
    assert snapshot.counters.get("readiness_dependency_error_total") == 1


def test_safe_dependency_status_increments_metrics_for_ok_status():
    from app.observability import metrics_store
    from app.services.readiness_service import safe_dependency_status

    metrics_store.reset()

    result = safe_dependency_status("database", lambda: "ok")

    snapshot = metrics_store.snapshot()
    assert result == "ok"
    assert snapshot.counters.get("readiness_dependency_checked_total") == 1
    assert snapshot.counters.get("readiness_dependency_error_total", 0) == 0


def test_safe_dependency_status_treats_unexpected_status_as_error(monkeypatch):
    from app.observability import metrics_store
    from app.services import readiness_service

    events: list[tuple[str, str | None]] = []

    def _record_event(message: str, *, order_id: str | None = None, **kwargs):
        events.append((message, order_id))

    monkeypatch.setattr(readiness_service, "log_event", _record_event)

    metrics_store.reset()
    result = readiness_service.safe_dependency_status("redis", lambda: "degraded")

    snapshot = metrics_store.snapshot()
    assert result == "error"
    assert snapshot.counters.get("readiness_dependency_checked_total") == 1
    assert snapshot.counters.get("readiness_dependency_error_total") == 1
    assert events == [("readiness_dependency_status_invalid", "redis:degraded")]
