from app import config as config_module
from app.services import rate_limiter


def test_get_rate_limiter_uses_memory_when_toggle_disabled():
    original_toggle = config_module.settings.rate_limit_use_redis
    rate_limiter.reset_rate_limiter_state()
    config_module.settings.rate_limit_use_redis = False
    try:
        assert isinstance(rate_limiter.get_rate_limiter(), rate_limiter.InMemoryRateLimiter)
    finally:
        config_module.settings.rate_limit_use_redis = original_toggle
        rate_limiter.reset_rate_limiter_state()


def test_get_rate_limiter_uses_redis_when_toggle_enabled(monkeypatch):
    original_toggle = config_module.settings.rate_limit_use_redis
    original_url = config_module.settings.redis_url
    created = {}

    class StubRedisRateLimiter:
        def __init__(self, redis_url: str) -> None:
            created["url"] = redis_url

        def check(self, key: str, *, max_requests: int, window_s: int):
            raise NotImplementedError

    monkeypatch.setattr(rate_limiter, "RedisRateLimiter", StubRedisRateLimiter)
    rate_limiter.reset_rate_limiter_state()
    config_module.settings.rate_limit_use_redis = True
    config_module.settings.redis_url = "redis://localhost:6379/0"
    try:
        limiter = rate_limiter.get_rate_limiter()
        assert isinstance(limiter, StubRedisRateLimiter)
        assert created["url"] == "redis://localhost:6379/0"
    finally:
        config_module.settings.rate_limit_use_redis = original_toggle
        config_module.settings.redis_url = original_url
        rate_limiter.reset_rate_limiter_state()


def test_redis_rate_limiter_translates_eval_response(monkeypatch):
    limiter = rate_limiter.RedisRateLimiter("redis://localhost:6379/0")
    monkeypatch.setattr(limiter, "_eval", lambda *args, **kwargs: [1, 7, 1060])
    status = limiter.check("tracking:127.0.0.1", max_requests=10, window_s=60)

    assert status.allowed is True
    assert status.remaining == 7
    assert status.reset_at_s >= 1060
    assert status.reset_after_s >= 1
