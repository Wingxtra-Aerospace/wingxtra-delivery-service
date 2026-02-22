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

## Wingxtra Cloud GCS header integration

When JWT claim `source=gcs`, the API also validates:
- `X-Wingxtra-Source: gcs` (configurable via `GCS_AUTH_SOURCE`)

If valid, request role is mapped to `OPS`.

## RBAC matrix

- `CUSTOMER`: no protected endpoint access; can use public tracking only.
- `MERCHANT`: create order, list own orders, view own order details/events.
- `OPS`/`ADMIN`: all write actions (`assign`, `cancel`, `submit mission intent`, `POD create`), jobs, and dispatch execution.

Write endpoints now use a strict backoffice check and return `403` with `Write action requires OPS/ADMIN` when a merchant/customer token attempts a mutating ops action.

## Public tracking

`GET /api/v1/tracking/{public_tracking_id}` remains unauthenticated.

Tracking output is sanitized to:
- `order_id`
- `public_tracking_id`
- `status`

When proof-of-delivery exists, tracking also includes:
- `pod_summary` (with at least `method`)

Rate limiting is applied per client IP:
- Public tracking (`GET /api/v1/tracking/{public_tracking_id}` and `GET /api/v1/orders/track/{public_tracking_id}`):
  - `PUBLIC_TRACKING_RATE_LIMIT_REQUESTS` (default `10`)
  - `PUBLIC_TRACKING_RATE_LIMIT_WINDOW_S` (default `60`)
- Order creation:
  - `ORDER_CREATE_RATE_LIMIT_REQUESTS` (default `1000`)
  - `ORDER_CREATE_RATE_LIMIT_WINDOW_S` (default `60`)

When limits are exceeded, the API returns `429 Too Many Requests`.


## Proof-of-delivery storage

For OTP-based POD submissions (`method=OTP`):
- OTP values are never stored in plaintext.
- The API stores only an HMAC-SHA256 digest using `POD_OTP_HMAC_SECRET`.

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
- Reusing the same key with a different payload returns `409` (`Idempotency key reused with different payload`).
- Idempotency records are persisted in the `idempotency_records` database table with TTL (`IDEMPOTENCY_TTL_S`, default `86400` seconds). Expired keys are purged opportunistically during idempotency checks/writes. Concurrent retries with the same scope/key are resolved safely to a single persisted record.


## Test auth bypass

For automated tests only, auth bypass is controlled by `ENABLE_TEST_AUTH_BYPASS` / `settings.enable_test_auth_bypass`.
It is **not** implicitly enabled by pytest process environment variables.

## CORS

Set `CORS_ALLOWED_ORIGINS` as comma-separated origins for UI clients.
