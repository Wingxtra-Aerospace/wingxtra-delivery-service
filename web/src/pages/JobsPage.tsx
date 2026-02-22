import { useEffect, useState } from "react";
import { apiFetch } from "../api";

export function JobsPage() {
  const [status, setStatus] = useState("Loading jobs...");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await apiFetch("/api/v1/jobs?page=1&page_size=1");
        if (!active) {
          return;
        }
        setStatus(response.ok ? "Connected to jobs API." : "Jobs API returned an error response.");
      } catch {
        if (!active) {
          return;
        }
        setStatus("Unable to load jobs.");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, []);

  return (
    <section>
      <h2>Jobs</h2>
      <p>Jobs list scaffold placeholder.</p>
      <p>{status}</p>
    </section>
  );
}
