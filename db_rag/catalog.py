from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from .retrieval import retrieve_queries


CATALOG_VERSION = 1


class SchemaEvidenceHit(BaseModel):
    source: str | None = None
    table: str
    column: str | None = None
    text: str
    source_kind: Literal["schema"] = "schema"
    provenance: dict[str, str]


class SchemaCatalog:
    def __init__(
        self,
        catalog: dict[str, Any],
        *,
        table_collection: Any | None = None,
        column_collection: Any | None = None,
        default_source_id: str | None = None,
    ) -> None:
        self._catalog = dict(catalog)
        self._table_collection = table_collection
        self._column_collection = column_collection
        self._default_source_id = _as_text(default_source_id)

    def field_exists(self, table: str, column: str) -> bool:
        return any(
            _as_text(entry.get("table")) == table
            and _as_text(entry.get("column")) == column
            and entry.get("runtime_available", True) is not False
            for entry in self._catalog.get("columns", [])
            if isinstance(entry, dict)
        )

    def inspect_table(
        self,
        source: str,
        table: str,
        *,
        offset: int = 0,
        limit: int = 25,
    ) -> list[SchemaEvidenceHit]:
        if offset < 0 or limit < 1:
            return []
        rows = [
            dict(entry)
            for entry in self._catalog.get("columns", [])
            if isinstance(entry, dict)
            and _as_text(entry.get("table")) == table
            and entry.get("runtime_available", True) is not False
            and (
                _as_text(entry.get("source") or entry.get("source_id"))
                or self._default_source_id
            )
            == source
        ][offset : offset + limit]
        return [
            _schema_evidence_hit(
                row,
                default_source_id=self._default_source_id,
            )
            for row in rows
        ]

    def search(self, query: str, *, limit: int = 5) -> list[SchemaEvidenceHit]:
        return self.search_many([query], limit=limit)[0]

    def search_many(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[list[SchemaEvidenceHit]]:
        if not queries:
            return []
        if limit < 1:
            return [[] for _query in queries]
        if self._table_collection is not None and self._column_collection is not None:
            retrieved = retrieve_queries(
                self._table_collection,
                self._column_collection,
                queries,
                table_k=limit,
                column_k=limit,
            )
            row_batches = [
                _bounded_interleave(table_rows, column_rows, limit=limit)
                for table_rows, column_rows in retrieved
            ]
        else:
            row_batches = []
            entries = [
                *(
                    dict(entry)
                    for entry in self._catalog.get("tables", [])
                    if isinstance(entry, dict)
                ),
                *(
                    dict(entry)
                    for entry in self._catalog.get("columns", [])
                    if isinstance(entry, dict)
                ),
            ]
            for query in queries:
                terms = {
                    term.casefold()
                    for term in query.split()
                    if term.strip()
                }
                row_batches.append(
                    sorted(
                        entries,
                        key=lambda entry: sum(
                            term in _as_text(entry.get("text")).casefold()
                            for term in terms
                        ),
                        reverse=True,
                    )[:limit]
                )

        return [
            [
                _schema_evidence_hit(
                    row,
                    default_source_id=self._default_source_id,
                )
                for row in rows[:limit]
            ]
            for rows in row_batches
        ]


def _schema_evidence_hit(
    row: dict[str, Any],
    *,
    default_source_id: str = "",
) -> SchemaEvidenceHit:
    source = _as_text(row.get("source") or row.get("source_id"))
    source = source or default_source_id
    table = _as_text(row.get("table"))
    column = _as_text(row.get("column"))
    return SchemaEvidenceHit(
        source=source or None,
        table=table,
        column=column or None,
        text=_as_text(row.get("text")),
        provenance={
            "authority": "runtime_schema_catalog",
            **({"source_id": source} if source else {}),
            "table": table,
            **({"column": column} if column else {}),
        },
    )


def _bounded_interleave(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for index in range(max(len(first), len(second))):
        for rows in (first, second):
            if index < len(rows):
                merged.append(rows[index])
                if len(merged) == limit:
                    return merged
    return merged


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _chunk_metadata(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        metadata = chunk.get("metadata") or {}
        return dict(metadata) if isinstance(metadata, dict) else {}
    metadata = getattr(chunk, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _chunk_value(chunk: Any, key: str) -> Any:
    if isinstance(chunk, dict) and key in chunk:
        return chunk.get(key)
    metadata = _chunk_metadata(chunk)
    if key in metadata:
        return metadata.get(key)
    return getattr(chunk, key, None)


def _column_entry(chunk: Any) -> dict[str, Any]:
    metadata = _chunk_metadata(chunk)
    entry: dict[str, Any] = {
        "table": _as_text(_chunk_value(chunk, "table")),
        "column": _as_text(_chunk_value(chunk, "column")),
        "text": _as_text(_chunk_value(chunk, "text")),
    }
    for key in ("schema_column", "description"):
        value = _as_text(metadata.get(key))
        if value:
            entry[key] = value
    if "runtime_available" in metadata:
        entry["runtime_available"] = bool(metadata.get("runtime_available"))
    values_json = _as_text(metadata.get("values_json"))
    if values_json:
        try:
            values = json.loads(values_json)
        except json.JSONDecodeError:
            values = None
        if isinstance(values, dict):
            entry["values"] = values
    for key in ("depends_on", "condition", "section_context"):
        value = _as_text(metadata.get(key))
        if value:
            entry[key] = value
    return entry


def _table_entry(chunk: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "table": _as_text(_chunk_value(chunk, "table")),
        "text": _as_text(_chunk_value(chunk, "text")),
    }
    metadata = _chunk_metadata(chunk)
    for key in ("row_count", "subjid_col", "fid_col"):
        if key in metadata:
            entry[key] = metadata[key]
    for key in ("has_subjid_join", "has_fid_join"):
        if key in metadata:
            entry[key] = bool(metadata[key])
    return entry


def build_full_schema_catalog(
    *,
    table_chunks: list[Any],
    column_chunks: list[Any],
    source_fingerprint: str,
) -> dict[str, Any]:
    tables = [
        _table_entry(chunk)
        for chunk in list(table_chunks or [])
        if _as_text(_chunk_value(chunk, "table"))
    ]
    columns = [
        _column_entry(chunk)
        for chunk in list(column_chunks or [])
        if _as_text(_chunk_value(chunk, "table")) and _as_text(_chunk_value(chunk, "column"))
    ]
    return {
        "catalog_version": CATALOG_VERSION,
        "source_fingerprint": _as_text(source_fingerprint),
        "include_excel_profiles": True,
        "contains_raw_excel_rows": False,
        "tables": tables,
        "columns": columns,
        "stats": {
            "tables": len(tables),
            "columns": len(columns),
            "table_chars": sum(len(entry["text"]) for entry in tables),
            "column_chars": sum(len(entry["text"]) for entry in columns),
        },
    }


def write_full_schema_catalog(path: Path, catalog: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_full_schema_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
