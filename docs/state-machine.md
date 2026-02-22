# State Machine

Order states:
- `CREATED`
- `VALIDATED`
- `QUEUED`
- `ASSIGNED`
- `MISSION_SUBMITTED`
- `LAUNCHED`
- `ENROUTE`
- `ARRIVED`
- `DELIVERING`
- `DELIVERED`
- `CANCELED`
- `FAILED`
- `ABORTED`

Rules:
- Transitions are enforced in service logic.
- Invalid transitions return HTTP `409 Conflict`.
- Every successful transition appends an immutable `DeliveryEvent` entry.
- Events are exposed in timeline order via `GET /api/v1/orders/{order_id}/events`.
- Ops can ingest execution events via `POST /api/v1/orders/{order_id}/events` using `MISSION_LAUNCHED`, `ENROUTE`, `ARRIVED`, `DELIVERED`, `FAILED` (with optional timestamp).
- `DELIVERED` ingest applies `DELIVERING` and `DELIVERED` transitions atomically to keep timeline/state consistent.
