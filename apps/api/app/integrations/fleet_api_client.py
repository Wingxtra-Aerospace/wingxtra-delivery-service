import time
from typing import Protocol

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.errors import (
    IntegrationBadGatewayError,
    IntegrationTimeoutError,
    IntegrationUnavailableError,
)


class FleetDroneTelemetry(BaseModel):
    drone_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    battery: float = Field(ge=0, le=100)
    is_available: bool = True


class FleetApiClientProtocol(Protocol):
    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]: ...


class FleetApiClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        max_retries: int,
        backoff_s: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    def get_latest_telemetry(self) -> list[FleetDroneTelemetry]:
        if not self.base_url:
            raise IntegrationUnavailableError("fleet_api", "Fleet API base URL is not configured")

        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.get(f"{self.base_url}/api/v1/telemetry/latest")

                if response.status_code >= 500:
                    raise IntegrationUnavailableError("fleet_api", "Fleet API returned 5xx")
                if response.status_code >= 400:
                    raise IntegrationBadGatewayError(
                        "fleet_api",
                        f"Fleet API returned {response.status_code}",
                    )

                payload = response.json()
                if not isinstance(payload, list):
                    raise IntegrationBadGatewayError(
                        "fleet_api",
                        "Fleet API returned malformed payload",
                    )
                return [FleetDroneTelemetry.model_validate(item) for item in payload]
            except httpx.TimeoutException:
                integration_error = IntegrationTimeoutError("fleet_api")
            except httpx.TransportError as err:
                integration_error = IntegrationUnavailableError("fleet_api", str(err))
            except IntegrationUnavailableError as err:
                integration_error = err

            if attempt >= self.max_retries:
                raise integration_error

            time.sleep(self.backoff_s * (2**attempt))

        return []


def get_fleet_api_client() -> FleetApiClientProtocol:
    return FleetApiClient(
        settings.fleet_api_base_url,
        timeout_s=settings.fleet_api_timeout_s,
        max_retries=settings.fleet_api_max_retries,
        backoff_s=settings.fleet_api_backoff_s,
    )
