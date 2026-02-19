# API

Base URL: `/`

## Health

### `GET /health`
Returns service health.

**Response 200**
```json
{
  "status": "ok"
}
```

## Orders

### `POST /api/v1/orders`
Creates a delivery order.

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

**Response 201**
Returns the created order with:
- `id` (UUID)
- `public_tracking_id`
- `status` (currently `CREATED`)
- timestamps

### `GET /api/v1/orders/{order_id}`
Returns one order by UUID.

- **Response 200** order payload.
- **Response 404** when order does not exist.

### `GET /api/v1/orders`
List orders.

Query params:
- `status` *(optional enum `CREATED|CANCELED`)*

**Response 200**
```json
{
  "items": [
    {
      "id": "...",
      "public_tracking_id": "..."
    }
  ]
}
```

### `POST /api/v1/orders/{order_id}/cancel`
Cancels an order.

- **Response 200**
```json
{
  "id": "<order-uuid>",
  "status": "CANCELED"
}
```
- **Response 404** when order does not exist.

## Public Tracking

### `GET /api/v1/tracking/{public_tracking_id}`
Returns public-safe tracking data.

**Response 200**
- `order_id`
- `public_tracking_id`
- `status`
- `created_at`
- `updated_at`

**Response 404** when tracking id does not exist.
