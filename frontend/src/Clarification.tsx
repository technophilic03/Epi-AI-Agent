import { useState } from "react";
import {
  AGENT_DECIDE_ANSWER,
  type ActiveInterrupt,
  type ResumeInterruptPayload,
} from "./types";

type ClarificationInterrupt = Extract<
  ActiveInterrupt,
  { type: "agent_clarification" }
>;

interface Props {
  disabled?: boolean;
  interrupt: ClarificationInterrupt;
  onResume: (payload: ResumeInterruptPayload) => void;
}

const FEEDBACK_CHOICE = "feedback";
const AGENT_DECIDE_CHOICE = "agent-decide";

export default function Clarification({
  disabled = false,
  interrupt,
  onResume,
}: Props) {
  const [selectedChoice, setSelectedChoice] = useState("");
  const [feedback, setFeedback] = useState("");
  const trimmedFeedback = feedback.trim();
  const selectedOption = interrupt.options.find(
    (option) => option.id === selectedChoice,
  );
  const canContinue = Boolean(
    selectedOption ||
      selectedChoice === AGENT_DECIDE_CHOICE ||
      (selectedChoice === FEEDBACK_CHOICE && trimmedFeedback),
  );

  function selectChoice(choice: string) {
    setSelectedChoice(choice);
    if (choice !== FEEDBACK_CHOICE) {
      setFeedback("");
    }
  }

  function submit() {
    if (!canContinue) {
      return;
    }
    const answer = selectedOption
      ? selectedOption.label
      : selectedChoice === AGENT_DECIDE_CHOICE
        ? AGENT_DECIDE_ANSWER
        : trimmedFeedback;
    onResume({ action: "answer", answer });
  }

  return (
    <section className="code-review-panel clarification-panel" aria-labelledby="clarification-heading">
      <h2 id="clarification-heading">Clarification needed</h2>
      <p>{interrupt.question}</p>
      {interrupt.reason ? <p>{interrupt.reason}</p> : null}
      <fieldset className="clarification-options" disabled={disabled} role="radiogroup">
        <legend>Your answer</legend>
        {interrupt.options.map((option) => (
          <label className="clarification-option" key={option.id}>
            <input
              checked={selectedChoice === option.id}
              name="clarification-choice"
              onChange={() => selectChoice(option.id)}
              type="radio"
              value={option.id}
            />
            <span>{option.label}</span>
          </label>
        ))}
        <label className="clarification-option" htmlFor="clarification-feedback-choice">
          <input
            checked={selectedChoice === FEEDBACK_CHOICE}
            id="clarification-feedback-choice"
            name="clarification-choice"
            onChange={() => selectChoice(FEEDBACK_CHOICE)}
            type="radio"
            value={FEEDBACK_CHOICE}
          />
          <span>Provide feedback</span>
        </label>
        {selectedChoice === FEEDBACK_CHOICE ? (
          <label className="clarification-feedback" htmlFor="clarification-feedback">
            <span>Feedback</span>
            <textarea
              disabled={disabled}
              id="clarification-feedback"
              onChange={(event) => setFeedback(event.target.value)}
              rows={3}
              value={feedback}
            />
          </label>
        ) : null}
        <label className="clarification-option" htmlFor="clarification-agent-decide">
          <input
            checked={selectedChoice === AGENT_DECIDE_CHOICE}
            id="clarification-agent-decide"
            name="clarification-choice"
            onChange={() => selectChoice(AGENT_DECIDE_CHOICE)}
            type="radio"
            value={AGENT_DECIDE_CHOICE}
          />
          <span>Let the agent decide</span>
        </label>
      </fieldset>
      <div className="code-review-actions">
        <button
          className="clarification-continue"
          disabled={disabled || !canContinue}
          onClick={submit}
          type="button"
        >
          Continue
        </button>
        <button
          disabled={disabled}
          onClick={() => onResume({ action: "cancel" })}
          type="button"
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
