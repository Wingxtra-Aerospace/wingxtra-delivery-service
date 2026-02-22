from fastapi import APIRouter, Response, status

from app.config import settings
from app.db.session import SessionLocal
from app.schemas.health import HealthResponse, ReadinessDependency, ReadinessResponse
from app.services.readiness_service import (
    database_dependency_status,
    redis_dependency_status,
    safe_dependency_status,
)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    summary="Readiness check",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(response: Response) -> ReadinessResponse:
    dependencies: list[ReadinessDependency] = []

    database_status = safe_dependency_status(
        "database", lambda: database_dependency_status(SessionLocal)
    )
    dependencies.append(ReadinessDependency(name="database", status=database_status))

    if settings.redis_url.strip():
        redis_status = safe_dependency_status(
            "redis",
            lambda: redis_dependency_status(
                settings.redis_url, timeout_s=settings.redis_readiness_timeout_s
            ),
        )
        dependencies.append(ReadinessDependency(name="redis", status=redis_status))

    readiness_status = "ok" if all(dep.status == "ok" for dep in dependencies) else "degraded"
    if readiness_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=readiness_status, dependencies=dependencies)
