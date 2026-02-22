import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JobsPage } from "./JobsPage";

function renderJobs(initialEntry = "/jobs") {
  function LocationProbe() {
    const location = useLocation();
    return <div data-testid="location-search">{location.search}</div>;
  }

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/jobs"
          element={
            <>
              <LocationProbe />
              <JobsPage />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("JobsPage", () => {
  it("renders loading then rows", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "job-1",
              order_id: "ord-1",
              assigned_drone_id: "DR-1",
              status: "ASSIGNED",
              created_at: "2026-01-01T00:00:00Z"
            }
          ],
          page: 1,
          page_size: 20,
          total: 1
        }),
        { status: 200 }
      )
    );

    renderJobs();

    expect(screen.getByText("Loading jobs...")).toBeInTheDocument();
    expect(await screen.findByText("job-1")).toBeInTheDocument();
  });

  it("active-only toggle changes request params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0 }), { status: 200 })
    );

    renderJobs("/jobs?page=1&page_size=20&active_only=true");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTestId("active-only-toggle"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const secondRequestUrl = String(fetchMock.mock.calls[1][0]);
    expect(secondRequestUrl).toContain("active=false");
    expect(screen.getByTestId("location-search").textContent).toContain("active_only=false");
  });
});
