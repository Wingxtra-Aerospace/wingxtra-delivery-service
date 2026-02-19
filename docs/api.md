# API

Base URL: `/`

## Health

### `GET /health`
Returns service health.

## Orders

### `POST /api/v1/orders`
Creates a delivery order in `CREATED` state and appends a `CREATED` delivery event.

**Request body**
- `customer_name` *(string, optional)*
- `customer_phone` *(string, optional)*
- `pickup_lat` *(float, required, -90..90)*
- `pickup_lng` *(float, required, -180..180)*
- `dropoff_lat` *(float, required, -90..90)*
- `dropoff_lng` *(float, required, -180..180)*
- `dropoff_accuracy_m` *(float, optional, >= 0)*
- `payload_weight_kg` *(float, required, > 0)*
- `payload_type` *(string, required, 1..100 chars)*
- `priority` *(enum: `NORMAL|URGENT|MEDICAL`, default `NORMAL`)*

### `GET /api/v1/orders/{order_id}`
Returns one order by UUID.

### `GET /api/v1/orders`
List orders.

Query params:
- `status` *(optional enum: `CREATED|VALIDATED|QUEUED|ASSIGNED|MISSION_SUBMITTED|LAUNCHED|ENROUTE|ARRIVED|DELIVERING|DELIVERED|CANCELED|FAILED|ABORTED`)*

### `POST /api/v1/orders/{order_id}/cancel`
Cancels an order only when state-machine transition is valid.

- **Response 200** when canceled.
- **Response 409** for invalid transition (for example from terminal states like `DELIVERED`).

### `GET /api/v1/orders/{order_id}/events`
Returns immutable timeline events for one order, ordered by event creation time (ascending).

**Response 200**
```json
{
  "items": [
    {
      "id": "...",
      "order_id": "...",
      "job_id": null,
      "type": "CREATED",
      "message": "Order created",
      "payload": {},
      "created_at": "..."
    }
  ]
}
```

## Public Tracking

### `GET /api/v1/tracking/{public_tracking_id}`
Returns public-safe tracking data.

**Response 200**
- `order_id`
- `public_tracking_id`
- `status`
- `created_at`
- `updated_at`
