from __future__ import annotations

import math
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config as config_module
from app.auth.dependencies import (
    RateLimitStatus,
    rate_limit_order_creation,
    rate_limit_public_tracking,
)
from app.services import rate_limiter


class FakeRedisCounterStore:
    def __init__(self) -> None:
        self._values: dict[str, tuple[int, float | None]] = {}

    def execute(self, *parts: str):
        command = parts[0]
        now = time.time()

        for key, (_, expires_at) in list(self._values.items()):
            if expires_at is not None and expires_at <= now:
                del self._values[key]

        if command == "INCR":
            key = parts[1]
            value, expires_at = self._values.get(key, (0, None))
            value += 1
            self._values[key] = (value, expires_at)
            return value

        if command == "EXPIRE":
            key = parts[1]
            ttl_s = int(parts[2])
            value, _ = self._values.get(key, (0, None))
            self._values[key] = (value, now + ttl_s)
            return 1

        raise AssertionError(f"Unsupported fake redis command: {parts}")


def _build_public_tracking_app() -> FastAPI:
    app = FastAPI()

    @app.get("/tracking/{tracking_id}")
    def tracking_endpoint(
        tracking_id: str,
        _rate_limit: RateLimitStatus = Depends(rate_limit_public_tracking),
    ):
        return {"ok": True}

    return app


def _build_create_order_app() -> FastAPI:
    app = FastAPI()

    @app.post("/orders")
    def create_order(_rate_limit: RateLimitStatus = Depends(rate_limit_order_creation)):
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset_state():
    rate_limiter.reset_rate_limiter_state()
    yield
    rate_limiter.reset_rate_limiter_state()


def test_get_rate_limiter_uses_memory_when_backend_is_memory():
    original_backend = config_module.settings.rate_limit_backend
    rate_limiter.reset_rate_limiter_state()
    config_module.settings.rate_limit_backend = "memory"
    try:
        assert isinstance(rate_limiter.get_rate_limiter(), rate_limiter.InMemoryRateLimiter)
    finally:
        config_module.settings.rate_limit_backend = original_backend


def test_get_rate_limiter_uses_redis_when_backend_is_redis(monkeypatch):
    original_backend = config_module.settings.rate_limit_backend
    original_url = config_module.settings.redis_url
    created = {}

    class StubRedisRateLimiter:
        def __init__(self, redis_url: str) -> None:
            created["url"] = redis_url

        def check(self, key: str, *, max_requests: int, window_s: int):
            raise NotImplementedError

    monkeypatch.setattr(rate_limiter, "RedisRateLimiter", StubRedisRateLimiter)
    rate_limiter.reset_rate_limiter_state()
    config_module.settings.rate_limit_backend = "redis"
    config_module.settings.redis_url = "redis://localhost:6379/0"
    try:
        limiter = rate_limiter.get_rate_limiter()
        assert isinstance(limiter, StubRedisRateLimiter)
        assert created["url"] == "redis://localhost:6379/0"
    finally:
        config_module.settings.rate_limit_backend = original_backend
        config_module.settings.redis_url = original_url


def test_redis_counters_persist_across_two_test_clients(monkeypatch):
    original_backend = config_module.settings.rate_limit_backend
    original_url = config_module.settings.redis_url
    original_limit = config_module.settings.public_tracking_rate_limit_requests
    original_window = config_module.settings.public_tracking_rate_limit_window_s

    store = FakeRedisCounterStore()
    monkeypatch.setattr(
        rate_limiter.RedisClient, "execute", lambda _self, *parts: store.execute(*parts)
    )

    config_module.settings.rate_limit_backend = "redis"
    config_module.settings.redis_url = "redis://shared-redis:6379/0"
    config_module.settings.public_tracking_rate_limit_requests = 1
    config_module.settings.public_tracking_rate_limit_window_s = 60

    app_one = _build_public_tracking_app()
    app_two = _build_public_tracking_app()
    try:
        with TestClient(app_one) as client_one:
            first = client_one.get("/tracking/public-1")
            assert first.status_code == 200

        with TestClient(app_two) as client_two:
            second = client_two.get("/tracking/public-1")
            assert second.status_code == 429
    finally:
        config_module.settings.rate_limit_backend = original_backend
        config_module.settings.redis_url = original_url
        config_module.settings.public_tracking_rate_limit_requests = original_limit
        config_module.settings.public_tracking_rate_limit_window_s = original_window


def test_redis_unavailable_fails_closed_for_public_tracking(monkeypatch):
    original_backend = config_module.settings.rate_limit_backend
    original_url = config_module.settings.redis_url

    def _raise_unavailable(_self, *parts):
        raise rate_limiter.RateLimiterBackendUnavailable("down")

    monkeypatch.setattr(rate_limiter.RedisClient, "execute", _raise_unavailable)

    config_module.settings.rate_limit_backend = "redis"
    config_module.settings.redis_url = "redis://shared-redis:6379/0"

    app = _build_public_tracking_app()
    try:
        with TestClient(app) as client:
            response = client.get("/tracking/public-1")
            assert response.status_code == 429
    finally:
        config_module.settings.rate_limit_backend = original_backend
        config_module.settings.redis_url = original_url


def test_redis_unavailable_fails_open_for_authenticated_endpoint(monkeypatch):
    original_backend = config_module.settings.rate_limit_backend
    original_url = config_module.settings.redis_url

    def _raise_unavailable(_self, *parts):
        raise rate_limiter.RateLimiterBackendUnavailable("down")

    monkeypatch.setattr(rate_limiter.RedisClient, "execute", _raise_unavailable)

    config_module.settings.rate_limit_backend = "redis"
    config_module.settings.redis_url = "redis://shared-redis:6379/0"

    app = _build_create_order_app()
    try:
        with TestClient(app) as client:
            response = client.post("/orders")
            assert response.status_code == 200
    finally:
        config_module.settings.rate_limit_backend = original_backend
        config_module.settings.redis_url = original_url


def test_redis_rate_limiter_uses_fixed_window_counter(monkeypatch):
    limiter = rate_limiter.RedisRateLimiter("redis://localhost:6379/0")
    observed: list[tuple[str, ...]] = []

    def fake_execute(*parts: str):
        observed.append(parts)
        if parts[0] == "INCR":
            return 1
        if parts[0] == "EXPIRE":
            return 1
        raise AssertionError(parts)

    monkeypatch.setattr(limiter._client, "execute", fake_execute)
    monkeypatch.setattr("time.time", lambda: 1_000.25)

    status = limiter.check("tracking:127.0.0.1", max_requests=10, window_s=60)

    assert status.allowed is True
    assert status.remaining == 9
    assert status.reset_at_s == math.ceil((math.floor(1_000.25 / 60) + 1) * 60)
    assert observed[0][0] == "INCR"
    assert observed[1][0] == "EXPIRE"
