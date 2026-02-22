import { clearToken, getToken } from "./auth";

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

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers
  });

  if (response.status === 401 || response.status === 403) {
    clearToken();
    window.dispatchEvent(new CustomEvent("wingxtra-auth-required"));
    throw new ApiAuthError();
  }

  return response;
}
