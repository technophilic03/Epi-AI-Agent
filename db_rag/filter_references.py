from __future__ import annotations

from typing import Any, Iterable


FieldReference = tuple[str, str, str]


class FilterReferenceResolutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def field_reference(value: Any) -> FieldReference:
    item = dict(value) if isinstance(value, dict) else {}
    return (
        str(item.get("source") or "").strip(),
        str(item.get("table") or "").strip(),
        str(item.get("column") or "").strip(),
    )


def resolve_filter_reference(
    value: Any,
    *,
    available_fields: Iterable[FieldReference],
) -> dict[str, Any]:
    item = dict(value) if isinstance(value, dict) else {}
    source, table, column = field_reference(item)
    label = f"{table}.{column}" if table and column else "malformed reference"
    available = set(available_fields)
    if not table or not column:
        raise FilterReferenceResolutionError(
            "PLAN_FILTER_REFERENCE_UNRESOLVED",
            f"Dataset-plan filter contains an unresolved {label}.",
        )
    if source:
        if (source, table, column) not in available:
            raise FilterReferenceResolutionError(
                "PLAN_FILTER_REFERENCE_UNRESOLVED",
                (
                    f"Dataset-plan filter reference {source}::{label} does not "
                    "match a selected plan field."
                ),
            )
        return {
            **item,
            "source": source,
            "table": table,
            "column": column,
        }

    sources = sorted(
        {
            candidate_source
            for candidate_source, candidate_table, candidate_column in available
            if candidate_table == table and candidate_column == column
        }
    )
    if not sources:
        raise FilterReferenceResolutionError(
            "PLAN_FILTER_REFERENCE_UNRESOLVED",
            (
                f"Dataset-plan filter reference {label} does not match a plan "
                "selected plan field."
            ),
        )
    if len(sources) > 1:
        raise FilterReferenceResolutionError(
            "PLAN_FILTER_REFERENCE_AMBIGUOUS",
            (
                f"Dataset-plan filter reference {label} matches multiple "
                f"sources: {', '.join(sources)}."
            ),
        )
    return {
        **item,
        "source": sources[0],
        "table": table,
        "column": column,
    }


def resolve_filter_references(
    filters: Iterable[dict[str, Any]],
    *,
    available_fields: Iterable[FieldReference],
) -> list[dict[str, Any]]:
    available = set(available_fields)
    resolved: list[dict[str, Any]] = []
    for value in filters:
        item = dict(value)
        for key in ("referenced_columns", "value_constraints"):
            if key not in item:
                continue
            item[key] = [
                resolve_filter_reference(
                    reference,
                    available_fields=available,
                )
                for reference in list(item.get(key) or [])
            ]
        resolved.append(item)
    return resolved


__all__ = [
    "FieldReference",
    "FilterReferenceResolutionError",
    "field_reference",
    "resolve_filter_reference",
    "resolve_filter_references",
]
