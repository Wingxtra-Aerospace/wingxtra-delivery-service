import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { apiFetch } from "../api";
import { DroneGcsLink, MissionGcsLink } from "../components/GcsLinks";
import type { JobResponse } from "../api/schema-types";
type JobItem = JobResponse;

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const location = useLocation();
  const initialJob = (location.state as { job?: JobItem } | null)?.job ?? null;

  const [job, setJob] = useState<JobItem | null>(initialJob);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fallbackMessage, setFallbackMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!jobId) {
        setError("Missing job id.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      setFallbackMessage(null);

      try {
        const response = await apiFetch(`/api/v1/jobs/${jobId}`);
        if (!response.ok) {
          if (response.status === 404 || response.status === 405) {
            setFallbackMessage("Job detail endpoint not available.");
            setLoading(false);
            return;
          }
          throw new Error(`Request failed with status ${response.status}`);
        }

        const body = (await response.json()) as JobItem;
        if (!active) return;
        setJob(body);
      } catch {
        if (!active) return;
        if (initialJob) {
          setFallbackMessage("Job detail endpoint not available.");
          setJob(initialJob);
        } else {
          setError("Unable to load job detail.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [jobId, initialJob]);

  return (
    <section>
      <h2>Job Detail</h2>
      <p>
        <Link to="/jobs">← Back to Jobs</Link>
      </p>

      {loading ? <p>Loading job detail...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {fallbackMessage ? <p className="notice">{fallbackMessage}</p> : null}

      {!loading && !error && job ? (
        <>
          <dl className="detail-grid">
            <dt>job_id</dt>
            <dd>{job.id}</dd>
            <dt>order_id</dt>
            <dd>
              <Link to={`/orders/${job.order_id}`}>{job.order_id}</Link>
            </dd>
            <dt>assigned_drone_id</dt>
            <dd>{job.assigned_drone_id}</dd>
            <dt>status</dt>
            <dd>{job.status}</dd>
            <dt>created_at</dt>
            <dd>{new Date(job.created_at).toLocaleString()}</dd>
            <dt>mission_intent_id</dt>
            <dd>{job.mission_intent_id || "—"}</dd>
          </dl>
          <div className="detail-links">
            {job.assigned_drone_id ? (
              <p>
                <DroneGcsLink droneId={job.assigned_drone_id} />
              </p>
            ) : null}
            {job.mission_intent_id ? (
              <p>
                <MissionGcsLink missionId={job.mission_intent_id} />
              </p>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
