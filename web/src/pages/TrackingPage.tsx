import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { TrackingViewResponse } from "../api/types";

type TrackingResponse = TrackingViewResponse & {
  order_id: string;
  public_tracking_id: string;
  status: string;
  milestones?: string[];
  pod_summary?: {
    method: string;
    created_at: string;
  };
  dropoff_lat?: number;
  dropoff_lng?: number;
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export function TrackingPage() {
  const { publicTrackingId } = useParams<{ publicTrackingId: string }>();
  const navigate = useNavigate();
  const [trackingIdInput, setTrackingIdInput] = useState(publicTrackingId ?? "");
  const [data, setData] = useState<TrackingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number>(0);

  useEffect(() => {
    setTrackingIdInput(publicTrackingId ?? "");
  }, [publicTrackingId]);

  useEffect(() => {
    if (!retryAfterSeconds) return;
    const timer = window.setInterval(() => {
      setRetryAfterSeconds((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [retryAfterSeconds]);

  useEffect(() => {
    async function load() {
      if (!publicTrackingId) {
        return;
      }

      setLoading(true);
      setError(null);
      setData(null);

      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/tracking/${encodeURIComponent(publicTrackingId)}`);

        if (response.status === 429) {
          const retryAfter = Number.parseInt(response.headers.get("Retry-After") || "30", 10);
          setRetryAfterSeconds(Number.isFinite(retryAfter) ? Math.max(1, retryAfter) : 30);
          setError("Tracking is temporarily rate limited. Please wait before trying again.");
          return;
        }

        if (!response.ok) {
          setError(`Unable to load tracking (${response.status}).`);
          return;
        }

        const body = (await response.json()) as TrackingResponse;
        setData(body);
      } catch {
        setError("Unable to load tracking right now.");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [publicTrackingId]);

  const hasCoordinates = useMemo(
    () => data?.dropoff_lat != null && data?.dropoff_lng != null,
    [data?.dropoff_lat, data?.dropoff_lng]
  );

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!trackingIdInput.trim()) return;
    navigate(`/tracking/${encodeURIComponent(trackingIdInput.trim())}`);
  };

  return (
    <section>
      <h2>Public Tracking</h2>
      <form className="tracking-form" onSubmit={onSubmit}>
        <label htmlFor="tracking-id">Public tracking ID</label>
        <input
          id="tracking-id"
          value={trackingIdInput}
          onChange={(event) => setTrackingIdInput(event.target.value)}
          placeholder="trk_..."
        />
        <button type="submit">Load</button>
      </form>

      {!publicTrackingId ? <p>Enter a public tracking ID to view shipment status.</p> : null}
      {loading ? <p>Loading tracking...</p> : null}

      {error ? (
        <p className="error" role="alert">
          {error}
          {retryAfterSeconds > 0 ? ` Try again in ~${retryAfterSeconds}s.` : ""}
        </p>
      ) : null}

      {data ? (
        <>
          <dl className="detail-grid">
            <dt>order_id</dt>
            <dd>{data.order_id}</dd>
            <dt>public_tracking_id</dt>
            <dd>{data.public_tracking_id}</dd>
            <dt>status</dt>
            <dd>{data.status}</dd>
          </dl>

          <h3>Milestones</h3>
          {data.milestones && data.milestones.length ? (
            <ul className="timeline-list">
              {data.milestones.map((milestone) => (
                <li key={milestone}>{milestone}</li>
              ))}
            </ul>
          ) : (
            <p>No milestones available.</p>
          )}

          <h3>Location</h3>
          {hasCoordinates ? (
            <p>
              Coordinates: {data.dropoff_lat}, {data.dropoff_lng}
            </p>
          ) : (
            <p>Coordinates unavailable.</p>
          )}

          <h3>Proof of delivery</h3>
          {data.pod_summary ? (
            <p>
              Method: {data.pod_summary.method} · {new Date(data.pod_summary.created_at).toLocaleString()}
            </p>
          ) : (
            <p>No POD summary.</p>
          )}

          <p>
            <Link to="/">Back to home</Link>
          </p>
        </>
      ) : null}
    </section>
  );
}
