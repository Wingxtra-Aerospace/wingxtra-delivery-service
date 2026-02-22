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
