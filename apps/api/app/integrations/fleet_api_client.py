from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from app.config import settings


class FleetDroneTelemetry(BaseModel):
    drone_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    battery: float = Field(ge=0, le=100)
    is_available: bool = True


class FleetApiClientProtocol(Protocol):
    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]: ...


class FleetApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/api/v1/telemetry/latest")
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        return [FleetDroneTelemetry.model_validate(item) for item in payload]


def get_fleet_api_client() -> FleetApiClientProtocol:
    return FleetApiClient(settings.fleet_api_base_url)
