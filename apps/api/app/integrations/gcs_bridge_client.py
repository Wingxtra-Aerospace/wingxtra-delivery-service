from typing import Protocol


class MissionPublisherProtocol(Protocol):
    def publish_mission_intent(self, mission_intent: dict) -> None: ...


class GcsBridgeClient:
    """Publish stub for mission intents.

    This intentionally performs no external side effects yet.
    """

    def publish_mission_intent(self, mission_intent: dict) -> None:
        _ = mission_intent
        return None


def get_gcs_bridge_client() -> MissionPublisherProtocol:
    return GcsBridgeClient()
