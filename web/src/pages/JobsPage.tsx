import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch } from "../api";
import type { JobsListResponse } from "../api/schema-types";
type JobItem = JobsListResponse["items"][number];

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

function toPositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function JobsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = toPositiveInt(searchParams.get("page"), 1);
  const pageSize = toPositiveInt(searchParams.get("page_size"), 20);
  const activeOnly = (searchParams.get("active_only") ?? "true") !== "false";

  const [items, setItems] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  const requestQuery = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    params.set("active", String(activeOnly));
    return params.toString();
  }, [page, pageSize, activeOnly]);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/jobs?${requestQuery}`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const body = (await response.json()) as JobsListResponse;
      setItems(body.items || []);
      setTotal(body.total || 0);
    } catch {
      setError("Unable to load jobs. Please retry.");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [requestQuery]);

  useEffect(() => {
    void fetchJobs();
  }, [fetchJobs]);

  const updateParams = (updates: Record<string, string>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next);
  };

  return (
    <section>
      <h2>Jobs</h2>

      <div className="filters-grid">
        <label>
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(event) =>
              updateParams({
                active_only: String(event.target.checked),
                page: "1"
              })
            }
            data-testid="active-only-toggle"
          />
          Active only
        </label>
      </div>

      {error ? (
        <div className="error" role="alert">
          {error} <button onClick={() => void fetchJobs()}>Retry</button>
        </div>
      ) : null}

      {loading ? <p>Loading jobs...</p> : null}
      {!loading && !error && items.length === 0 ? <p>No jobs found.</p> : null}

      {!loading && !error && items.length > 0 ? (
        <table className="orders-table">
          <thead>
            <tr>
              <th>job_id</th>
              <th>order_id</th>
              <th>assigned_drone_id</th>
              <th>status</th>
              <th>created_at</th>
              <th>updated_at</th>
            </tr>
          </thead>
          <tbody>
            {items.map((job) => (
              <tr
                key={job.id}
                className="row-clickable"
                onClick={() => navigate(`/jobs/${job.id}`, { state: { job } })}
              >
                <td>{job.id}</td>
                <td>{job.order_id}</td>
                <td>{job.assigned_drone_id}</td>
                <td>{job.status}</td>
                <td>{new Date(job.created_at).toLocaleString()}</td>
                <td>{job.updated_at ? new Date(job.updated_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <div className="pagination-bar">
        <button disabled={page <= 1} onClick={() => updateParams({ page: String(page - 1) })}>
          Previous
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button disabled={page >= totalPages} onClick={() => updateParams({ page: String(page + 1) })}>
          Next
        </button>

        <label>
          Page Size
          <select
            value={pageSize}
            onChange={(event) => updateParams({ page_size: event.target.value, page: "1" })}
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
