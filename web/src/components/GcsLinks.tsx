const GCS_BASE_URL = "https://gcs.wingxtra.com";

export function OpenGcsButton() {
  return (
    <a className="primary-link-button" href={GCS_BASE_URL} target="_blank" rel="noreferrer">
      Open Wingxtra GCS
    </a>
  );
}

export function DroneGcsLink({ droneId }: { droneId?: string | null }) {
  if (!droneId) return null;
  return (
    <a
      href={`${GCS_BASE_URL}/?drone=${encodeURIComponent(droneId)}`}
      target="_blank"
      rel="noreferrer"
    >
      Open Drone in Wingxtra GCS
    </a>
  );
}

export function MissionGcsLink({ missionId }: { missionId?: string | null }) {
  if (!missionId) return null;
  return (
    <a
      href={`${GCS_BASE_URL}/?mission=${encodeURIComponent(missionId)}`}
      target="_blank"
      rel="noreferrer"
    >
      Open Mission in Wingxtra GCS
    </a>
  );
}
