from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthContext, require_roles
from app.schemas.ui import DispatchRunResponse
from app.services.ui_service import run_auto_dispatch

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])


@router.post("/run", response_model=DispatchRunResponse, summary="Run auto dispatch")
def run_dispatch_endpoint(
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
) -> DispatchRunResponse:
    result = run_auto_dispatch(auth)
    return DispatchRunResponse(**result)
