from fastapi import Response

from app.routers.rate_limit_headers import apply_rate_limit_headers


def test_apply_rate_limit_headers_sets_expected_values():
    response = Response()

    apply_rate_limit_headers(response, limit=10, remaining=3, reset_at_s=1_700_000_123)

    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "3"
    assert response.headers["X-RateLimit-Reset"] == "1700000123"
