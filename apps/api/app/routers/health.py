from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.observability import log_event
from app.schemas.health import HealthResponse, ReadinessDependency, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", summary="Readiness check", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    try:
        database_status = _database_dependency_status(SessionLocal)
    except Exception:
        log_event("readiness_dependency_check_failed")
        database_status = "error"

    dependencies = [ReadinessDependency(name="database", status=database_status)]
    readiness_status = "ok" if database_status == "ok" else "degraded"
    return ReadinessResponse(status=readiness_status, dependencies=dependencies)


def _database_dependency_status(
    session_factory: Callable[[], Session],
) -> Literal["ok", "error"]:
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "error"
    return "ok"
