import pytest
from fastapi import HTTPException

from app.auth.dependencies import _apply_rate_limit, reset_rate_limits


@pytest.fixture(autouse=True)
def _reset_buckets_after_test():
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_apply_rate_limit_success_uses_consistent_reset_fields(monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_000.25)

    status = _apply_rate_limit("tracking:test", max_requests=2, window_s=60, detail="limit")

    assert status.limit == 2
    assert status.remaining == 1
    assert status.reset_after_s == 60
    assert status.reset_at_s == 1061


def test_apply_rate_limit_rejection_uses_deadline_based_reset(monkeypatch):
    times = iter((1_000.25, 1_000.35))
    monkeypatch.setattr("time.time", lambda: next(times))

    _apply_rate_limit("tracking:test", max_requests=1, window_s=60, detail="limit")

    with pytest.raises(HTTPException) as exc_info:
        _apply_rate_limit("tracking:test", max_requests=1, window_s=60, detail="limit")

    err = exc_info.value
    assert err.status_code == 429
    assert err.headers is not None
    assert err.headers["Retry-After"] == "60"
    assert err.headers["X-RateLimit-Reset"] == "1061"
