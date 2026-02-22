from fastapi import APIRouter, Response, status

from app.config import settings
from app.db.session import SessionLocal
from app.integrations.fleet_api_client import get_fleet_api_client
from app.integrations.gcs_bridge_client import get_gcs_bridge_client
from app.schemas.health import HealthResponse, ReadinessDependency, ReadinessResponse
from app.services.readiness_service import (
    database_dependency_status,
    fleet_dependency_health_status,
    fleet_dependency_status,
    gcs_bridge_dependency_health_status,
    redis_dependency_status,
    safe_dependency_status,
)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
def health() -> HealthResponse:
    dependencies = {
        "fleet_api": fleet_dependency_health_status(get_fleet_api_client()),
        "gcs_bridge": gcs_bridge_dependency_health_status(get_gcs_bridge_client()),
    }
    return HealthResponse(status="ok", dependencies=dependencies)


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

    if settings.fleet_api_base_url.strip():
        fleet_status = safe_dependency_status(
            "fleet_api",
            lambda: fleet_dependency_status(get_fleet_api_client()),
        )
        dependencies.append(ReadinessDependency(name="fleet_api", status=fleet_status))

    readiness_status = "ok" if all(dep.status == "ok" for dep in dependencies) else "degraded"
    if readiness_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=readiness_status, dependencies=dependencies)
