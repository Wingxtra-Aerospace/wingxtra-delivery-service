import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../AuthProvider";
import { apiFetch } from "../api";

type OrderDetail = {
  id: string;
  status: string;
  priority?: string | null;
  pickup_lat?: number | null;
  pickup_lng?: number | null;
  dropoff_lat?: number | null;
  dropoff_lng?: number | null;
  assigned_drone_id?: string | null;
  public_tracking_id: string;
  created_at: string;
  mission_id?: string | null;
  mission_intent_id?: string | null;
};

type EventItem = {
  id: string;
  type: string;
  message: string;
  created_at: string;
  mission_id?: string | null;
  mission_intent_id?: string | null;
};

type PodResponse = {
  order_id: string;
  method: string | null;
  operator_name?: string | null;
  photo_url?: string | null;
  created_at?: string | null;
};

const EVENT_TYPES = ["MISSION_LAUNCHED", "ENROUTE", "ARRIVED", "DELIVERED", "FAILED"];

function extractErrorMessage(errorBody: unknown, fallback: string): string {
  if (errorBody && typeof errorBody === "object" && "detail" in errorBody) {
    const detail = (errorBody as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  }
  return fallback;
}

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { claims } = useAuth();

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [pod, setPod] = useState<PodResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [droneId, setDroneId] = useState("");
  const [ingestEventType, setIngestEventType] = useState(EVENT_TYPES[0]);
  const [ingestOccurredAt, setIngestOccurredAt] = useState("");

  const role = claims?.role;
  const canOps = role === "OPS" || role === "ADMIN";
  const canCancel = role === "OPS" || role === "ADMIN" || role === "MERCHANT";

  const fetchAll = useCallback(async () => {
    if (!orderId) {
      setError("Missing order id.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setActionError(null);

    try {
      const [orderRes, eventsRes] = await Promise.all([
        apiFetch(`/api/v1/orders/${orderId}`),
        apiFetch(`/api/v1/orders/${orderId}/events?page=1&page_size=100`)
      ]);

      if (!orderRes.ok) {
        const body = (await orderRes.json()) as unknown;
        throw new Error(extractErrorMessage(body, "Unable to load order detail."));
      }
      if (!eventsRes.ok) {
        const body = (await eventsRes.json()) as unknown;
        throw new Error(extractErrorMessage(body, "Unable to load order events."));
      }

      const orderBody = (await orderRes.json()) as OrderDetail;
      const eventsBody = (await eventsRes.json()) as { items: EventItem[] };

      setOrder(orderBody);
      setEvents(
        [...(eventsBody.items || [])].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
      );

      if (canOps) {
        const podRes = await apiFetch(`/api/v1/orders/${orderId}/pod`);
        if (podRes.ok) {
          setPod((await podRes.json()) as PodResponse);
        } else {
          setPod({ order_id: orderId, method: null });
        }
      } else {
        setPod({ order_id: orderId, method: null });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load order detail.");
    } finally {
      setLoading(false);
    }
  }, [orderId, canOps]);

  useEffect(() => {
    void fetchAll();
  }, [fetchAll]);

  const trackingLink = useMemo(() => {
    if (!order?.public_tracking_id) return null;
    return `${window.location.origin}/tracking?trackingId=${order.public_tracking_id}`;
  }, [order?.public_tracking_id]);

  const missionId =
    order?.mission_id ||
    order?.mission_intent_id ||
    events.find((event) => event.mission_id || event.mission_intent_id)?.mission_id ||
    events.find((event) => event.mission_id || event.mission_intent_id)?.mission_intent_id ||
    null;

  async function runAction(action: () => Promise<Response>, successMessage: string) {
    setActionError(null);
    try {
      const response = await action();
      if (!response.ok) {
        const body = (await response.json()) as unknown;
        throw new Error(extractErrorMessage(body, `Request failed with status ${response.status}`));
      }
      setToast(successMessage);
      await fetchAll();
      setTimeout(() => setToast(null), 2500);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed.");
    }
  }

  const onAssign = async () => {
    if (!droneId.trim() || !orderId) return;
    await runAction(
      () =>
        apiFetch(`/api/v1/orders/${orderId}/assign`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ drone_id: droneId.trim() })
        }),
      "Drone assigned successfully."
    );
  };

  const onCancel = async () => {
    if (!orderId) return;
    const confirmed = window.confirm("Cancel this order? This action cannot be undone.");
    if (!confirmed) return;
    await runAction(() => apiFetch(`/api/v1/orders/${orderId}/cancel`, { method: "POST" }), "Order canceled.");
  };

  const onSubmitMission = async () => {
    if (!orderId) return;
    await runAction(
      () => apiFetch(`/api/v1/orders/${orderId}/submit-mission-intent`, { method: "POST" }),
      "Mission intent submitted."
    );
  };

  const onIngestEvent = async () => {
    if (!orderId) return;
    const payload: Record<string, string> = { event_type: ingestEventType };
    if (ingestOccurredAt) {
      payload.occurred_at = new Date(ingestOccurredAt).toISOString();
    }
    await runAction(
      () =>
        apiFetch(`/api/v1/orders/${orderId}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }),
      "Event ingested."
    );
  };

  return (
    <section>
      <h2>Order Detail</h2>
      <p>
        <Link to="/orders">← Back to Orders</Link>
      </p>

      {toast ? <p className="notice">{toast}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {actionError ? <p className="error">{actionError}</p> : null}

      {loading ? <p>Loading order detail...</p> : null}

      {!loading && !error && order ? (
        <>
          <dl className="detail-grid">
            <dt>id</dt>
            <dd>{order.id}</dd>
            <dt>status</dt>
            <dd>{order.status}</dd>
            <dt>priority</dt>
            <dd>{order.priority || "—"}</dd>
            <dt>assigned_drone_id</dt>
            <dd>{order.assigned_drone_id || "—"}</dd>
            <dt>pickup</dt>
            <dd>
              {order.pickup_lat != null && order.pickup_lng != null
                ? `${order.pickup_lat}, ${order.pickup_lng}`
                : "—"}
            </dd>
            <dt>dropoff</dt>
            <dd>
              {order.dropoff_lat != null && order.dropoff_lng != null
                ? `${order.dropoff_lat}, ${order.dropoff_lng}`
                : "—"}
            </dd>
            <dt>created_at</dt>
            <dd>{new Date(order.created_at).toLocaleString()}</dd>
          </dl>

          <div className="detail-links">
            <p>
              Public tracking: <a href={trackingLink || "#"}>{order.public_tracking_id}</a>
              <button
                type="button"
                onClick={async () => {
                  if (trackingLink) {
                    await navigator.clipboard.writeText(trackingLink);
                    setToast("Tracking link copied.");
                    setTimeout(() => setToast(null), 2000);
                  }
                }}
              >
                Copy
              </button>
            </p>
            {order.assigned_drone_id ? (
              <p>
                <a
                  href={`https://gcs.wingxtra.com/?drone=${encodeURIComponent(order.assigned_drone_id)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open Drone in Wingxtra GCS
                </a>
              </p>
            ) : null}
            {missionId ? (
              <p>
                <a
                  href={`https://gcs.wingxtra.com/?mission=${encodeURIComponent(missionId)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open Mission in Wingxtra GCS
                </a>
              </p>
            ) : null}
          </div>

          <h3>Timeline</h3>
          {events.length === 0 ? (
            <p>No events yet.</p>
          ) : (
            <ul className="timeline-list">
              {events.map((event) => (
                <li key={event.id}>
                  <strong>{event.type}</strong> · {new Date(event.created_at).toLocaleString()} · {event.message}
                </li>
              ))}
            </ul>
          )}

          <h3>Proof of delivery</h3>
          {pod?.method ? (
            <p>
              Method: {pod.method}
              {pod.created_at ? ` · ${new Date(pod.created_at).toLocaleString()}` : ""}
            </p>
          ) : (
            <p>No POD</p>
          )}

          <h3>Actions</h3>
          <div className="actions-grid">
            {canCancel ? (
              <button type="button" onClick={() => void onCancel()}>
                Cancel order
              </button>
            ) : null}

            {canOps ? (
              <>
                <div>
                  <label>
                    Drone ID
                    <input value={droneId} onChange={(event) => setDroneId(event.target.value)} placeholder="DR-100" />
                  </label>
                  <button type="button" onClick={() => void onAssign()} disabled={!droneId.trim()}>
                    Manual assign drone
                  </button>
                </div>

                <div>
                  <label>
                    Event type
                    <select value={ingestEventType} onChange={(event) => setIngestEventType(event.target.value)}>
                      {EVENT_TYPES.map((eventType) => (
                        <option key={eventType} value={eventType}>
                          {eventType}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Occurred at
                    <input
                      type="datetime-local"
                      value={ingestOccurredAt}
                      onChange={(event) => setIngestOccurredAt(event.target.value)}
                    />
                  </label>
                  <button type="button" onClick={() => void onIngestEvent()}>
                    Ingest event
                  </button>
                </div>

                <button type="button" onClick={() => void onSubmitMission()}>
                  Submit mission intent
                </button>
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
