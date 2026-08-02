export type MessagePart =
  | { type: "text"; text: string }
  | { type: "code"; language: string; code: string }
  | {
      type: "dbRagDatasetResult";
      datasetId: string;
      details: string;
      rowCount: string;
      sql: string;
      summary: string;
    };

function parseJsonAnswer(text: string): MessagePart[] | null {
  try {
    const parsed = JSON.parse(text) as unknown;
    if (
      parsed &&
      typeof parsed === "object" &&
      "answer" in parsed &&
      typeof (parsed as { answer?: unknown }).answer === "string"
    ) {
      return [
        {
          type: "text",
          text: (parsed as { answer: string }).answer.trim(),
        },
      ];
    }
  } catch {
    return null;
  }

  return null;
}

function parseDbRagDatasetResult(text: string): MessagePart[] | null {
  const datasetMatch = text.match(
    /Dataset\s+`([^`]+)`\s+was created(?:\s+with\s+([0-9,]+)\s+rows?)?\.?/i,
  );
  if (!datasetMatch || !/SQL used:/i.test(text)) {
    return null;
  }

  const sqlMatch = text.match(/SQL used:\s*```(?:sql)?\s*([\s\S]*?)```/i);
  const datasetId = datasetMatch[1];
  const rowCount = datasetMatch[2] ?? "";
  const completionSentence = rowCount
    ? `Dataset \`${datasetId}\` was created with ${rowCount} rows.`
    : `Dataset \`${datasetId}\` was created.`;

  const detailsStart = (datasetMatch.index ?? 0) + datasetMatch[0].length;
  const detailsEnd = sqlMatch?.index ?? text.length;
  const details = text.slice(detailsStart, detailsEnd).trim();
  const sql = sqlMatch?.[1]?.trim() ?? "";

  return [
    {
      type: "dbRagDatasetResult",
      datasetId,
      details,
      rowCount,
      sql,
      summary: `${completionSentence} Preview or download it from Generated datasets below.`,
    },
  ];
}

export function parseAssistantMessage(text: string): MessagePart[] {
  const trimmed = text.trim();
  const jsonAnswer = parseJsonAnswer(trimmed);
  if (jsonAnswer) {
    return jsonAnswer;
  }
  const dbRagDatasetResult = parseDbRagDatasetResult(trimmed);
  if (dbRagDatasetResult) {
    return dbRagDatasetResult;
  }

  const parts: MessagePart[] = [];
  const pattern = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    const before = text.slice(cursor, match.index).trim();
    if (before && before !== "SQL used:" && before !== "SQL used") {
      parts.push({ type: "text", text: before });
    }
    parts.push({
      type: "code",
      language: (match[1] || "text").toLowerCase(),
      code: match[2].trim(),
    });
    cursor = match.index + match[0].length;
  }

  const after = text.slice(cursor).trim();
  if (after) {
    parts.push({ type: "text", text: after });
  }

  return parts.length ? parts : [{ type: "text", text }];
}
