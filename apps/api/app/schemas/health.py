from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    dependencies: dict[str, Literal["ok", "degraded", "down"]]


class ReadinessDependency(BaseModel):
    name: str
    status: Literal["ok", "error"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    dependencies: list[ReadinessDependency]
