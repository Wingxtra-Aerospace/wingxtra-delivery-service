from app.integrations import NoopMissionPublisher


def get_mission_publisher():
    return NoopMissionPublisher()


def get_gcs_bridge_client():
    return NoopMissionPublisher()
