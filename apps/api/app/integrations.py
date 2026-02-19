from typing import Protocol


class MissionPublisher(Protocol):
    def publish_mission_intent(self, payload: dict) -> None: ...


class NoopMissionPublisher:
    def publish_mission_intent(self, payload: dict) -> None:
        return None
