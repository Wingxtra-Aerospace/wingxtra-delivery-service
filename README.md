# wingxtra-delivery-service
Wingxtra Delivery Platform — Powering Wingxtra’s drone delivery services, built on our proprietary Cloud GCS and DroneEngage fleet stack. It handles customer orders, GPS drop-offs, dispatch, drone assignment, mission intent translation, tracking, and proof-of-delivery for real UAV operations.

# Wingxtra Delivery Service (Monorepo)

This repository is the **monorepo** for Wingxtra’s drone delivery vertical.  
It adds the **delivery business layer** (orders → dispatch → mission intent → tracking → proof-of-delivery) **on top of** Wingxtra’s existing stack:

- **Wingxtra Cloud GCS** (operator UI / command & control)
- **DroneEngage** (vehicle gateway + mission execution)
- **Wingxtra Fleet API** (telemetry ingestion + latest drone positions/health)

> **Important:** The delivery layer must NOT replace Wingxtra Cloud GCS or DroneEngage.  
> It should consume fleet state and publish delivery intents + events.

---

## Goals

### Must support (MVP → Production)
- Customer order creation (pickup/dropoff, payload, priority)
- Customer GPS dropoff capture (client-provided coordinates + accuracy + timestamp)
- Ops/merchant order management (view, assign, cancel, reschedule)
- Drone assignment (auto + manual override)
- Delivery mission intent generation (high-level mission description)
- Status lifecycle + delivery events timeline
- Customer tracking endpoint (public read-only link)
- Proof of delivery (POD): photo/signature/OTP or operator confirmation + metadata
- Auditable logs of decisions and state transitions

---

## Architecture Summary

### Layering
1) **Delivery Services Layer (this repo)**
   - Orders, dispatch, tracking, POD, event log, policies.
2) **C2 Layer (existing)**
   - Wingxtra Cloud GCS remains the operator console and source of truth for missions.
3) **Vehicle Layer (existing)**
   - DroneEngage executes missions and produces telemetry/events.

### Data Flow (high level)
- Customer/merchant places order → Delivery Service stores order.
- Dispatch selects drone using fleet status (from Fleet API).
- Delivery Service creates **Delivery Mission Intent**.
- Wingxtra Cloud GCS / mission bridge translates intent → real mission plan for DroneEngage.
- Telemetry/events update delivery state → customer tracking + ops timeline.

---

## Recommended Tech Choices

This monorepo is intended to be **Python-first for backend** (FastAPI), and **React** for UI modules.

- Backend API: **FastAPI + Pydantic**
- DB: **PostgreSQL** (SQLite allowed for local dev only)
- Migrations: **Alembic**
- Async jobs: **Celery + Redis** (or RQ) for dispatch/ETA updates/retries
- API docs: OpenAPI (FastAPI auto)
- Containerization: Docker Compose for local dev

> Codex: implement incrementally, each PR must include tests + docs updates.

---

## Repository Structure

wingxtra-delivery-service/
README.md

docs/
architecture.md
api.md
state-machine.md
mission-intent.md
security.md
operations.md

apps/
api/ # FastAPI application (core backend)
app/
main.py
config.py
logging.py


db/
      session.py
      base.py
      migrations/             # Alembic migrations

    models/                   # ORM models (SQLAlchemy)
      order.py
      delivery_job.py
      delivery_event.py
      proof_of_delivery.py
      drone.py                # optional cached drone registry
      user.py                 # optional if auth added here

    schemas/                  # Pydantic schemas
      order.py
      dispatch.py
      tracking.py
      events.py
      pod.py

    services/                 # business logic
      orders_service.py
      dispatch_service.py
      mission_intent_service.py
      tracking_service.py
      pod_service.py
      policy_service.py        # battery thresholds, service areas, SLAs

    integrations/             # external service clients
      fleet_api_client.py      # reads latest telemetry + drone health
      gcs_bridge_client.py     # publish mission intents to Wingxtra Cloud (optional)
      notifications_client.py  # SMS/WhatsApp/email (optional)

    routers/                  # API route modules
      health.py
      orders.py
      dispatch.py
      tracking.py
      events.py
      pod.py

    auth/                     # optional auth + RBAC
      dependencies.py
      rbac.py
      tokens.py

  tests/
    unit/
    integration/
    conftest.py

