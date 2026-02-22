const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function HomePage() {
  return (
    <section>
      <h2>Home</h2>
      <p>
        Milestone 6 UI scaffold with routing, JWT paste-login, role guards, and API
        auth header wiring.
      </p>
      <p>
        API base URL: <code>{apiBaseUrl}</code>
      </p>
    </section>
  );
}
