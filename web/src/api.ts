import { clearToken, getToken } from "./auth";
import { createRequestId, emitApiError } from "./observability";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const baseUrl = apiBaseUrl.replace(/\/$/, "");

export class ApiAuthError extends Error {
  constructor(message = "Authentication required") {
    super(message);
    this.name = "ApiAuthError";
  }
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers ?? {});
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const requestId = headers.get("X-Request-ID") ?? createRequestId();
  headers.set("X-Request-ID", requestId);

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers
    });
  } catch {
    emitApiError({ requestId });
    throw new Error("Network request failed");
  }

  if (response.status === 401 || response.status === 403) {
    clearToken();
    window.dispatchEvent(new CustomEvent("wingxtra-auth-required"));
    throw new ApiAuthError();
  }

  if (!response.ok) {
    emitApiError({ requestId, status: response.status });
  }

  return response;
}
