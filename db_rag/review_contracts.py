from __future__ import annotations

from typing import Any

def _column_key(column: dict[str, Any]) -> str:
    source = str(dict(column or {}).get("source") or "").strip()
    table = str(dict(column or {}).get("table") or "").strip()
    name = str(dict(column or {}).get("column") or "").strip()
    if not table or not name:
        return ""
    return "::".join(part for part in (source, table, name) if part)


def _column_pair(column: dict[str, Any]) -> tuple[str, ...]:
    source = str(dict(column or {}).get("source") or "").strip().lower()
    table = str(dict(column or {}).get("table") or "").strip().lower()
    name = str(dict(column or {}).get("column") or "").strip().lower()
    if not table or not name:
        return ()
    return tuple(part for part in (source, table, name) if part)


def _table_pair(column: dict[str, Any]) -> tuple[str, ...]:
    source = str(dict(column or {}).get("source") or "").strip().lower()
    table = str(dict(column or {}).get("table") or "").strip().lower()
    if not table:
        return ()
    return tuple(part for part in (source, table) if part)


def _column_pair_in_context(
    column: dict[str, Any],
    available_pairs: set[tuple[str, ...]],
) -> tuple[str, ...]:
    identity = _column_pair(column)
    if len(identity) != 2:
        return identity
    matches = {
        pair
        for pair in available_pairs
        if len(pair) == 3 and pair[-2:] == identity
    }
    return next(iter(matches)) if len(matches) == 1 else identity


def _build_grouped_review(review: dict[str, Any]) -> dict[str, Any]:
    columns = [
        dict(column)
        for column in list(review.get("columns") or [])
        if isinstance(column, dict)
    ]
    user_columns = [
        {**column, "key": _column_key(column), "selected": True}
        for column in columns
    ]

    available_pairs = {
        _column_pair(column)
        for column in columns
        if _column_pair(column)
    }
    filters_by_pair: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    row_filters = dict(review.get("row_filters") or {})
    for filter_entry in [
        *list(row_filters.get("population") or []),
        *list(row_filters.get("data_quality") or []),
        *list(row_filters.get("explicit_value") or []),
    ]:
        if not isinstance(filter_entry, dict):
            continue
        for ref in [
            *list(filter_entry.get("referenced_columns") or []),
            *[
                {
                    "source": item.get("source"),
                    "table": item.get("table"),
                    "column": item.get("column"),
                }
                for item in list(filter_entry.get("value_constraints") or [])
                if isinstance(item, dict)
            ],
        ]:
            if isinstance(ref, dict):
                pair = _column_pair_in_context(ref, available_pairs)
                if pair:
                    filters_by_pair.setdefault(pair, []).append(
                        dict(filter_entry)
                    )

    intent_snapshot = dict(review.get("intent_snapshot") or {})
    intent = dict(review.get("intent") or {})
    clinical_concepts = list(
        intent_snapshot.get("clinical_concepts")
        or intent.get("clinical_concepts")
        or []
    )
    assignments = {
        str(assignment.get("concept_id") or "").strip(): dict(assignment)
        for assignment in list(
            intent_snapshot.get("clinical_concept_assignments")
            or intent.get("clinical_concept_assignments")
            or []
        )
        if isinstance(assignment, dict)
        and str(assignment.get("concept_id") or "").strip()
    }
    columns_by_pair = {
        _column_pair(column): column for column in user_columns
    }
    assigned_pairs: set[tuple[str, ...]] = set()
    groups: list[dict[str, Any]] = []
    for concept in clinical_concepts:
        if not isinstance(concept, dict):
            continue
        concept_id = str(concept.get("concept_id") or "").strip()
        concept_label = str(concept.get("label") or "").strip()
        if not concept_id or not concept_label:
            continue
        assignment = assignments.get(concept_id, {})
        group_columns: list[dict[str, Any]] = []
        for reference in list(assignment.get("columns") or []):
            if not isinstance(reference, dict):
                continue
            pair = _column_pair(reference)
            column = columns_by_pair.get(pair)
            if column is None:
                continue
            assigned_pairs.add(pair)
            group_columns.append(
                {
                    **column,
                    "filters": list(filters_by_pair.get(pair) or []),
                }
            )
        groups.append(
            {
                "concept_id": concept_id,
                "concept_label": concept_label,
                "kind": "clinical",
                "columns": group_columns,
                "unresolved_reason": str(
                    assignment.get("unresolved_reason") or ""
                ).strip(),
            }
        )

    unassigned_columns = [
        {
            **column,
            "filters": list(
                filters_by_pair.get(_column_pair(column)) or []
            ),
        }
        for column in user_columns
        if _column_pair(column) not in assigned_pairs
    ]
    if unassigned_columns:
        groups.append(
            {
                "concept_id": "additional_selected_fields",
                "concept_label": "Additional selected fields",
                "kind": "additional",
                "columns": unassigned_columns,
                "unresolved_reason": "",
            }
        )

    for group in groups:
        group_tables = {
            _table_pair(column)
            for column in list(group.get("columns") or [])
            if _table_pair(column)
        }
    return {"groups": groups}


__all__ = [
    "_build_grouped_review",
    "_column_key",
]
