import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StructuredOutput from "./StructuredOutput";

describe("StructuredOutput", () => {
  it("renders QA answers from backend output", () => {
    render(
      <StructuredOutput
        output={{
          qa_response: "There are 17 index cases with diabetes.",
          dataset_id: "subset-17",
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Agent output" }),
    ).toBeInTheDocument();
    expect(screen.getByText("QA answer")).toBeInTheDocument();
    expect(
      screen.getByText("There are 17 index cases with diabetes."),
    ).toBeInTheDocument();
    expect(screen.getByText("Related dataset")).toBeInTheDocument();
    expect(screen.getByText("subset-17")).toBeInTheDocument();
  });

  it("renders clarification prompts without dumping raw JSON", () => {
    render(
      <StructuredOutput
        output={{
          needs_clarification: true,
          clarification_question: "Which dataset should I use?",
        }}
      />,
    );

    expect(screen.getByText("Clarification needed")).toBeInTheDocument();
    expect(screen.getByText("Which dataset should I use?")).toBeInTheDocument();
    expect(screen.queryByText("needs_clarification")).not.toBeInTheDocument();
  });

  it("renders nothing for unknown output shapes", () => {
    const { container } = render(<StructuredOutput output={{ arbitrary: "value" }} />);

    expect(container).toBeEmptyDOMElement();
  });
});
