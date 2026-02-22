import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthProvider";

type LocationState = {
  from?: string;
  message?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { loginWithToken } = useAuth();
  const [jwtToken, setJwtToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  const state = (location.state || {}) as LocationState;

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    const result = loginWithToken(jwtToken);
    if (!result.ok) {
      setError(result.message || "Login failed.");
      return;
    }

    navigate(state.from || "/", { replace: true });
  };

  return (
    <section>
      <h2>Login (OPS/DEV JWT)</h2>
      <p>
        Paste a JWT token for development/operator access. This UI stores token in
        memory and <code>sessionStorage</code> only.
      </p>
      {state.message ? <p className="notice">{state.message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      <form onSubmit={handleSubmit} className="token-form">
        <label htmlFor="jwt-token">Paste JWT token</label>
        <textarea
          id="jwt-token"
          rows={6}
          value={jwtToken}
          onChange={(event) => setJwtToken(event.target.value)}
          placeholder="eyJhbGciOiJI..."
        />
        <button type="submit">Login</button>
      </form>
    </section>
  );
}
