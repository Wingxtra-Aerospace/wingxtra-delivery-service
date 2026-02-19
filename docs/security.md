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
- `OPS`: full operations (list orders, order detail/events, assign, cancel, jobs).
- `ADMIN`: all OPS permissions.

## Public tracking

`GET /api/v1/tracking/{public_tracking_id}` remains unauthenticated.

Tracking output is sanitized to:
- `order_id`
- `public_tracking_id`
- `status`

Rate limiting is applied per client IP:
- Public tracking (stricter defaults):
  - `PUBLIC_TRACKING_RATE_LIMIT_REQUESTS` (default `10`)
  - `PUBLIC_TRACKING_RATE_LIMIT_WINDOW_S` (default `60`)
- Order creation:
  - `ORDER_CREATE_RATE_LIMIT_REQUESTS` (default `5`)
  - `ORDER_CREATE_RATE_LIMIT_WINDOW_S` (default `60`)

When limits are exceeded, the API returns `429 Too Many Requests`.

## CORS

Set `CORS_ALLOWED_ORIGINS` as comma-separated origins for UI clients.


## Idempotency
Supported endpoints:
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/submit-mission-intent`

The API stores idempotency key + request hash + response payload.


## Test-only auth bypass

For automated pytest runs, protected endpoints support a test bypass path so validation and business behavior can be asserted without attaching JWT headers on every request. This bypass activates when `PYTEST_CURRENT_TEST` is present or when `ENABLE_TEST_AUTH_BYPASS=true`.
