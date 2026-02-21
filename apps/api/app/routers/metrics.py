from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthContext, require_backoffice_write
from app.observability import metrics_store
from app.schemas.metrics import MetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Observability metrics", response_model=MetricsResponse)
def metrics_endpoint(
    _auth: AuthContext = Depends(require_backoffice_write),
) -> MetricsResponse:
    """
    Metrics are intended for backoffice consumers and require OPS/ADMIN auth.
    The endpoint must remain stable for authorized clients and tests.
    """
    snapshot = metrics_store.snapshot()

    return MetricsResponse(
        counters=snapshot.counters or {},
        timings=snapshot.timings or {},
    )
