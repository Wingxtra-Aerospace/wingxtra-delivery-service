from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadinessDependency(BaseModel):
    name: str
    status: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: list[ReadinessDependency]
