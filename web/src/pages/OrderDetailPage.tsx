import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../api";
import type { OrderItem } from "../types";

export function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<OrderItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!orderId) {
        setError("Missing order id.");
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await apiFetch(`/api/v1/orders/${orderId}`);
        if (!response.ok) {
          throw new Error(String(response.status));
        }
        const body = (await response.json()) as OrderItem;
        if (!active) return;
        setOrder(body);
      } catch {
        if (!active) return;
        setError("Unable to load order detail.");
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [orderId]);

  return (
    <section>
      <h2>Order Detail</h2>
      <p>
        <Link to="/orders">← Back to Orders</Link>
      </p>
      {loading ? <p>Loading order detail...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {!loading && !error && order ? (
        <dl>
          <dt>order_id</dt>
          <dd>{order.id}</dd>
          <dt>created_at</dt>
          <dd>{new Date(order.created_at).toLocaleString()}</dd>
          <dt>status</dt>
          <dd>{order.status}</dd>
          <dt>priority</dt>
          <dd>{order.priority || "—"}</dd>
          <dt>assigned_drone_id</dt>
          <dd>{order.assigned_drone_id || "—"}</dd>
          <dt>public_tracking_id</dt>
          <dd>{order.public_tracking_id}</dd>
        </dl>
      ) : null}
    </section>
  );
}
