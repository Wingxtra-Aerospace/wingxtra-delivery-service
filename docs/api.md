# API

OpenAPI is provided by FastAPI:
- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

Core UI integration endpoints:
- `GET /api/v1/orders` (pagination + filtering)
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/orders/{order_id}/events`
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/cancel`
- `GET /api/v1/jobs`
- `GET /api/v1/tracking/{public_tracking_id}`


Security headers for Ops endpoints:
- `Authorization: Bearer <token>`
- `X-Wingxtra-Source: gcs`
