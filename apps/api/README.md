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
