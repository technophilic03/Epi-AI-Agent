import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Clarification from "./Clarification";
import type { ActiveInterrupt } from "./types";

type ClarificationInterrupt = Extract<
  ActiveInterrupt,
  { type: "agent_clarification" }
>;

const interrupt: ClarificationInterrupt = {
  id: "interrupt-clarification",
  type: "agent_clarification",
  question: "Which follow-up summary should be used?",
  reason: "Each participant has multiple visits.",
  options: [
    { id: "any", label: "Any missed dose during follow-up" },
    { id: "total", label: "Total missed doses during follow-up" },
  ],
};

describe("Clarification", () => {
  it("requires exactly one fixed option before continuing", () => {
    const onResume = vi.fn();

    render(<Clarification interrupt={interrupt} onResume={onResume} />);

    const continueButton = screen.getByRole("button", { name: "Continue" });
    expect(continueButton).toBeDisabled();
    expect(screen.getByRole("radiogroup")).toHaveAccessibleName(
      "Your answer",
    );

    fireEvent.click(
      screen.getByRole("radio", {
        name: "Any missed dose during follow-up",
      }),
    );
    expect(
      screen.getByRole("radio", {
        name: "Any missed dose during follow-up",
      }),
    ).toBeChecked();
    expect(
      screen.getByRole("radio", {
        name: "Total missed doses during follow-up",
      }),
    ).not.toBeChecked();
    expect(continueButton).toBeEnabled();

    fireEvent.click(continueButton);

    expect(onResume).toHaveBeenCalledWith({
      action: "answer",
      answer: "Any missed dose during follow-up",
    });
  });

  it("shows feedback only for its selected option", () => {
    const onResume = vi.fn();

    render(<Clarification interrupt={interrupt} onResume={onResume} />);

    fireEvent.click(screen.getByRole("radio", { name: "Provide feedback" }));
    const feedback = screen.getByLabelText("Feedback");
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();

    fireEvent.change(feedback, { target: { value: "Use the last visit." } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onResume).toHaveBeenCalledWith({
      action: "answer",
      answer: "Use the last visit.",
    });

    fireEvent.click(
      screen.getByRole("radio", {
        name: "Total missed doses during follow-up",
      }),
    );
    expect(screen.queryByLabelText("Feedback")).not.toBeInTheDocument();
  });

  it("delegates only when the delegate choice is selected", () => {
    const onResume = vi.fn();

    render(<Clarification interrupt={interrupt} onResume={onResume} />);

    fireEvent.click(
      screen.getByRole("radio", { name: "Let the agent decide" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(onResume).toHaveBeenCalledWith({
      action: "answer",
      answer: "__agent_decide__",
    });
  });

  it("keeps all four choices exclusive and disables actions when requested", () => {
    const onResume = vi.fn();

    const { rerender } = render(
      <Clarification interrupt={interrupt} onResume={onResume} />,
    );

    expect(screen.getAllByRole("radio")).toHaveLength(4);
    fireEvent.click(screen.getByRole("radio", { name: "Provide feedback" }));
    expect(screen.getByRole("radio", { name: "Provide feedback" })).toBeChecked();
    fireEvent.click(
      screen.getByRole("radio", { name: "Let the agent decide" }),
    );
    expect(
      screen.getByRole("radio", { name: "Provide feedback" }),
    ).not.toBeChecked();

    rerender(<Clarification disabled interrupt={interrupt} onResume={onResume} />);
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onResume).not.toHaveBeenCalled();
  });

  it("allows cancellation while enabled", () => {
    const onResume = vi.fn();

    render(<Clarification interrupt={interrupt} onResume={onResume} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onResume).toHaveBeenCalledWith({ action: "cancel" });
  });
});
