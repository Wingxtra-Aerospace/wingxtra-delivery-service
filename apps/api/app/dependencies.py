from app.integrations import NoopMissionPublisher


def get_mission_publisher():
    return NoopMissionPublisher()
