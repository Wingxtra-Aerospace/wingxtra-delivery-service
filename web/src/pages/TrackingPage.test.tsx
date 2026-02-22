import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TrackingPage } from "./TrackingPage";

function renderTracking(initialEntry = "/tracking/TRK-1") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/tracking" element={<TrackingPage />} />
        <Route path="/tracking/:publicTrackingId" element={<TrackingPage />} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TrackingPage", () => {
  it("renders tracking status and milestones", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          order_id: "ord-1",
          public_tracking_id: "TRK-1",
          status: "ENROUTE",
          milestones: ["CREATED", "ENROUTE"],
          pod_summary: { method: "PHOTO", created_at: "2026-01-01T00:00:00Z" }
        }),
        { status: 200 }
      )
    );

    renderTracking();

    expect(await screen.findByText("ENROUTE")).toBeInTheDocument();
    expect(screen.getByText("CREATED")).toBeInTheDocument();
    expect(screen.getByText(/Method: PHOTO/)).toBeInTheDocument();
  });

  it("handles 429 with friendly countdown", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("", { status: 429, headers: { "Retry-After": "7" } }));

    renderTracking();

    expect(await screen.findByRole("alert")).toHaveTextContent("rate limited");
    expect(screen.getByRole("alert")).toHaveTextContent("Try again in ~7s");
  });

  it("navigates from form input", async () => {
    vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ order_id: "ord-1", public_tracking_id: "TRK-1", status: "CREATED" }), {
          status: 200
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ order_id: "ord-2", public_tracking_id: "TRK-2", status: "ARRIVED" }), {
          status: 200
        })
      );

    renderTracking();
    const input = await screen.findByLabelText("Public tracking ID");
    fireEvent.change(input, { target: { value: "TRK-2" } });
    fireEvent.click(screen.getByText("Load"));

    await waitFor(() => expect(screen.getByText("ARRIVED")).toBeInTheDocument());
  });
});
