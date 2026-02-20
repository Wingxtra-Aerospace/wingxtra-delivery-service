from fastapi import APIRouter

from app.observability import metrics_store

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Observability metrics")
def metrics_endpoint() -> dict:
    """
    Metrics must always be available for Ops UI and tests.
    This endpoint must NEVER 400/401, even without auth headers.
    """
    snapshot = metrics_store.snapshot()

    return {
        "counters": snapshot.counters or {},
        "timings": snapshot.timings or {},
    }
