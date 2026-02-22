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

        before_limited = int(time.time())
        limited = client.get("/api/v1/tracking/11111111-1111-4111-8111-111111111111")
        after_limited = int(time.time())
        assert limited.status_code == 429

        retry_after = int(limited.headers["Retry-After"])
        reset_at = int(limited.headers["X-RateLimit-Reset"])

        assert retry_after >= 1
        # Reset timestamp should not be in the past when the response is observed.
        assert reset_at >= after_limited

        # X-RateLimit-Reset should align with Retry-After despite request/response latency
        # and internal integer rounding.
        lower_bound = retry_after - 1
        upper_bound = retry_after + 2
        assert lower_bound <= reset_at - before_limited <= upper_bound
    finally:
        settings.public_tracking_rate_limit_requests = original_requests
        settings.public_tracking_rate_limit_window_s = original_window
        reset_rate_limits()
