import { useEffect, useState } from "react";
import { apiFetch } from "../api";

export function OrdersPage() {
  const [status, setStatus] = useState("Loading orders...");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await apiFetch("/api/v1/orders?page=1&page_size=1");
        if (!active) {
          return;
        }
        setStatus(response.ok ? "Connected to orders API." : "Orders API returned an error response.");
      } catch {
        if (!active) {
          return;
        }
        setStatus("Unable to load orders.");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h2>Orders</h2>
      <p>Orders list/view scaffold placeholder.</p>
      <p>{status}</p>
    </section>
  );
}
