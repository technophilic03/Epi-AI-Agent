import type { ClarificationExchange } from "./types";

interface Props {
  exchanges: ClarificationExchange[];
}

export default function ClarificationTrace({ exchanges }: Props) {
  if (!exchanges.length) {
    return null;
  }

  return (
    <details className="clarification-trace">
      <summary>Clarification trace</summary>
      <ol>
        {exchanges.map((exchange) => (
          <li key={exchange.interrupt_id}>
            <p>
              <strong>Question:</strong> {exchange.question}
            </p>
            {exchange.reason ? (
              <p>
                <strong>Reason:</strong> {exchange.reason}
              </p>
            ) : null}
            <p>
              <strong>Answer:</strong> {exchange.answer}
            </p>
          </li>
        ))}
      </ol>
    </details>
  );
}
