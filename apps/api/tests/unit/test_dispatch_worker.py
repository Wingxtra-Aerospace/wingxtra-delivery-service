import importlib.util
import json
import pathlib
import sys
import urllib.error

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
WORKER_PATH = REPO_ROOT / "workers" / "dispatch_worker" / "worker.py"


spec = importlib.util.spec_from_file_location("dispatch_worker_module", WORKER_PATH)
worker_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = worker_module
spec.loader.exec_module(worker_module)


class _FakeResponse:
    def __init__(self, body: dict, status: int = 200) -> None:
        self._body = json.dumps(body).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_load_settings_defaults():
    settings = worker_module.load_settings({})

    assert settings.api_base_url == "http://localhost:8000"
    assert settings.interval_s == 10
    assert settings.timeout_s == 5.0
    assert settings.max_assignments is None
    assert settings.max_retries == 2


def test_load_settings_rejects_invalid_interval():
    with pytest.raises(ValueError, match="INTERVAL"):
        worker_module.load_settings({"WINGXTRA_DISPATCH_WORKER_INTERVAL_S": "0"})


def test_load_settings_rejects_negative_max_retries():
    with pytest.raises(ValueError, match="MAX_RETRIES"):
        worker_module.load_settings({"WINGXTRA_DISPATCH_WORKER_MAX_RETRIES": "-1"})


def test_run_dispatch_once_success_with_max_assignments():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=3,
        auth_token="abc",
        max_retries=2,
        retry_backoff_s=0.5,
    )

    def opener(request, timeout):
        assert timeout == 2.0
        assert request.full_url == "http://api/api/v1/dispatch/run"
        assert request.headers["Authorization"] == "Bearer abc"
        assert json.loads(request.data.decode("utf-8")) == {"max_assignments": 3}
        return _FakeResponse({"assigned_count": 2}, status=200)

    result = worker_module.run_dispatch_once(settings, opener=opener)

    assert result.ok is True
    assert result.assigned_count == 2
    assert result.status_code == 200


def test_run_dispatch_once_http_error_returns_failure():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=None,
        auth_token=None,
        max_retries=2,
        retry_backoff_s=0.5,
    )

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=None,
        )

    result = worker_module.run_dispatch_once(settings, opener=opener)

    assert result.ok is False
    assert result.status_code == 503
    assert result.assigned_count == 0


def test_run_dispatch_with_retries_retries_retryable_errors_then_succeeds():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=None,
        auth_token=None,
        max_retries=2,
        retry_backoff_s=0.25,
    )
    sleeps: list[float] = []
    calls = {"count": 0}

    def opener(request, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.URLError("temporary network")
        return _FakeResponse({"assigned_count": 1}, status=200)

    result = worker_module.run_dispatch_with_retries(
        settings,
        opener=opener,
        sleep=lambda seconds: sleeps.append(seconds),
    )

    assert result.ok is True
    assert result.attempts == 3
    assert sleeps == [0.25, 0.5]


def test_run_dispatch_with_retries_does_not_retry_4xx():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=None,
        auth_token=None,
        max_retries=5,
        retry_backoff_s=0.25,
    )

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )

    result = worker_module.run_dispatch_with_retries(
        settings,
        opener=opener,
        sleep=lambda _seconds: None,
    )

    assert result.ok is False
    assert result.status_code == 401
    assert result.attempts == 1


def test_run_dispatch_with_retries_retries_429_then_succeeds():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=None,
        auth_token=None,
        max_retries=1,
        retry_backoff_s=0.1,
    )
    calls = {"count": 0}

    def opener(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(
                url=request.full_url,
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )
        return _FakeResponse({"assigned_count": 4}, status=200)

    result = worker_module.run_dispatch_with_retries(
        settings,
        opener=opener,
        sleep=lambda _seconds: None,
    )

    assert result.ok is True
    assert result.assigned_count == 4
    assert result.attempts == 2


def test_run_dispatch_with_retries_stops_after_max_retries():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=None,
        auth_token=None,
        max_retries=1,
        retry_backoff_s=0.1,
    )

    def opener(request, timeout):
        raise urllib.error.URLError("still-down")

    result = worker_module.run_dispatch_with_retries(
        settings,
        opener=opener,
        sleep=lambda _seconds: None,
    )

    assert result.ok is False
    assert result.error == "URLError: still-down"
    assert result.attempts == 2
