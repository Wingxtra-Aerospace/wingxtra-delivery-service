import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiFetch } from "../api";
import type { OrderItem, OrdersListResponse } from "../types";

const STATUS_OPTIONS = ["", "CREATED", "VALIDATED", "QUEUED", "ASSIGNED", "MISSION_SUBMITTED", "LAUNCHED", "ENROUTE", "ARRIVED", "DELIVERING", "DELIVERED", "CANCELED", "FAILED", "ABORTED"];
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

function toPositiveInt(value: string | null, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = toPositiveInt(searchParams.get("page"), 1);
  const pageSize = toPositiveInt(searchParams.get("page_size"), 20);
  const status = searchParams.get("status") ?? "";
  const query = searchParams.get("q") ?? "";
  const fromDate = searchParams.get("from") ?? "";
  const toDate = searchParams.get("to") ?? "";

  const [items, setItems] = useState<OrderItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  const requestQuery = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (status) params.set("status", status);
    if (query) params.set("search", query);
    if (fromDate) params.set("from", fromDate);
    if (toDate) params.set("to", toDate);
    return params.toString();
  }, [page, pageSize, status, query, fromDate, toDate]);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/v1/orders?${requestQuery}`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const body = (await response.json()) as OrdersListResponse;
      setItems(body.items || []);
      setTotal(body.total || 0);
    } catch {
      setError("Unable to load orders. Please retry.");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [requestQuery]);

  useEffect(() => {
    void fetchOrders();
  }, [fetchOrders]);

  const updateParams = (updates: Record<string, string>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) next.delete(key);
      else next.set(key, value);
    });
    setSearchParams(next);
  };

  const onRowClick = (orderId: string) => {
    navigate(`/orders/${orderId}`);
  };

  return (
    <section>
      <h2>Orders</h2>

      <div className="filters-grid">
        <label>
          Status
          <select
            value={status}
            onChange={(event) => updateParams({ status: event.target.value, page: "1" })}
            data-testid="status-filter"
          >
            <option value="">All</option>
            {STATUS_OPTIONS.filter(Boolean).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label>
          Search
          <input
            value={query}
            onChange={(event) => updateParams({ q: event.target.value, page: "1" })}
            placeholder="Tracking ID / customer"
          />
        </label>

        <label>
          From
          <input
            type="datetime-local"
            value={fromDate}
            onChange={(event) => updateParams({ from: event.target.value, page: "1" })}
          />
        </label>

        <label>
          To
          <input
            type="datetime-local"
            value={toDate}
            onChange={(event) => updateParams({ to: event.target.value, page: "1" })}
          />
        </label>
      </div>

      {error ? (
        <div className="error" role="alert">
          {error} <button onClick={() => void fetchOrders()}>Retry</button>
        </div>
      ) : null}

      {loading ? <p>Loading orders...</p> : null}

      {!loading && !error && items.length === 0 ? <p>No orders found for current filters.</p> : null}

      {!loading && !error && items.length > 0 ? (
        <table className="orders-table">
          <thead>
            <tr>
              <th>order_id</th>
              <th>created_at</th>
              <th>status</th>
              <th>priority</th>
              <th>assigned_drone_id</th>
              <th>public_tracking_id</th>
            </tr>
          </thead>
          <tbody>
            {items.map((order) => (
              <tr key={order.id} onClick={() => onRowClick(order.id)} className="row-clickable">
                <td>{order.id}</td>
                <td>{new Date(order.created_at).toLocaleString()}</td>
                <td>{order.status}</td>
                <td>{order.priority || "—"}</td>
                <td>{order.assigned_drone_id || "—"}</td>
                <td>
                  <Link to={`/tracking?trackingId=${order.public_tracking_id}`} onClick={(event) => event.stopPropagation()}>
                    {order.public_tracking_id}
                  </Link>
                </td>
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
          <select value={pageSize} onChange={(event) => updateParams({ page_size: event.target.value, page: "1" })}>
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
