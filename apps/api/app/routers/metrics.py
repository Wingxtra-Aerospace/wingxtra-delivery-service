from fastapi import APIRouter

from app.observability import metrics_store
from app.schemas.metrics import MetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Observability metrics", response_model=MetricsResponse)
def metrics_endpoint() -> MetricsResponse:
    """
    Metrics must always be available for Ops UI and tests.
    This endpoint must NEVER 400/401, even without auth headers.
    """
    snapshot = metrics_store.snapshot()

    return MetricsResponse(
        counters=snapshot.counters or {},
        timings=snapshot.timings or {},
    )
