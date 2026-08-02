import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ClarificationTrace from "./ClarificationTrace";

describe("ClarificationTrace", () => {
  it("starts closed and reveals every question and answer when opened", () => {
    render(
      <ClarificationTrace
        exchanges={[
          {
            interrupt_id: "interrupt-1",
            question: "Which visit should be used?",
            reason: "Multiple visits are available.",
            answer: "Use 12 months.",
          },
        ]}
      />,
    );

    const summary = screen.getByText("Clarification trace", {
      selector: "summary",
    });
    const details = summary.closest("details");

    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");

    fireEvent.click(summary);

    expect(details).toHaveAttribute("open");
    expect(screen.getByText("Use 12 months.")).toBeInTheDocument();
  });
});
