import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ModelOutputLimit from "./ModelOutputLimit";
import type { ModelOutputLimitInterrupt } from "./types";

const interrupt: ModelOutputLimitInterrupt = {
  id: "interrupt-output",
  type: "model_output_limit",
  model_id: "gpt-5.6-sol",
  model_label: "gpt-5.6-sol (Medium)",
  automatic_token_ceiling: 50_000,
  continuation_tokens: 25_000,
  additional_output_cost: "$0.75",
  message:
    "gpt-5.6-sol (Medium) reached its 50,000-token turn limit. Continuing with another 25,000 tokens may cost up to an additional $0.75 in output charges.",
  actions: ["continue", "cancel"],
};

describe("ModelOutputLimit", () => {
  it("renders the selected profile warning and exactly two actions", () => {
    const onResume = vi.fn();
    render(
      <ModelOutputLimit
        disabled={false}
        interrupt={interrupt}
        onResume={onResume}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "More output needed" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/another 25,000 tokens/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.75/)).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onResume).toHaveBeenCalledWith({ action: "continue" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onResume).toHaveBeenLastCalledWith({ action: "cancel" });
    expect(screen.queryByText(/switch model/i)).not.toBeInTheDocument();
  });

  it("disables both decisions while a resume is in flight", () => {
    render(
      <ModelOutputLimit
        disabled
        interrupt={interrupt}
        onResume={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});
