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


ETAG_RESPONSE_HEADER = {
    "ETag": {
        "description": "Entity tag representing the current tracking payload",
        "schema": {"type": "string"},
    }
}

CACHE_CONTROL_RESPONSE_HEADER = {
    "Cache-Control": {
        "description": "Caching policy for conditional tracking responses",
        "schema": {"type": "string"},
    }
}

TRACKING_CACHE_CONTROL_VALUE = "public, max-age=0, must-revalidate"


TRACKING_SUCCESS_HEADERS = {
    **RATE_LIMIT_SUCCESS_HEADERS,
    **ETAG_RESPONSE_HEADER,
    **CACHE_CONTROL_RESPONSE_HEADER,
}

TRACKING_NOT_MODIFIED_HEADERS = {
    **ETAG_RESPONSE_HEADER,
    **CACHE_CONTROL_RESPONSE_HEADER,
}


def apply_tracking_cache_headers(response, *, etag: str) -> None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = TRACKING_CACHE_CONTROL_VALUE
