const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function HomePage() {
  return (
    <section>
      <h2>Home</h2>
      <p>
        Minimal React scaffold for Wingxtra delivery UI. Use navigation links above
        to move between placeholder pages.
      </p>
      <p>
        API base URL: <code>{apiBaseUrl}</code>
      </p>
    </section>
  );
}
