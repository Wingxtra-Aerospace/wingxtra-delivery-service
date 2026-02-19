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
