import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DbRagReview from "./DbRagReview";
import type { ActiveInterrupt } from "./types";

type DatasetPlanInterrupt = Extract<
  ActiveInterrupt,
  { type: "dataset_plan_review" }
>;

function interrupt(): DatasetPlanInterrupt {
  return {
    id: "interrupt-plan-1",
    type: "dataset_plan_review",
    artifact: {
      id: "plan-1",
      kind: "dataset_plan",
      version: 1,
      expected_status: "draft",
    },
    view: {
      goal: "Create a tuberculosis recurrence cohort.",
      dataset_title: "Tuberculosis Recurrence Cohort",
      concept_groups: [
        {
          concept_id: "recurrence",
          concept_label: "TB recurrence",
          columns: [
            {
              key: "report::outcomes::recurrence",
              source: "report",
              table: "outcomes",
              column: "recurrence",
              roles: ["requested"],
            },
            {
              key: "report::outcomes::episode",
              source: "report",
              table: "outcomes",
              column: "episode",
              roles: ["requested"],
              selected: false,
            },
          ],
        },
        {
          concept_id: "age",
          concept_label: "Age",
          columns: [
            {
              key: "report::baseline::age",
              source: "report",
              table: "baseline",
              column: "age",
              roles: ["requested"],
            },
          ],
        },
      ],
      selected_fields: ["report::outcomes::recurrence"],
      filters: [{ description: "Use baseline records." }],
      required_fields: [
        {
          key: "report::baseline::subject_id",
          source: "report_duckdb",
          table: "Baseline",
          column: "SUBJECT_ID",
          purpose: "identity",
          roles: ["identifier"],
          label: "Required identifier",
          required: true,
        },
      ],
      joins: [],
      unresolved_scientific_choices: [],
    },
  };
}

describe("DbRagReview", () => {
  it("reads the typed view and approves selected keys", () => {
    const onDecision = vi.fn();
    render(
      <DbRagReview interrupt={interrupt()} onDecision={onDecision} reviewMode="all" />,
    );

    expect(screen.getByRole("heading", { name: "Review dataset plan" }))
      .toBeInTheDocument();
    expect(screen.getByText("Create a tuberculosis recurrence cohort."))
      .toBeInTheDocument();
    expect(screen.getByText("Use baseline records.")).toBeInTheDocument();
    expect(screen.getByText("Baseline · SUBJECT_ID")).toBeInTheDocument();
    expect(screen.queryByText(/report_duckdb/)).not.toBeInTheDocument();
    const reviewActions = document.querySelector<HTMLDivElement>(
      ".db-rag-review-actions",
    );
    if (!reviewActions) {
      throw new Error("Review action group was not rendered.");
    }
    expect(
      within(reviewActions)
        .getAllByRole("button")
        .map((button) => button.textContent?.trim()),
    ).toEqual([
      "Approve plan and extract",
      "Request revision",
      "Cancel review",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "Approve plan and extract" }));
    expect(onDecision).toHaveBeenCalledWith({
      action: "approve",
      selected_column_keys: [
        "report::baseline::age",
        "report::outcomes::recurrence",
      ],
    });
  });

  it("emits only trimmed revise and cancel decisions", () => {
    const onDecision = vi.fn();
    render(<DbRagReview interrupt={interrupt()} onDecision={onDecision} />);

    fireEvent.click(screen.getByRole("button", { name: "Request revision" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please enter revision feedback.",
    );
    fireEvent.change(screen.getByLabelText("Revision feedback"), {
      target: { value: "  Use the first recurrence episode.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request revision" }));
    expect(onDecision).toHaveBeenLastCalledWith({
      action: "revise",
      feedback: "Use the first recurrence episode.",
      selected_column_keys: [
        "report::baseline::age",
        "report::outcomes::recurrence",
      ],
    });

    fireEvent.click(screen.getByRole("button", { name: "Cancel review" }));
    expect(onDecision).toHaveBeenLastCalledWith({ action: "cancel" });
  });

  it("advances past a concept that contains only required fields", () => {
    const value = interrupt();
    value.view.concept_groups[0] = {
      concept_id: "index-participant",
      concept_label: "Index case participant identifier",
      columns: [
        {
          key: "report::baseline::subject_id",
          source: "report",
          table: "Baseline",
          column: "SUBJECT_ID",
          roles: ["identifier"],
          required: true,
        },
      ],
    };

    render(<DbRagReview interrupt={value} onDecision={vi.fn()} />);

    const continueButton = screen.getByRole("button", {
      name: "Approve & continue",
    });
    expect(continueButton).toBeEnabled();

    fireEvent.click(continueButton);
    expect(screen.getByRole("heading", { name: "Age" })).toBeInTheDocument();
  });
});
