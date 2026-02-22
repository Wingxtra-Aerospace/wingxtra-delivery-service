# Wingxtra Delivery UI (web)

Minimal React + Vite + TypeScript scaffold for Milestone 6 UI work.

## Requirements

- Node.js 18+
- npm

## Setup

```bash
cd web
npm install
```

## Run in development

```bash
npm run dev
```

Default dev server: `http://localhost:5173`

## Environment

- `VITE_API_BASE_URL` (default: `http://localhost:8000`)

To override:

```bash
cp .env.example .env
# edit .env
```

## API proxy

Vite dev server proxies backend calls to avoid local CORS friction:

- `/api/*`
- `/health`
- `/ready`
- `/metrics`

Proxy target uses `VITE_API_BASE_URL` origin.

## Auth handling (OPS/DEV token paste)

- Navigate to `/login` and paste a JWT token.
- Login is intentionally manual because backend currently has no UI login endpoint.
- JWT token storage policy:
  - in-memory (runtime)
  - `sessionStorage` (survives tab reload in same browser session)
  - **not** persisted in `localStorage`
- API requests include `Authorization: Bearer <token>` when logged in.
- On API `401`/`403`, UI clears token and redirects user back through guarded routes.

## Route access policy

- Ops pages (`/jobs`, `/ops-console`): `OPS` or `ADMIN`
- Merchant pages (`/orders`, `/tracking`): `MERCHANT` or `ADMIN`
- Unauthorized access redirects to `/login` with an explanatory message.

## Current user display

UI decodes JWT payload claims locally (without signature validation) to display:

- `sub` (user id)
- `role`
- tenant hint from `tenant_id`, `tenant`, or `merchant_id`

This is display-only and does not replace backend auth checks.


## Run tests

```bash
npm run test
```

Includes Vitest + Testing Library coverage for Orders page loading and URL/filter behavior.


## Orders page (MVP)

- Route: `/orders`
- Fetches `GET /api/v1/orders` with URL-driven filters and pagination
- Query params mirrored in URL for shareable links: `page`, `page_size`, `status`, `q`, `from`, `to`
- Row click navigates to `/orders/:orderId` detail


## Order detail page

- Route: `/orders/:orderId`
- Fetches order detail, timeline events, and POD (OPS/ADMIN)
- Includes role-gated actions (assign/cancel/ingest event/submit mission intent)
- Includes public tracking link copy button and Wingxtra GCS deep links (drone/mission when available)


## Jobs pages

- `/jobs`: paginated jobs table with URL-driven `page`, `page_size`, and `active_only` toggle (`active_only` maps to API `active`).
- `/jobs/:jobId`: fetches `GET /api/v1/jobs/{jobId}` when available, with fallback message `Job detail endpoint not available.` if not accessible.
- Job detail links back to related Order at `/orders/:orderId`.


## Public tracking page

- Route: `/tracking/:publicTrackingId` (no auth required).
- Calls only `GET /api/v1/tracking/{public_tracking_id}` from this view (no private order endpoint calls).
- Handles API `429` with user-friendly cooldown messaging to avoid hammering retries.
- Displays only fields returned by tracking API response, including optional `pod_summary`.


## Ops console page

- Route: `/ops-console` (OPS/ADMIN guarded by app routing).
- Link-out only integration: opens `https://gcs.wingxtra.com` in a new tab.
- No iframe embedding, no postMessage integration, and no token query params.
- Reusable GCS deep-link helpers are used on Order/Job detail pages for drone and mission links.


## OpenAPI Type Generation

Generate API types from FastAPI OpenAPI:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run gen:types
```

Check type generation succeeds (used in CI):

```bash
npm run gen:types:check
```

Generated file: `src/api/types.ts`
