import time
from typing import Protocol

import httpx

from app.config import settings
from app.integrations.errors import (
    IntegrationBadGatewayError,
    IntegrationTimeoutError,
    IntegrationUnavailableError,
)
from app.schemas.mission_intent import MissionIntent


class MissionPublisherProtocol(Protocol):
    def publish_mission_intent(self, mission_intent: dict) -> None: ...


class GcsBridgeClient:
    """Publish mission intents to the GCS bridge when configured."""

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

    def publish_mission_intent(self, mission_intent: dict) -> None:
        if not self.base_url:
            return None

        try:
            mission_intent = MissionIntent.model_validate(mission_intent).model_dump(mode="json")
        except Exception as err:
            raise IntegrationBadGatewayError(
                "gcs_bridge", "Mission intent payload failed contract validation"
            ) from err

        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.post(
                        f"{self.base_url}/api/v1/mission-intents",
                        json=mission_intent,
                    )

                if response.status_code >= 500:
                    raise IntegrationUnavailableError("gcs_bridge", "GCS bridge returned 5xx")
                if response.status_code >= 400:
                    raise IntegrationBadGatewayError(
                        "gcs_bridge",
                        f"GCS bridge returned {response.status_code}",
                    )
                return None
            except httpx.TimeoutException:
                integration_error = IntegrationTimeoutError("gcs_bridge")
            except httpx.TransportError as err:
                integration_error = IntegrationUnavailableError("gcs_bridge", str(err))
            except IntegrationUnavailableError as err:
                integration_error = err

            if attempt >= self.max_retries:
                raise integration_error
            time.sleep(self.backoff_s * (2**attempt))

        return None


def get_gcs_bridge_client() -> MissionPublisherProtocol:
    return GcsBridgeClient(
        base_url=settings.gcs_bridge_base_url,
        timeout_s=settings.gcs_bridge_timeout_s,
        max_retries=settings.gcs_bridge_max_retries,
        backoff_s=settings.gcs_bridge_backoff_s,
    )
