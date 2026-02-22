import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OrderDetailPage } from "./OrderDetailPage";

const useAuthMock = vi.hoisted(() => vi.fn());

vi.mock("../AuthProvider", () => ({
  useAuth: useAuthMock
}));

function renderDetail(initialEntry = "/orders/ord-123") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/orders/:orderId" element={<OrderDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  useAuthMock.mockReset();
});

describe("OrderDetailPage", () => {
  it("renders timeline events", async () => {
    useAuthMock.mockReturnValue({ claims: { role: "OPS" } });

    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "ord-123",
          status: "QUEUED",
          public_tracking_id: "TRK-1",
          created_at: "2026-01-01T00:00:00Z"
        }),
        { status: 200 }
      )
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            {
              id: "evt-1",
              type: "CREATED",
              message: "Order created",
              created_at: "2026-01-01T00:00:00Z"
            }
          ]
        }),
        { status: 200 }
      )
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ order_id: "ord-123", method: null }), { status: 200 })
    );

    renderDetail();

    expect(await screen.findByText("Timeline")).toBeInTheDocument();
    expect(await screen.findByText(/CREATED/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });

  it("hides ops-only actions for merchant", async () => {
    useAuthMock.mockReturnValue({ claims: { role: "MERCHANT" } });

    vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "ord-123",
            status: "QUEUED",
            public_tracking_id: "TRK-1",
            created_at: "2026-01-01T00:00:00Z"
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [] }), { status: 200 })
      );

    renderDetail();

    await waitFor(() => expect(screen.getByText("Actions")).toBeInTheDocument());

    expect(screen.queryByText("Manual assign drone")).not.toBeInTheDocument();
    expect(screen.queryByText("Submit mission intent")).not.toBeInTheDocument();
    expect(screen.getByText("Cancel order")).toBeInTheDocument();
  });
});
