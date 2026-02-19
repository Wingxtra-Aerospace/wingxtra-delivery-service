# UI Integration Support

This document describes delivery API endpoints intended for Wingxtra Cloud GCS Ops UI integration.

## Base URL
- Local: `http://localhost:8000`

## CORS
CORS is enabled via `CORS_ALLOWED_ORIGINS` (comma-separated env var, default includes localhost UI origins).

## Authentication
All Ops endpoints require JWT bearer auth.

For Wingxtra Cloud GCS requests (JWT `source=gcs`), include:
- `Authorization: Bearer <token>`
- `X-Wingxtra-Source: gcs`

Tracking endpoint remains public/unauthenticated.

## Endpoints

### Create order
`POST /api/v1/orders`

### Orders list
`GET /api/v1/orders`

Query params:
- `status` (optional)
- `search` (optional)
- `from` (optional datetime)
- `to` (optional datetime)
- `page` (default `1`)
- `page_size` (default `20`, max `100`)

### Order detail
`GET /api/v1/orders/{order_id}`

### Events timeline
`GET /api/v1/orders/{order_id}/events`

### Manual assignment
`POST /api/v1/orders/{order_id}/assign`
```json
{ "drone_id": "DRONE-12" }
```

### Cancel order
`POST /api/v1/orders/{order_id}/cancel`

### Jobs list (active deliveries)
`GET /api/v1/jobs?active=true`

### Public tracking view
`GET /api/v1/tracking/{public_tracking_id}`

## Example requests
```bash
curl "http://localhost:8000/api/v1/orders?page=1&page_size=20&search=TRK"
curl "http://localhost:8000/api/v1/jobs?active=true"
curl -X POST "http://localhost:8000/api/v1/orders/ord-1/assign" \
  -H "Content-Type: application/json" \
  -d '{"drone_id":"DRONE-12"}'
```


### Submit mission intent
`POST /api/v1/orders/{order_id}/submit-mission-intent`

Idempotent via `Idempotency-Key` header.

In test mode, placeholder order IDs such as `ord-1` and `ord-2` are accepted by assign/submit endpoints for UI smoke tests.


## Rate limiting
- Public tracking is limited per client IP via `PUBLIC_TRACKING_RATE_LIMIT_REQUESTS` and `PUBLIC_TRACKING_RATE_LIMIT_WINDOW_S` (returns `429` when exceeded).
- Order creation is limited per client IP via `ORDER_CREATE_RATE_LIMIT_REQUESTS` and `ORDER_CREATE_RATE_LIMIT_WINDOW_S` (returns `429` when exceeded).
