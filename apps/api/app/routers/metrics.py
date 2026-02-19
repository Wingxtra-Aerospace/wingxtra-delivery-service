from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthContext, require_roles
from app.observability import metrics_store

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Observability metrics")
def metrics_endpoint(
    _auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> dict:
    snapshot = metrics_store.snapshot()
    return {"counters": snapshot.counters, "timings": snapshot.timings}
