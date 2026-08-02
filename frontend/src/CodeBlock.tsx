import type { ReactNode } from "react";

interface Props {
  actions?: ReactNode;
  code: string;
  label?: string;
  language?: string;
}

interface Token {
  className?: string;
  text: string;
}

const SQL_KEYWORDS = new Set([
  "select",
  "from",
  "where",
  "join",
  "left",
  "right",
  "inner",
  "outer",
  "on",
  "and",
  "or",
  "as",
  "case",
  "when",
  "then",
  "else",
  "end",
  "group",
  "by",
  "order",
  "having",
  "limit",
  "distinct",
  "count",
  "sum",
  "avg",
  "min",
  "max",
  "null",
  "is",
  "not",
  "in",
  "like",
]);

const PYTHON_KEYWORDS = new Set([
  "False",
  "None",
  "True",
  "and",
  "as",
  "assert",
  "break",
  "class",
  "continue",
  "def",
  "elif",
  "else",
  "except",
  "finally",
  "for",
  "from",
  "if",
  "import",
  "in",
  "is",
  "lambda",
  "not",
  "or",
  "pass",
  "raise",
  "return",
  "try",
  "while",
  "with",
  "yield",
]);

function normalizeLanguage(language: string | undefined): string {
  const normalized = String(language || "text").toLowerCase();
  if (normalized === "py") {
    return "python";
  }
  if (normalized === "js") {
    return "javascript";
  }
  return normalized;
}

function tokenize(code: string, language: string): Token[] {
  const pattern =
    /(--[^\n]*|#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b|[{}[\]():.,<>=+\-*/%]+)/g;
  const tokens: Token[] = [];
  let cursor = 0;
  for (const match of code.matchAll(pattern)) {
    const text = match[0];
    const index = match.index ?? 0;
    if (index > cursor) {
      tokens.push({ text: code.slice(cursor, index) });
    }
    tokens.push(classifyToken(text, language, code, index));
    cursor = index + text.length;
  }
  if (cursor < code.length) {
    tokens.push({ text: code.slice(cursor) });
  }
  return tokens;
}

function classifyToken(text: string, language: string, code: string, index: number): Token {
  if (text.startsWith("--") || text.startsWith("#")) {
    return { className: "syntax-comment", text };
  }
  if (
    (text.startsWith('"') && text.endsWith('"')) ||
    (text.startsWith("'") && text.endsWith("'"))
  ) {
    if (language === "json" && code.slice(index + text.length).trimStart().startsWith(":")) {
      return { className: "syntax-property", text };
    }
    return { className: "syntax-string", text };
  }
  if (/^\d/.test(text)) {
    return { className: "syntax-number", text };
  }
  const lowered = text.toLowerCase();
  if (language === "sql" && SQL_KEYWORDS.has(lowered)) {
    return { className: "syntax-keyword", text };
  }
  if (language === "python") {
    if (PYTHON_KEYWORDS.has(text)) {
      return { className: "syntax-keyword", text };
    }
    if (code.slice(index + text.length).trimStart().startsWith("(")) {
      return { className: "syntax-function", text };
    }
  }
  if (language === "json" && ["true", "false", "null"].includes(lowered)) {
    return { className: "syntax-keyword", text };
  }
  if (/^[{}[\]():.,<>=+\-*/%]+$/.test(text)) {
    return { className: "syntax-punctuation", text };
  }
  return { text };
}

export default function CodeBlock({
  actions,
  code,
  label,
  language = "text",
}: Props) {
  const normalizedLanguage = normalizeLanguage(language);
  const tokens = tokenize(code, normalizedLanguage);
  const includePlainTextFallback = normalizedLanguage !== "text";

  if (!code.trim()) {
    return null;
  }

  return (
    <figure className={`code-block code-block-${normalizedLanguage}`}>
      {label || actions ? (
        <figcaption>
          {label ? <span>{label}</span> : <span />}
          {actions}
        </figcaption>
      ) : null}
      <pre>
        <code
          aria-hidden={includePlainTextFallback ? true : undefined}
          className={`language-${normalizedLanguage}`}
        >
          {tokens.map((token, index) =>
            token.className ? (
              <span className={`syntax-token ${token.className}`} key={index}>
                {token.text}
              </span>
            ) : (
              token.text
            ),
          )}
        </code>
        {includePlainTextFallback ? (
          <code className="code-block-plain-text">{code}</code>
        ) : null}
      </pre>
    </figure>
  );
}
