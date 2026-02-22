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
- `POST /api/v1/orders/{order_id}/events` (OPS/ADMIN internal mission execution ingest)
- `POST /api/v1/orders/{order_id}/assign`
- `POST /api/v1/orders/{order_id}/cancel`
- `POST /api/v1/orders/{order_id}/pod`
- `POST /api/v1/dispatch/run`
- `GET /api/v1/orders/{order_id}/pod`
- `GET /api/v1/orders/track/{public_tracking_id}`
- `GET /api/v1/jobs` (pagination: `page`>=1, `page_size` 1-100; filters: `active`, `order_id`; ordered newest-first)
- `GET /api/v1/jobs/{job_id}` (`404` when missing/invalid job id, backoffice roles only)
- `GET /api/v1/tracking/{public_tracking_id}`
- `GET /health`
- `GET /ready`
- `GET /metrics` (OPS/ADMIN)



Pagination contract for list endpoints is standardized as a generic `Page[T]` shape:
- `items`: array of resource objects
- `page`: current page number
- `page_size`: requested page size
- `total`: total number of matching records
- `pagination`: backward-compatible nested object (`{page, page_size, total}`) retained for legacy clients

Applied to:
- `GET /api/v1/orders`
- `GET /api/v1/jobs`
- `GET /api/v1/orders/{order_id}/events` (also supports `page` and `page_size`)

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
- Set `RATE_LIMIT_BACKEND=redis` and `REDIS_URL=redis://...` to enforce limits across replicas; default behavior is `memory` in tests and `redis` in non-test runtime.
- `APP_MODE` controls demo gating: `demo|pilot|production` (recommended production value: `production`). In production mode, placeholder/non-UUID order IDs are rejected and DB-backed-only paths are enforced.

Public tracking response is sanitized to: `order_id`, `public_tracking_id`, `status`, and `milestones` (timeline event types in chronological order). When proof-of-delivery exists, it includes `pod_summary` with only `method` and `created_at`. Merchant/customer contact fields and POD `photo_url` are redacted from public tracking responses. This sanitized contract applies to both `GET /api/v1/tracking/{public_tracking_id}` and `GET /api/v1/orders/track/{public_tracking_id}`.

Both public tracking endpoints now return an `ETag` header and support conditional GET via `If-None-Match`; unchanged tracking payloads return `304 Not Modified` with an empty body. Weak validators (`W/`) and comma-separated tag lists are accepted, and `*` is treated as a wildcard match. OpenAPI documents `ETag` and `Cache-Control` on `200` and `304` responses for both tracking routes, and runtime responses use `Cache-Control: public, max-age=0, must-revalidate`.

POD read endpoint (`GET /api/v1/orders/{order_id}/pod`) returns `PodResponse`; when no POD record exists yet, `method` is `null`.

POD create validation is method-specific: `PHOTO` requires `photo_url`, `OTP` requires `otp_code`, and `OPERATOR_CONFIRM` requires `operator_name` (invalid combinations return `400`). For backward compatibility, `confirmed_by` is accepted as an alias of `operator_name` in request payloads.



Observability headers:
- `X-Request-ID` accepted on requests and echoed on responses.


Dispatch run accepts optional JSON body `{"max_assignments": <int>}` (1-100) to cap assignments per run.
In hybrid mode, when `max_assignments` is provided, the service can combine DB-backed and placeholder assignments up to the requested cap.
Dispatch run response contains `assigned` and `assignments` list entries with `order_id` and `status`.
Jobs list item schema includes `eta_seconds` (nullable integer) for ETA visibility.


Manual assignment validates availability, battery, payload constraints (`max_payload_kg`, `payload_type`), and pickup service area; incompatible drones return `400` with a specific reason.
Dispatch scoring weights are configurable via `WINGXTRA_DISPATCH_SCORE_DISTANCE_WEIGHT` and `WINGXTRA_DISPATCH_SCORE_BATTERY_WEIGHT`.
Order create validation enforces optional bounds: `lat` in [-90, 90], `weight` > 0, non-empty `payload_type` (invalid values return `422`).
Dispatch run assigns at most one order per available drone and returns both `assigned` and `assignments`.

Mission execution ingest endpoint accepts `MISSION_LAUNCHED`, `ENROUTE`, `ARRIVED`, `DELIVERED`, and `FAILED` with optional `occurred_at` timestamp (aliases: `event`/`type`, `timestamp`).
Mission execution ingest supports optional idempotency markers `source` (default `ops_event_ingest`) and `event_id`; duplicates by `(order_id, source, event_id)` or `(order_id, source, event_type, occurred_at)` are treated as replay-safe no-ops.
State-machine validation is enforced (`409` on invalid/backward transition).
`DELIVERED` automatically applies `DELIVERING -> DELIVERED` so timeline progression remains auditable.

Order creation emits timeline events in order: `CREATED`, `VALIDATED`, `QUEUED`.
Manual assignment appends `ASSIGNED` after those lifecycle events.

Orders created via `POST /api/v1/orders` are persisted with UUID primary keys in the API database.
