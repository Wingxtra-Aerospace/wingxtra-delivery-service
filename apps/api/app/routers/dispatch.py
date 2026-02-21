from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext, require_backoffice_write
from app.db.session import get_db
from app.schemas.ui import DispatchRunResponse
from app.services.ui_service import run_auto_dispatch

router = APIRouter(prefix="/api/v1/dispatch", tags=["dispatch"])


@router.post("/run", response_model=DispatchRunResponse, summary="Run auto dispatch")
def run_dispatch_endpoint(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_backoffice_write),
) -> DispatchRunResponse:
    result = run_auto_dispatch(auth, db)
    return DispatchRunResponse.model_validate(result)
