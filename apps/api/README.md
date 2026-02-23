# API App

FastAPI backend scaffold for Wingxtra delivery service.

## Prerequisites

- Python 3.11+

## Local setup

```bash
cd apps/api
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run API locally

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Run checks

```bash
cd apps/api
source .venv/bin/activate
ruff format .
ruff check .
pytest
```


## Database migrations

Apply migrations:

```bash
cd apps/api
alembic -c alembic.ini upgrade head
```

Runtime schema controls:

- `AUTO_CREATE_SCHEMA` (default: `false`) allows `create_all` only for non-production local/dev bootstraps.
- `REQUIRE_MIGRATIONS` (optional) forces startup check against Alembic head.
- In `APP_MODE=production`, startup enforces `AUTO_CREATE_SCHEMA=false` and `REQUIRE_MIGRATIONS=true`.

Docker image startup uses `apps/api/scripts/entrypoint.sh`, which runs migrations before uvicorn.
