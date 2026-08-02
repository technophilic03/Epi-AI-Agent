import "@testing-library/jest-dom/vitest";
// @ts-expect-error Vitest resolves Node built-ins; the browser build excludes tests.
import { readFileSync } from "node:fs";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CodeBlock from "./CodeBlock";

describe("CodeBlock", () => {
  it("uses a shrinkable layout contract inside message attachments", () => {
    const styles = readFileSync("src/styles.css", "utf8");

    expect(styles).toMatch(/\.message-attachment-list[^}]*min-width:\s*0;/s);
    expect(styles).toMatch(/\.message-attachment-list[^}]*max-width:\s*100%;/s);
    expect(styles).toMatch(
      /\.message-used-files,[^}]*\.message-attachment-list\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(/\.code-block\s*\{[^}]*min-width:\s*0;/s);
    expect(styles).toMatch(/\.code-block\s*\{[^}]*max-width:\s*100%;/s);
    expect(styles).toMatch(/\.code-block\s*\{[^}]*width:\s*100%;/s);
    expect(styles).toMatch(/\.code-block\s*\{[^}]*box-sizing:\s*border-box;/s);
    expect(styles).toMatch(
      /\.message-attachment-card\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.dataset-details\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.db-rag-dataset-review-panel\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.db-rag-dataset-review-panel\s*\{[^}]*width:\s*min\(100%,\s*920px\);/s,
    );
    expect(styles).toMatch(
      /\.analysis-run-attachment\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.dataset-sql,[^}]*\.analysis-output-lineage\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.analysis-output-lineage\s*>\s*details\s*\{[^}]*min-width:\s*0;[^}]*max-width:\s*100%;/s,
    );
    expect(styles).toMatch(
      /\.db-rag-dataset-review-header,[^}]*\.db-rag-dataset-review-section,[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/s,
    );
    expect(styles).toMatch(
      /\.dataset-preview[^}]*min-width:\s*0;[^}]*max-width:\s*100%;/s,
    );
  });

  it("highlights SQL keywords, strings, and numbers", () => {
    render(
      <CodeBlock
        code={"select age from subject where gender = 'male' and age >= 18"}
        label="Prepared SQL"
        language="sql"
      />,
    );

    expect(screen.getByText("Prepared SQL")).toBeInTheDocument();
    expect(screen.getByText("select")).toHaveClass("syntax-keyword");
    expect(screen.getByText("'male'")).toHaveClass("syntax-string");
    expect(screen.getByText("18")).toHaveClass("syntax-number");
  });

  it("highlights Python keywords and strings", () => {
    render(
      <CodeBlock
        code={"import pandas as pd\nprint('ready')"}
        label="Python"
        language="python"
      />,
    );

    expect(screen.getByText("import")).toHaveClass("syntax-keyword");
    expect(screen.getByText("print")).toHaveClass("syntax-function");
    expect(screen.getByText("'ready'")).toHaveClass("syntax-string");
  });

  it("highlights JSON keys and values without using raw HTML", () => {
    render(
      <CodeBlock
        code={'{"schema": {"age": 42, "safe": "<script>"}}'}
        label="Schema"
        language="json"
      />,
    );

    expect(screen.getByText('"schema"')).toHaveClass("syntax-property");
    expect(screen.getByText("42")).toHaveClass("syntax-number");
    expect(screen.getByText('"<script>"')).toHaveClass("syntax-string");
  });
});
