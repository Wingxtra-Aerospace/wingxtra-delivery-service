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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_backoffice_write),
    db: Session = Depends(get_db),
) -> JobsListResponse:
    items, total = list_jobs(auth, db, active, page, page_size)
    return JobsListResponse(
        items=[JobResponse.model_validate(job) for job in items],
        pagination={"page": page, "page_size": page_size, "total": total},
    )
