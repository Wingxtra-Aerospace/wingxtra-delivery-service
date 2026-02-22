import socket
from collections.abc import Callable
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.observability import log_event
from app.schemas.health import HealthResponse, ReadinessDependency, ReadinessResponse

ReadinessStatus = Literal["ok", "error"]

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

    database_status = _safe_dependency_status(
        "database", lambda: _database_dependency_status(SessionLocal)
    )
    dependencies.append(ReadinessDependency(name="database", status=database_status))

    if settings.redis_url.strip():
        redis_status = _safe_dependency_status(
            "redis",
            lambda: _redis_dependency_status(settings.redis_url),
        )
        dependencies.append(ReadinessDependency(name="redis", status=redis_status))

    readiness_status = "ok" if all(dep.status == "ok" for dep in dependencies) else "degraded"
    if readiness_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status=readiness_status, dependencies=dependencies)


def _safe_dependency_status(
    dependency_name: str,
    checker: Callable[[], ReadinessStatus],
) -> ReadinessStatus:
    try:
        return checker()
    except Exception as exc:  # defensive: readiness must fail closed to degraded
        log_event(
            "readiness_dependency_check_failed",
            order_id=f"{dependency_name}:{type(exc).__name__}",
        )
        return "error"


def _database_dependency_status(
    session_factory: Callable[[], Session],
) -> ReadinessStatus:
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "error"
    return "ok"


def _redis_dependency_status(redis_url: str) -> ReadinessStatus:
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        return "error"

    host = parsed.hostname
    if not host:
        return "error"

    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1.0) as conn:
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            payload = conn.recv(16)
    except OSError:
        return "error"

    return "ok" if payload.startswith(b"+PONG") else "error"
