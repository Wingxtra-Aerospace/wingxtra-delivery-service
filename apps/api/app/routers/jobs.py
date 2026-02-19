from fastapi import APIRouter, Query

from app.schemas.ui import JobResponse, JobsListResponse
from app.services.ui_service import list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobsListResponse, summary="List delivery jobs")
def list_jobs_endpoint(active: bool = Query(default=True)) -> JobsListResponse:
    return JobsListResponse(items=[JobResponse.model_validate(job) for job in list_jobs(active)])
