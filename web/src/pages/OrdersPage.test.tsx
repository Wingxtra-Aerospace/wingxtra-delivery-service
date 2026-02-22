import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OrdersPage } from "./OrdersPage";

function renderOrders(initialEntry = "/orders") {
  function LocationProbe() {
    const location = useLocation();
    return <div data-testid="location-search">{location.search}</div>;
  }

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/orders"
          element={
            <>
              <LocationProbe />
              <OrdersPage />
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

describe("OrdersPage", () => {
  it("renders loading then rows", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "ord-123",
              created_at: "2026-01-01T00:00:00Z",
              status: "CREATED",
              priority: "NORMAL",
              public_tracking_id: "TRK-123"
            }
          ],
          page: 1,
          page_size: 20,
          total: 1
        }),
        { status: 200 }
      )
    );

    renderOrders();

    expect(screen.getByText("Loading orders...")).toBeInTheDocument();
    expect(await screen.findByText("ord-123")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("status filter updates URL and request params", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0 }), { status: 200 })
    );

    renderOrders("/orders?page=1&page_size=20");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId("status-filter"), { target: { value: "DELIVERED" } });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const secondRequestUrl = String(fetchMock.mock.calls[1][0]);
    expect(secondRequestUrl).toContain("status=DELIVERED");

    expect(screen.getByTestId("location-search").textContent).toContain("status=DELIVERED");
    expect(screen.getByTestId("location-search").textContent).toContain("page=1");
  });
});