web/                          # optional: Delivery UI (React)
  README.md
  src/
  package.json
  
workers/
dispatch_worker/ # background jobs
tasks.py
worker.py

shared/
contracts/ # shared JSON schemas + enums (language-agnostic)
order_contract.json
telemetry_contract.json
mission_intent_contract.json
delivery_event_contract.json
  
utils/
  geo.py
  time.py
  ids.py

  infra/
docker-compose.yml
nginx/
scripts/

.github/
workflows/
ci.yml
lint.yml
test.yml


You may simplify the tree initially (MVP) but keep the boundaries consistent.

---

## Core Domain Concepts (Data Model)

### Order
Represents the customer request.

Fields (minimum):
- `id` (UUID)
- `public_tracking_id` (short string)
- `customer_name`, `customer_phone` (optional if anonymous)
- `pickup_lat`, `pickup_lng`
- `dropoff_lat`, `dropoff_lng`
- `dropoff_accuracy_m` (optional)
- `payload_weight_kg`, `payload_type`
- `priority` (NORMAL, URGENT, MEDICAL)
- `status` (see state machine)
- timestamps: `created_at`, `updated_at`

### DeliveryJob
Represents execution attempt for an Order.
- `order_id`
- `assigned_drone_id`
- `mission_intent_id`
- `eta_seconds` (optional)
- `status`

### DeliveryEvent
Immutable timeline events for audit + UI.
- `order_id`
- `job_id` (optional)
- `type` (CREATED, ASSIGNED, LAUNCHED, ENROUTE, ARRIVED, DELIVERING, DELIVERED, FAILED, ABORTED, CANCELED)
- `message`
- `payload` (JSON)
- `created_at`

### ProofOfDelivery (POD)
- `order_id`
- `method` (PHOTO, OTP, SIGNATURE, OPERATOR_CONFIRM)
- `photo_url` (optional)
- `otp_hash` (optional)
- `confirmed_by` (optional)
- `metadata` (JSON)
- `created_at`

### Drone (optional registry)
For capability constraints:
- `drone_id`
- `max_payload_kg`
- `home_lat`, `home_lng` (optional)
- `active` (bool)

> Drone live state should come from Fleet API telemetry, not stored as truth here.

---

## Delivery State Machine (Authoritative)

States (suggested):
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
- Terminal: `CANCELED`, `FAILED`, `ABORTED`

Rules:
- State transitions must be atomic and logged to `DeliveryEvent`.
- A delivery can have multiple jobs (retries) but only one active job.

Documentation: `docs/state-machine.md`

---

## Mission Intent Contract (Delivery → GCS)

The delivery service generates a **mission intent** rather than raw waypoint plans.

MissionIntent minimal structure:
- `intent_id`
- `order_id`
- `drone_id`
- `pickup`: {lat,lng,alt_m}
- `dropoff`: {lat,lng,alt_m, delivery_alt_m}
- `actions`: [TAKEOFF, CRUISE, DESCEND, DROP_OR_WINCH, ASCEND, RTL]
- `constraints`: battery_min_pct, geofence_id/service_area_id, max_wind_mps (optional)
- `safety`: abort_rtl_on_fail, loiter_timeout_s, lost_link_behavior
- `metadata`: payload, priority, timestamps

Documentation: `docs/mission-intent.md` + `shared/contracts/mission_intent_contract.json`

---

## Fleet API Integration (Read-only)

Delivery service must query Fleet API for drone readiness.

Expected Fleet API usage:
- `GET /api/v1/telemetry/latest` -> list of drones with latest:
  - lat/lng/alt
  - battery
  - airspeed/groundspeed
  - mode/armed
  - link quality
  - timestamp
