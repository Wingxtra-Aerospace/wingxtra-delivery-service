# UI Integration Support

This document describes delivery API endpoints intended for Wingxtra Cloud GCS Ops UI integration.

## Base URL
- Local: `http://localhost:8000`

## CORS
CORS is enabled via `CORS_ALLOWED_ORIGINS` (comma-separated env var, default includes localhost UI origins).

## Endpoints

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
