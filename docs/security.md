# Security

## Wingxtra Cloud GCS auth integration

Protected Ops endpoints accept and validate these headers:
- `Authorization: Bearer <token>`
- `X-Wingxtra-Source: <source>`

Environment variables:
- `GCS_AUTH_TOKEN` (default: `wingxtra-dev-token`)
- `GCS_AUTH_SOURCE` (default: `gcs`)

On successful validation, requests are mapped to role: `OPS`.

Protected endpoints:
- `GET /api/v1/orders`
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/orders/{order_id}/events`
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/cancel`
- `GET /api/v1/jobs`

Public unauthenticated endpoint:
- `GET /api/v1/tracking/{public_tracking_id}`

## CORS
Set `CORS_ALLOWED_ORIGINS` as comma-separated origins for external UI applications.
