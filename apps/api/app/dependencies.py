from typing import Protocol


class MissionPublisher(Protocol):
    def publish_mission_intent(self, payload: dict) -> None: ...


class NoopMissionPublisher:
    def publish_mission_intent(self, payload: dict) -> None:
        return None


def get_mission_publisher() -> MissionPublisher:
    return NoopMissionPublisher()


def get_gcs_bridge_client() -> MissionPublisher:
    return NoopMissionPublisher()
