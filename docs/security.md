# Security

## JWT authentication

Protected API endpoints require a JWT bearer token:
- `Authorization: Bearer <jwt>`

JWT claims used by API:
- `sub` (user identity)
- `role` (`CUSTOMER`, `MERCHANT`, `OPS`, `ADMIN`)
- `source` (optional; `gcs` for Wingxtra Cloud GCS)
- `exp` (expiration timestamp)

Config:
- `JWT_SECRET`
- `ALLOWED_ROLES`

In non-test runtime (`WINGXTRA_TESTING=false`), startup fails fast if `JWT_SECRET` is left at the default value.
In non-test runtime, `JWT_SECRET` must also be at least 32 characters.

## Wingxtra Cloud GCS header integration

When JWT claim `source=gcs`, the API also validates:
- `X-Wingxtra-Source: gcs` (configurable via `GCS_AUTH_SOURCE`)

If valid, request role is mapped to `OPS`.

## RBAC matrix

- `CUSTOMER`: can cancel only their own orders (identity matched against stored order customer phone); no other protected access.
- `MERCHANT`: create order, list own orders, view/update own order details/events, and cancel own orders.
- `OPS`/`ADMIN`: all operational actions (`assign`, `cancel`, `submit mission intent`, `POD create`), jobs, and dispatch execution.

## Public tracking

`GET /api/v1/tracking/{public_tracking_id}` remains unauthenticated.

Tracking output is sanitized to:
- `order_id`
- `public_tracking_id`
- `status`
- `milestones` (event type milestones only; no internal actor/operator data)

When proof-of-delivery exists, tracking also includes:
- `pod_summary` (`method`, `created_at` only; no image/contact fields)

Rate limiting is applied per client IP:
- Public tracking (`GET /api/v1/tracking/{public_tracking_id}` and `GET /api/v1/orders/track/{public_tracking_id}`):
  - `PUBLIC_TRACKING_RATE_LIMIT_REQUESTS` (default `10`)
  - `PUBLIC_TRACKING_RATE_LIMIT_WINDOW_S` (default `60`)
- Order creation:
  - `ORDER_CREATE_RATE_LIMIT_REQUESTS` (default `1000`)
  - `ORDER_CREATE_RATE_LIMIT_WINDOW_S` (default `60`)

When limits are exceeded, the API returns `429 Too Many Requests` with `Retry-After` (delta seconds), `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (Unix epoch seconds) headers.
`X-RateLimit-Reset` is computed from the active window deadline (not by adding rounded deltas), so it stays consistent with `Retry-After` under sub-second timing and transport latency.


## Proof-of-delivery storage

For OTP-based POD submissions (`method=OTP`):
- OTP values are never stored in plaintext.
- The API stores only an HMAC-SHA256 digest using `POD_OTP_HMAC_SECRET`.
- In non-test runtime (`WINGXTRA_TESTING=false`), startup fails fast if `POD_OTP_HMAC_SECRET` is left at the default value.
- In non-test runtime, `POD_OTP_HMAC_SECRET` must be at least 32 characters.

## Idempotency

Supported endpoints:
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/orders/{order_id}/submit-mission-intent`
- `POST /api/v1/orders/{order_id}/pod`

Behavior:
- `Idempotency-Key` is optional but, when provided, replay is deterministic.
- `Idempotency-Key` values must be non-empty and at most 255 characters.
- Scope is deterministic per endpoint/user (and per-order where required).
- Replays with the same payload return the original response payload.
- Failed requests (for example upstream publish failures returning 5xx) are not recorded as idempotent successes; retrying with the same key can still execute and succeed later.
- Reusing the same key with a different payload returns `409` (`Idempotency key reused with different payload`).
- Idempotency records are persisted in the `idempotency_records` database table with TTL (`IDEMPOTENCY_TTL_S`, default `86400` seconds) and a DB-level unique constraint on `(route scope, idempotency key)`. Expired keys are purged opportunistically during idempotency checks/writes. Concurrent retries with the same scope/key are resolved safely to a single persisted record, and the first persisted response body is reused for deterministic replays.


## Test auth bypass

For automated tests only, auth bypass is controlled by `ENABLE_TEST_AUTH_BYPASS` / `settings.enable_test_auth_bypass`.
It is **not** implicitly enabled by pytest process environment variables.

## CORS

Set `CORS_ALLOWED_ORIGINS` as comma-separated origins for UI clients.
