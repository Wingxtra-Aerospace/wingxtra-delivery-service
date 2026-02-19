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

Rate limiting is applied per client IP for public tracking requests:
- `PUBLIC_TRACKING_RATE_LIMIT_REQUESTS`
- `PUBLIC_TRACKING_RATE_LIMIT_WINDOW_S`

## CORS

Set `CORS_ALLOWED_ORIGINS` as comma-separated origins for UI clients.


## Idempotency
Supported endpoints:
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/submit-mission-intent`

The API stores idempotency key + request hash + response payload.
