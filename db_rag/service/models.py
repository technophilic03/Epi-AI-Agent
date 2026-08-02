from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DbRagTableHit:
    table: str
    text: str


@dataclass
class DbRagColumnHit:
    table: str
    column: str
    text: str
    score: float | None = None
    clinical_concept_ids: tuple[str, ...] = ()
    technical_need_ids: tuple[str, ...] = ()

    def as_prompt_line(self) -> str:
        return f"{self.table}.{self.column}"


@dataclass
class DbRagContext:
    tables: list[DbRagTableHit] = field(default_factory=list)
    columns: list[DbRagColumnHit] = field(default_factory=list)
    table_context: str = ""
    column_context: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def table_names(self) -> list[str]:
        return [entry.table for entry in self.tables]

    @property
    def column_names(self) -> list[str]:
        return [entry.column for entry in self.columns]


@dataclass
class ColumnSelectionCandidate:
    selection_id: str
    question: str
    tables: list[str]
    columns: list[dict[str, str]]
    rationale: str
    feedback_history: list[dict[str, Any]] = field(default_factory=list)
    status: str = "awaiting_review"
    selection_source: str = "legacy"
    fallback_reason: str = ""
    raw_model_output: str = ""
    variable_roles: dict[str, Any] = field(default_factory=dict)
    row_filters: dict[str, Any] = field(default_factory=dict)
    protected_columns: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PreparedSqlCandidate:
    question: str
    sql: str
    tables: list[str]
    columns: list[dict[str, str]]
    selection_id: str
    status: str = "prepared"
    variable_roles: dict[str, Any] = field(default_factory=dict)
    row_filters: dict[str, Any] = field(default_factory=dict)
    protected_columns: list[dict[str, Any]] = field(default_factory=list)
    applied_filters: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ValidatedExtractionSql:
    sql: str
    sha256: str


@dataclass
class SqlExecutionResult:
    answer: str
    sql: str
    dataframe: Any
    source_tables: list[str]
