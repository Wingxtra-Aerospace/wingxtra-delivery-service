from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthContext, require_roles
from app.db.session import get_db
from app.schemas.ui import JobResponse, JobsListResponse
from app.services.ui_service import get_job, list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobsListResponse, summary="List delivery jobs")
def list_jobs_endpoint(
    active: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    order_id: str | None = Query(default=None),
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
    db: Session = Depends(get_db),
) -> JobsListResponse:
    items, total = list_jobs(auth, db, active, page, page_size, order_id)
    return JobsListResponse(
        items=[JobResponse.model_validate(job) for job in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{job_id}", response_model=JobResponse, summary="Get delivery job detail")
def get_job_endpoint(
    job_id: str,
    auth: AuthContext = Depends(require_roles("OPS", "ADMIN")),
    db: Session = Depends(get_db),
) -> JobResponse:
    return JobResponse.model_validate(get_job(auth, db, job_id))