- (optional) `GET /api/v1/telemetry/{drone_id}/latest`

Delivery service uses this to compute:
- nearest drone to pickup
- battery sufficiency (distance estimate)
- availability (not already on a mission; can be inferred or provided)

---

## Public Tracking

Tracking must be safe for public use:
- `GET /api/v1/tracking/{public_tracking_id}`
  returns:
  - status
  - last known drone position (optional / rate-limited)
  - ETA (optional)
  - event milestones (sanitized)
  - proof-of-delivery summary when delivered

Do NOT expose:
- operator identity
- internal drone IDs (unless masked)
- internal coordinates beyond what is needed

---

## API Endpoints (MVP)

### Health
- `GET /health`

### Orders
- `POST /api/v1/orders`
- `GET /api/v1/orders/{id}`
- `GET /api/v1/orders?status=&from=&to=&q=`
- `POST /api/v1/orders/{id}/cancel`
- `PATCH /api/v1/orders/{id}` (limited: dropoff, phone, priority)

### Dispatch
- `POST /api/v1/dispatch/run` (assign queued orders)
- `POST /api/v1/orders/{id}/assign` (manual assign)

### Mission Intents
- `POST /api/v1/orders/{id}/submit-mission-intent` (creates + publishes intent)

### Events
- `GET /api/v1/orders/{id}/events`

### Proof of Delivery
- `POST /api/v1/orders/{id}/pod`

### Tracking (Public)
- `GET /api/v1/tracking/{public_tracking_id}`

Documentation: `docs/api.md`

---

## Security & Roles (Phase 2)

Roles:
- `CUSTOMER` (public tracking only)
- `MERCHANT` (create/view their orders)
- `OPS` (dispatch, assign, cancel, override)
- `ADMIN` (system settings)

Use JWT auth or API keys initially.
Document in `docs/security.md`.

---

## Development Workflow (for Codex)

### Principles
- Small PRs, each PR must include:
  - tests
  - updated docs in `/docs`
  - migration if schema changes
- Never break existing telemetry ingestion stack.

### Suggested Milestones
1) DB schema + Orders API + public tracking ID
2) Events timeline + state machine enforcement
3) Fleet API client + Dispatch (auto assignment)
4) Mission intent generation + publish stub (no vehicle coupling yet)
5) Proof of Delivery
6) UI pages in Wingxtra Cloud GCS (if integrated)
7) Hardening: auth, rate limits, idempotency keys, observability

---

## Local Development

### Requirements
- Python 3.11+
- Docker + Docker Compose

### Start (example)
1) `docker compose up -d`
2) `cd apps/api`
3) `pip install -r requirements.txt`
4) `alembic upgrade head`
5) `uvicorn app.main:app --reload --port 8000`

### Test commands
- From repo root: `pytest -q`
- From API module: `cd apps/api && pytest -q`

### UI (Milestone 6 scaffold)
- Install: `cd web && npm install`
- Run dev server: `cd web && npm run dev`
- Build: `cd web && npm run build`
- API base URL env: `VITE_API_BASE_URL` (defaults to `http://localhost:8000`)
- Auth flow: use `/login` to paste JWT (OPS/DEV path); token is stored in memory + `sessionStorage` only, never `localStorage`
- Route guards: ops routes require `OPS/ADMIN`; merchant routes require `MERCHANT/ADMIN`

---

## License & Attribution
This repo is proprietary to Wingxtra unless stated otherwise.
If any third-party code is vendored, include:
- original LICENSE file
- attribution in `docs/third_party.md`

---

## What Codex Should NOT Do
- Do not replace Wingxtra Cloud GCS mission control logic.
- Do not bypass DroneEngage safety and failsafes.
- Do not store sensitive customer PII without basic access controls.

---

## Next Step
Start with Milestone 1: Orders + DB schema + tracking endpoint + tests.
Update this README as structure evolves.
