import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiErrorBanner } from "./ApiErrorBanner";

describe("ApiErrorBanner", () => {
  it("shows normalized request failure and dismisses", async () => {
    render(<ApiErrorBanner />);

    window.dispatchEvent(
      new CustomEvent("wingxtra-api-error", {
        detail: {
          requestId: "req-1",
          message: "Service unavailable",
          retryable: true
        }
      })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
