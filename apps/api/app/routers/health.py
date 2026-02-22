from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.health import HealthResponse, ReadinessDependency, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", summary="Readiness check", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    dependencies: list[ReadinessDependency] = []

    try:
        db: Session = SessionLocal()
        db.execute(text("SELECT 1"))
        dependencies.append(ReadinessDependency(name="database", status="ok"))
    except Exception:
        dependencies.append(ReadinessDependency(name="database", status="error"))
        return ReadinessResponse(status="degraded", dependencies=dependencies)
    finally:
        if "db" in locals():
            db.close()

    return ReadinessResponse(status="ok", dependencies=dependencies)
