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
- `POST /api/v1/dispatch/run`
- `GET /api/v1/orders/{order_id}/pod`
- `GET /api/v1/orders/track/{public_tracking_id}`
- `GET /api/v1/jobs` (pagination: `page`, `page_size`; filter: `active`)
- `POST /api/v1/dispatch/run`
- `GET /api/v1/tracking/{public_tracking_id}`
- `GET /health`
- `GET /ready`
- `GET /metrics` (OPS/ADMIN)


Health and observability endpoints now publish explicit response schemas in OpenAPI:
- `GET /health` → `HealthResponse` (`status`)
- `GET /ready` → `ReadinessResponse` (`status`, `dependencies`), returns HTTP `200` when ready and `503` when degraded
- `GET /metrics` → `MetricsResponse` (`counters`, `timings`)

Security headers for Ops endpoints:
- `Authorization: Bearer <token>`
- `X-Wingxtra-Source: gcs`


JWT bearer required for protected endpoints.


Idempotency support:
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/orders/{order_id}/submit-mission-intent`
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/pod`
- `POST /api/v1/dispatch/run`

Provide `Idempotency-Key` header.
Replay with same payload returns same response; reused key with different payload returns `409`.


Rate limiting:
- `GET /api/v1/tracking/{public_tracking_id}` returns `429` when public tracking rate limit is exceeded.
- `GET /api/v1/orders/track/{public_tracking_id}` returns `429` when public tracking rate limit is exceeded.
- `POST /api/v1/orders` returns `429` when order creation rate limit is exceeded.
- Successful and limited responses include numeric-string `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (Unix epoch seconds); limited responses also include numeric-string `Retry-After` (delta seconds).
- OpenAPI documents these rate-limit headers on `POST /api/v1/orders`, `GET /api/v1/orders/track/{public_tracking_id}`, and `GET /api/v1/tracking/{public_tracking_id}` responses (including `429`).

Public tracking response is sanitized to: `order_id`, `public_tracking_id`, `status`, and `milestones` (timeline event types in chronological order). When proof-of-delivery exists, it also includes `pod_summary` (including at least `method`). This sanitized contract applies to both `GET /api/v1/tracking/{public_tracking_id}` and `GET /api/v1/orders/track/{public_tracking_id}`.

POD read endpoint (`GET /api/v1/orders/{order_id}/pod`) returns `PodResponse`; when no POD record exists yet, `method` is `null`.

POD create validation is method-specific: `PHOTO` requires `photo_url`, `OTP` requires `otp_code`, and `OPERATOR_CONFIRM` requires `operator_name` (invalid combinations return `400`). For backward compatibility, `confirmed_by` is accepted as an alias of `operator_name` in request payloads.



Observability headers:
- `X-Request-ID` accepted on requests and echoed on responses.


Dispatch run accepts optional JSON body `{"max_assignments": <int>}` (1-100) to cap assignments per run.
In hybrid mode, when `max_assignments` is provided, the service can combine DB-backed and placeholder assignments up to the requested cap.
Dispatch run response contains `assigned` and `assignments` list entries with `order_id` and `status`.


Manual assignment validates drone availability and battery threshold. Low-battery or unavailable drones return `400`.
Order create validation enforces optional bounds: `lat` in [-90, 90], `weight` > 0, non-empty `payload_type` (invalid values return `422`).
Dispatch run assigns at most one order per available drone and returns both `assigned` and `assignments`.

Order creation emits timeline events in order: `CREATED`, `VALIDATED`, `QUEUED`.
Manual assignment appends `ASSIGNED` after those lifecycle events.

Orders created via `POST /api/v1/orders` are persisted with UUID primary keys in the API database.
