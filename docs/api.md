# API

Base URL: `/`

## Health

### `GET /health`
Returns service health.

## Orders

### `POST /api/v1/orders`
Creates a delivery order in `CREATED` state and appends a `CREATED` delivery event.

### `GET /api/v1/orders/{order_id}`
Returns one order by UUID.

### `GET /api/v1/orders`
List orders.

Query params:
- `status` *(optional enum: `CREATED|VALIDATED|QUEUED|ASSIGNED|MISSION_SUBMITTED|LAUNCHED|ENROUTE|ARRIVED|DELIVERING|DELIVERED|CANCELED|FAILED|ABORTED`)*

### `POST /api/v1/orders/{order_id}/cancel`
Cancels an order only when state-machine transition is valid.

### `POST /api/v1/orders/{order_id}/assign`
Manually assigns a drone to an order.

**Request body**
```json
{
  "drone_id": "DRONE-123"
}
```

Behavior:
- Order is prepared through `CREATED -> VALIDATED -> QUEUED` when needed.
- Drone must be available and have battery >= 30% from Fleet API.
- On success, order transitions to `ASSIGNED`, assignment job is created, and event timeline is appended.


### `POST /api/v1/orders/{order_id}/submit-mission-intent`
Generates mission intent for an assigned order, publishes via stub bridge client, stores `mission_intent_id` on the active delivery job, and transitions order to `MISSION_SUBMITTED`.

- **Response 200**
```json
{
  "order_id": "<uuid>",
  "mission_intent_id": "mi_...",
  "status": "MISSION_SUBMITTED"
}
```
- **Response 409** when order is not in `ASSIGNED` state or no active job exists.

### `GET /api/v1/orders/{order_id}/events`
Returns immutable timeline events for one order, ordered by event creation time (ascending).

## Dispatch

### `POST /api/v1/dispatch/run`
Runs automatic dispatch for dispatchable orders (`CREATED`, `VALIDATED`, `QUEUED`).

Behavior:
- Reads latest drone telemetry from Fleet API (`GET /api/v1/telemetry/latest` on Fleet API service).
- Filters to available drones with battery >= 30%.
- Scores candidates by pickup distance (with minor battery bonus) and assigns best drone.
- Creates `delivery_jobs` records and appends state transition events (`VALIDATED`, `QUEUED`, `ASSIGNED`) as needed.

**Response 200**
```json
{
  "assignments": [
    {
      "order_id": "<uuid>",
      "assigned_drone_id": "DRONE-123"
    }
  ]
}
```

## Public Tracking

### `GET /api/v1/tracking/{public_tracking_id}`
Returns public-safe tracking data.
