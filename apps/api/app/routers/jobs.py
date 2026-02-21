from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext, require_backoffice_write
from app.db.session import get_db
from app.schemas.ui import JobResponse, JobsListResponse
from app.services.ui_service import list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobsListResponse, summary="List delivery jobs")
def list_jobs_endpoint(
    active: bool = Query(default=True),
    auth: AuthContext = Depends(require_backoffice_write),
    db: Session = Depends(get_db),
) -> JobsListResponse:
    items = [JobResponse.model_validate(job) for job in list_jobs(auth, db, active)]
    return JobsListResponse(items=items)
