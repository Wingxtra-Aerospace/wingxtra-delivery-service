import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiAuthError } from "./api";

const validJwt = "header.eyJyb2xlIjoiQURNSU4ifQ.signature";

afterEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("adds Authorization and X-Request-ID headers", async () => {
    sessionStorage.setItem("wingxtra_ui_jwt", validJwt);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));

    await apiFetch("/api/v1/orders");

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe(`Bearer ${validJwt}`);
    expect(headers.get("X-Request-ID")).toBeTruthy();
  });

  it("raises auth error on 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 401 }));

    await expect(apiFetch("/api/v1/orders")).rejects.toBeInstanceOf(ApiAuthError);
  });

  it("emits normalized API error event for server errors", async () => {
    const handler = vi.fn();
    window.addEventListener("wingxtra-api-error", handler);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 500 }));

    await apiFetch("/api/v1/orders");

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail.message).toContain("temporarily unavailable");
    expect(event.detail.requestId).toBeTruthy();
    window.removeEventListener("wingxtra-api-error", handler);
  });
});
