import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GlobalErrorBoundary } from "./GlobalErrorBoundary";

function CrashComponent(): never {
  throw new Error("boom");
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("GlobalErrorBoundary", () => {
  it("renders fallback UI and reload action", () => {
    const reloadMock = vi.spyOn(window.location, "reload").mockImplementation(() => undefined);

    render(
      <GlobalErrorBoundary>
        <CrashComponent />
      </GlobalErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    expect(reloadMock).toHaveBeenCalled();
  });
});
