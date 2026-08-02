import { useEffect, useState } from "react";
import {
  initialSelectedKeys,
  nextConceptIndex,
  selectedKeysForApproval,
} from "./reviewSelection";
import type {
  ActiveInterrupt,
  ResumeInterruptPayload,
  ReviewColumn,
  ReviewDataLinkage,
  ReviewGroup,
} from "./types";

type DatasetPlanInterrupt = Extract<
  ActiveInterrupt,
  { type: "dataset_plan_review" }
>;

export type ReviewMode = "step" | "all";

interface Props {
  disabled?: boolean;
  interrupt: DatasetPlanInterrupt;
  onDecision: (payload: ResumeInterruptPayload) => void;
  onReviewModeChange?: (mode: ReviewMode) => void;
  reviewMode?: ReviewMode;
}

function columnLabel(column: {
  table: string;
  column: string;
}): string {
  return `${column.table} · ${column.column}`;
}

function selectableKeys(group: ReviewGroup): string[] {
  return group.columns
    .filter(
      (column) =>
        column.roles.length === 1 && column.roles[0] === "requested",
    )
    .map((column) => column.key);
}

export default function DbRagReview({
  disabled = false,
  interrupt,
  onDecision,
  onReviewModeChange,
  reviewMode,
}: Props) {
  const groups = interrupt.view.concept_groups;
  const filters = interrupt.view.filters;
  const requiredFields = interrupt.view.required_fields ?? [];
  const dataLinkage: ReviewDataLinkage = {
    relationships: interrupt.view.joins,
  };
  const [conceptIndex, setConceptIndex] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [feedbackError, setFeedbackError] = useState("");
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(
    () => initialSelectedKeys(groups),
  );
  const [localMode, setLocalMode] = useState<ReviewMode>("step");
  const activeMode = reviewMode ?? localMode;
  const setMode = onReviewModeChange ?? setLocalMode;

  useEffect(() => {
    setConceptIndex(0);
    setFeedback("");
    setFeedbackError("");
    setSelectedKeys(initialSelectedKeys(groups));
  }, [groups, interrupt.id]);

  const approvedKeys = selectedKeysForApproval(selectedKeys);
  const currentGroup = groups[conceptIndex];

  function toggle(key: string) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function renderColumn(column: ReviewColumn) {
    const optionalRequested =
      column.roles.length === 1 && column.roles[0] === "requested";
    if (!optionalRequested) {
      return (
        <div className="db-rag-required-provenance" key={column.key}>
          <strong>{columnLabel(column)}</strong>
          <span>Required by the current draft.</span>
        </div>
      );
    }
    return (
      <label className="db-rag-column-option" key={column.key}>
        <input
          aria-label={columnLabel(column)}
          checked={selectedKeys.has(column.key)}
          disabled={disabled}
          onChange={() => toggle(column.key)}
          type="checkbox"
        />
        <span>
          <strong>{columnLabel(column)}</strong>
          {column.description ? <span>{column.description}</span> : null}
        </span>
      </label>
    );
  }

  function renderGroup(group: ReviewGroup) {
    return (
      <article className="db-rag-concept-card" key={group.concept_id}>
        <h3>{group.concept_label}</h3>
        <div className="db-rag-column-list">
          {group.columns.map(renderColumn)}
        </div>
        {group.unresolved_reason ? <p>{group.unresolved_reason}</p> : null}
      </article>
    );
  }

  function revise() {
    const trimmed = feedback.trim();
    if (!trimmed) {
      setFeedbackError("Please enter revision feedback.");
      return;
    }
    setFeedbackError("");
    onDecision({
      action: "revise",
      feedback: trimmed,
      selected_column_keys: approvedKeys,
    });
  }

  if (!currentGroup) {
    return (
      <section className="db-rag-review-panel">
        <h2>Review dataset plan</h2>
        <p>No review groups are available.</p>
      </section>
    );
  }

  const visibleGroups = activeMode === "all" ? groups : [currentGroup];
  const isFinalConcept = conceptIndex === groups.length - 1;

  return (
    <section className="db-rag-review-panel" aria-labelledby="db-rag-heading">
      <header className="db-rag-review-header">
        <div>
          <h2 id="db-rag-heading">Review dataset plan</h2>
          <p>{interrupt.view.goal}</p>
        </div>
        <div className="db-rag-review-mode" aria-label="DB-RAG review mode">
          <button
            aria-pressed={activeMode === "step"}
            disabled={disabled}
            onClick={() => setMode("step")}
            type="button"
          >
            Step by step
          </button>
          <button
            aria-pressed={activeMode === "all"}
            disabled={disabled}
            onClick={() => setMode("all")}
            type="button"
          >
            All concepts
          </button>
        </div>
      </header>

      {visibleGroups.map(renderGroup)}

      {filters.length ? (
        <section className="db-rag-filter-summary">
          <h3>Filters</h3>
          <ul>
            {filters.map((filter, index) => (
              <li key={index}>
                {filter.description || filter.predicate || JSON.stringify(filter)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {requiredFields.length ? (
        <section className="db-rag-linkage-section">
          <h3>Required identifiers</h3>
          <div className="db-rag-column-list">
            {requiredFields.map((field) => (
              <div className="db-rag-required-provenance" key={field.key}>
                <strong>{columnLabel(field)}</strong>
                <span>{field.label}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {dataLinkage.relationships.length ? (
        <section className="db-rag-linkage-section">
          <h3>Data linkage</h3>
          <ul>
            {dataLinkage.relationships.map((relationship, index) => (
              <li key={`${relationship.left_table}-${index}`}>
                {relationship.key_pairs.length
                  ? relationship.key_pairs.map((pair) => (
                      <span key={`${pair.left_column}-${pair.right_column}`}>
                        {relationship.left_table} · {pair.left_column} ↔{" "}
                        {relationship.right_table} · {pair.right_column}
                      </span>
                    ))
                  : `${relationship.left_table} to ${relationship.right_table}`}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {interrupt.view.unresolved_scientific_choices.length ? (
        <section>
          <h3>Unresolved scientific choices</h3>
          <ul>
            {interrupt.view.unresolved_scientific_choices.map((choice) => (
              <li key={choice}>{choice}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <label className="db-rag-feedback">
        <span>Revision feedback</span>
        <textarea
          disabled={disabled}
          onChange={(event) => setFeedback(event.target.value)}
          rows={4}
          value={feedback}
        />
      </label>
      {feedbackError ? <p role="alert">{feedbackError}</p> : null}

      <div className="db-rag-review-actions">
        {activeMode === "step" && conceptIndex > 0 ? (
          <button
            disabled={disabled}
            onClick={() => setConceptIndex((current) => current - 1)}
            type="button"
          >
            Previous concept
          </button>
        ) : null}
        <button
          disabled={disabled}
          onClick={() => onDecision({ action: "cancel" })}
          type="button"
        >
          Cancel review
        </button>
        <button disabled={disabled} onClick={revise} type="button">
          Request revision
        </button>
        {activeMode === "all" || isFinalConcept ? (
          <button
            disabled={disabled}
            onClick={() =>
              onDecision({
                action: "approve",
                selected_column_keys: approvedKeys,
              })
            }
            type="button"
          >
            Approve plan and extract
          </button>
        ) : (
          <button
            disabled={
              disabled ||
              (selectableKeys(currentGroup).length > 0 &&
                selectableKeys(currentGroup).every(
                  (key) => !selectedKeys.has(key),
                ))
            }
            onClick={() =>
              setConceptIndex((current) =>
                nextConceptIndex(current, groups.length),
              )
            }
            type="button"
          >
            Approve &amp; continue
          </button>
        )}
      </div>
    </section>
  );
}
