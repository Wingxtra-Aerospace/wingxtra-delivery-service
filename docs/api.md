# API

OpenAPI is provided by FastAPI:
- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

Core UI integration endpoints:
- `POST /api/v1/orders`
- `GET /api/v1/orders` (pagination + filtering)
- `GET /api/v1/orders/{order_id}`
- `PATCH /api/v1/orders/{order_id}` (limited: `customer_phone`, `dropoff_lat/dropoff_lng`, `priority`)
- `GET /api/v1/orders/{order_id}/events`
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/orders/{order_id}/pod`
- `GET /api/v1/jobs`
- `POST /api/v1/dispatch/run`
- `GET /api/v1/tracking/{public_tracking_id}`
- `GET /metrics` (OPS/ADMIN only)


Security headers for Ops endpoints:
- `Authorization: Bearer <token>`
- `X-Wingxtra-Source: gcs`


JWT bearer required for protected endpoints.


Idempotency support:
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/submit-mission-intent`

Provide `Idempotency-Key` header.
Replay with same payload returns same response; reused key with different payload returns `409`.


Rate limiting:
- `GET /api/v1/tracking/{public_tracking_id}` returns `429` when public tracking rate limit is exceeded.
- `POST /api/v1/orders` returns `429` when order creation rate limit is exceeded.

Public tracking response is sanitized to: `order_id`, `public_tracking_id`, `status`. When proof-of-delivery exists, it also includes `pod_summary` (including at least `method`).


Observability headers:
- `X-Request-ID` accepted on requests and echoed on responses.


Dispatch run response contains `assigned` and `assignments` list entries with `order_id` and `status`.


Manual assignment validates drone availability and battery threshold. Low-battery or unavailable drones return `400`.
Order create validation enforces optional bounds: `lat` in [-90, 90], `weight` > 0, non-empty `payload_type` (invalid values return `422`).
Dispatch run assigns at most one order per available drone and returns both `assigned` and `assignments`.

Order creation emits timeline events in order: `CREATED`, `VALIDATED`, `QUEUED`.
Manual assignment appends `ASSIGNED` after those lifecycle events.

Orders created via `POST /api/v1/orders` are persisted with UUID primary keys in the API database.
