import type {
  ModelOutputLimitInterrupt,
  ResumeInterruptPayload,
} from "./types";

interface Props {
  disabled: boolean;
  interrupt: ModelOutputLimitInterrupt;
  onResume(payload: ResumeInterruptPayload): void;
}

export default function ModelOutputLimit({
  disabled,
  interrupt,
  onResume,
}: Props) {
  return (
    <section
      aria-labelledby="model-output-limit-heading"
      className="model-output-limit-panel"
    >
      <h2 id="model-output-limit-heading">More output needed</h2>
      <p>{interrupt.message}</p>
      <p className="model-output-limit-note">
        The model stays the same and continues this response.
      </p>
      <div className="model-output-limit-actions">
        <button
          disabled={disabled}
          onClick={() => onResume({ action: "continue" })}
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
