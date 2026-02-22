RATE_LIMIT_SUCCESS_HEADERS = {
    "X-RateLimit-Limit": {
        "description": "Configured request quota for the current rate-limit window",
        "schema": {"type": "string"},
    },
    "X-RateLimit-Remaining": {
        "description": "Number of requests remaining in the current rate-limit window",
        "schema": {"type": "string"},
    },
    "X-RateLimit-Reset": {
        "description": "Unix epoch second when the current rate-limit window resets",
        "schema": {"type": "string"},
    },
}

RATE_LIMIT_THROTTLED_HEADERS = {
    **RATE_LIMIT_SUCCESS_HEADERS,
    "Retry-After": {
        "description": "Seconds until the client can retry the request",
        "schema": {"type": "string"},
    },
}
