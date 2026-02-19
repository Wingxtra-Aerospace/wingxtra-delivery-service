# AGENTS.md

## Mission
Implement the Wingxtra delivery services layer described in README.md.
Work in small PRs that are easy to review and test.

## Hard rules
- Do NOT replace Wingxtra Cloud GCS or DroneEngage control logic.
- Do NOT add GPL-licensed code.
- Keep delivery logic in the new delivery service modules.
- Every PR must include tests and update docs/ when behavior changes.
- Prefer Postgres (SQLite allowed only for local dev).

## Build & test expectations
- Add a docker-compose for local dev (db + redis if needed).
- Add CI workflow that runs lint + tests.
- All endpoints must have request/response schemas and validation.

## Milestones (do in order)
1) Repo scaffold + FastAPI app + DB migrations + Orders CRUD + public tracking.
2) Delivery event timeline + state machine enforcement.
3) Fleet API client + dispatch (auto assignment) + manual assignment endpoint.
4) Mission intent contract + mission intent generation + publish stub.
5) Proof-of-delivery module + endpoints.
6) UI pages (optional): Orders/Jobs/Tracking view + Ops console integration.
7) Hardening: auth/RBAC, idempotency, rate limiting, observability.
