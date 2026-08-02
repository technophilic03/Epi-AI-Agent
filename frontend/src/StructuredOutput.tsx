interface Props {
  output: Record<string, unknown>;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export default function StructuredOutput({ output }: Props) {
  const qaResponse = stringValue(output.qa_response);
  const answer = stringValue(output.answer);
  const clarificationQuestion = stringValue(output.clarification_question);
  const datasetId = stringValue(output.dataset_id);
  const needsClarification = output.needs_clarification === true;
  const displayAnswer = qaResponse || answer;
  const hasContent =
    Boolean(displayAnswer) || (needsClarification && Boolean(clarificationQuestion));

  if (!hasContent && !datasetId) {
    return null;
  }

  return (
    <section className="structured-output-panel" aria-label="Structured output">
      <h3>Agent output</h3>
      {displayAnswer ? (
        <div className="structured-output-card">
          <h4>{qaResponse ? "QA answer" : "Answer"}</h4>
          <p>{displayAnswer}</p>
        </div>
      ) : null}
      {needsClarification && clarificationQuestion ? (
        <div className="structured-output-card structured-output-warning">
          <h4>Clarification needed</h4>
          <p>{clarificationQuestion}</p>
        </div>
      ) : null}
      {datasetId ? (
        <div className="structured-output-card">
          <h4>Related dataset</h4>
          <p>
            <code className="inline-code">{datasetId}</code>
          </p>
        </div>
      ) : null}
    </section>
  );
}
