RATE_LIMIT_HEADER_SCHEMA = {"type": "string", "pattern": r"^\d+$"}

RATE_LIMIT_SUCCESS_HEADERS = {
    "X-RateLimit-Limit": {
        "description": "Configured request quota for the current rate-limit window",
        "schema": RATE_LIMIT_HEADER_SCHEMA,
    },
    "X-RateLimit-Remaining": {
        "description": "Number of requests remaining in the current rate-limit window",
        "schema": RATE_LIMIT_HEADER_SCHEMA,
    },
    "X-RateLimit-Reset": {
        "description": "Unix epoch second when the current rate-limit window resets",
        "schema": RATE_LIMIT_HEADER_SCHEMA,
    },
}

RATE_LIMIT_THROTTLED_HEADERS = {
    **RATE_LIMIT_SUCCESS_HEADERS,
    "Retry-After": {
        "description": "Seconds until the client can retry the request",
        "schema": RATE_LIMIT_HEADER_SCHEMA,
    },
}


def apply_rate_limit_headers(response, *, limit: int, remaining: int, reset_at_s: int) -> None:
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_at_s)
