# Mission Intent

Mission intent is the delivery-layer contract sent to Wingxtra Cloud for mission planning.

## Contract

Canonical schema: `shared/contracts/mission_intent_contract.json`.

Mission intent fields:
- `intent_id`: unique mission intent identifier
- `order_id`: delivery order UUID
- `drone_id`: assigned drone identifier
- `pickup`: `{lat, lng, alt_m}`
- `dropoff`: `{lat, lng, alt_m, delivery_alt_m}`
- `actions`: high-level mission action list (`TAKEOFF`, `CRUISE`, `DESCEND`, `DROP_OR_WINCH`, `ASCEND`, `RTL`)
- `constraints`: policy constraints such as minimum battery/service area
- `safety`: safety controls and fail behavior
- `metadata`: payload and request context

## Submission Flow (v1)

Endpoint: `POST /api/v1/orders/{order_id}/submit-mission-intent`

Rules:
- Order must be in `ASSIGNED` state.
- Order must have an active `delivery_job` with `assigned_drone_id`.
- Service generates mission intent payload and a new `intent_id`.
- Mission intent payload is validated against the delivery service contract schema before publish.
- Mission intent is sent through a publish stub (`gcs_bridge_client`) with no DroneEngage coupling.
- `delivery_jobs.mission_intent_id` is set from `intent_id`.
- Order transitions `ASSIGNED -> MISSION_SUBMITTED` and appends immutable timeline event.
