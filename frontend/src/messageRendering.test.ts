import { describe, expect, it } from "vitest";
import { parseAssistantMessage } from "./messageRendering";

describe("parseAssistantMessage", () => {
  it("extracts sql fenced blocks", () => {
    const parts = parseAssistantMessage("SQL used:\n```sql\nSELECT 1;\n```\nDone.");

    expect(parts).toEqual([
      { type: "code", language: "sql", code: "SELECT 1;" },
      { type: "text", text: "Done." },
    ]);
  });

  it("extracts multiple fenced code languages", () => {
    const parts = parseAssistantMessage(
      "Python:\n```python\nprint('done')\n```\nJSON:\n```json\n{\"ok\": true}\n```",
    );

    expect(parts).toEqual([
      { type: "text", text: "Python:" },
      { type: "code", language: "python", code: "print('done')" },
      { type: "text", text: "JSON:" },
      { type: "code", language: "json", code: "{\"ok\": true}" },
    ]);
  });

  it("formats JSON answer messages as summary text", () => {
    const parts = parseAssistantMessage(
      JSON.stringify({
        answer: "Dataset subset-1 was created.",
        needs_clarification: false,
        clarification_question: null,
      }),
    );

    expect(parts).toEqual([
      { type: "text", text: "Dataset subset-1 was created." },
    ]);
  });

  it("compacts DB-RAG dataset completion messages", () => {
    const parts = parseAssistantMessage(
      [
        "Read-only SQL execution completed with 2 result row(s). Dataset `dataset-art-1` was created with 2 rows.",
        "",
        "Included columns:",
        "- Analysis columns: `Form 2A.IC_AGE`",
        "",
        "Filters:",
        "- Data quality: Exclude missing values.",
        "",
        "SQL used:",
        "```sql",
        "select IC_AGE from \"Form 2A\"",
        "```",
      ].join("\n"),
    );

    expect(parts).toEqual([
      {
        type: "dbRagDatasetResult",
        datasetId: "dataset-art-1",
        rowCount: "2",
        summary:
          "Dataset `dataset-art-1` was created with 2 rows. Preview or download it from Generated datasets below.",
        details:
          "Included columns:\n- Analysis columns: `Form 2A.IC_AGE`\n\nFilters:\n- Data quality: Exclude missing values.",
        sql: 'select IC_AGE from "Form 2A"',
      },
    ]);
  });
});
