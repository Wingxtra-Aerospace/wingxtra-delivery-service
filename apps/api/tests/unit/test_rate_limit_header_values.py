import time

from app.auth.dependencies import reset_rate_limits
from app.config import settings


def test_public_tracking_429_headers_are_numeric_and_time_consistent(client):
    original_requests = settings.public_tracking_rate_limit_requests
    original_window = settings.public_tracking_rate_limit_window_s
    settings.public_tracking_rate_limit_requests = 1
    settings.public_tracking_rate_limit_window_s = 60
    reset_rate_limits()

    try:
        ok = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        assert ok.status_code == 200
        assert ok.headers["X-RateLimit-Limit"].isdigit()
        assert ok.headers["X-RateLimit-Remaining"].isdigit()
        assert ok.headers["X-RateLimit-Reset"].isdigit()

        now = int(time.time())
        limited = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        assert limited.status_code == 429

        retry_after = int(limited.headers["Retry-After"])
        reset_at = int(limited.headers["X-RateLimit-Reset"])

        assert retry_after >= 1
        assert reset_at >= now
        # X-RateLimit-Reset should align with Retry-After window.
        assert reset_at - now <= retry_after + 1
    finally:
        settings.public_tracking_rate_limit_requests = original_requests
        settings.public_tracking_rate_limit_window_s = original_window
        reset_rate_limits()
