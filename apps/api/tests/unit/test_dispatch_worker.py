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


def test_load_settings_rejects_invalid_interval():
    with pytest.raises(ValueError, match="INTERVAL"):
        worker_module.load_settings({"WINGXTRA_DISPATCH_WORKER_INTERVAL_S": "0"})


def test_run_dispatch_once_success_with_max_assignments():
    settings = worker_module.DispatchWorkerSettings(
        api_base_url="http://api",
        interval_s=10,
        timeout_s=2.0,
        max_assignments=3,
        auth_token="abc",
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
