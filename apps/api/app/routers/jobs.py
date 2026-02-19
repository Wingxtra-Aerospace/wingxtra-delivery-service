from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import AuthContext, require_gcs_ops_auth
from app.schemas.ui import JobResponse, JobsListResponse
from app.services.ui_service import list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobsListResponse, summary="List delivery jobs")
def list_jobs_endpoint(
    active: bool = Query(default=True),
    auth: AuthContext = Depends(require_gcs_ops_auth),
) -> JobsListResponse:
    _ = auth
    return JobsListResponse(items=[JobResponse.model_validate(job) for job in list_jobs(active)])
