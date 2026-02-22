import { useEffect, useState } from "react";
import { apiFetch } from "../api";

export function OpsConsolePage() {
  const [status, setStatus] = useState("Loading ops metrics...");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await apiFetch("/metrics");
        if (!active) {
          return;
        }
        setStatus(response.ok ? "Connected to ops metrics API." : "Metrics API returned an error response.");
      } catch {
        if (!active) {
          return;
        }
        setStatus("Unable to load metrics.");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h2>Ops Console</h2>
      <p>Ops controls and status panel scaffold placeholder.</p>
      <p>{status}</p>
    </section>
  );
}
