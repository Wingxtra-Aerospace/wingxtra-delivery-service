import { useEffect, useState } from "react";
import { apiFetch } from "../api";

export function TrackingPage() {
  const [status, setStatus] = useState("Loading tracking sample...");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await apiFetch("/health");
        if (!active) {
          return;
        }
        setStatus(response.ok ? "API connectivity OK." : "API is reachable but returned an error.");
      } catch {
        if (!active) {
          return;
        }
        setStatus("Unable to reach API.");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h2>Tracking</h2>
      <p>Public tracking view scaffold placeholder.</p>
      <p>{status}</p>
    </section>
  );
}
