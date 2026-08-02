from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from db_rag.service.dataset_naming import generate_dataset_name
from db_rag.service.schema import _lookup_schema_variable_metadata
from graph.state import MetaKeys
from utils.dataset_artifacts import (
    DEFAULT_RUNTIME_ROOT,
    StagedDatasetArtifact,
    persist_dataset_artifact,
    register_dataset_artifact,
    stage_dataset_artifact,
)


_COLUMN_METADATA_FIELDS = (
    "semantic",
    "reason",
    "values",
    "depends_on",
    "condition",
    "section_context",
    "column_profile",
)


def _read_value(payload: Any, field: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(field, default)
    return getattr(payload, field, default)


def _string_list(values: Any) -> list[str]:
    result: list[str] = []
    for value in list(values or []):
        text = str(value or "").strip()
        if text:
            result.append(text)
    return result


def _normalize_population_scope(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    population = str(raw.get("population") or "").strip().lower() or None
    if population not in {
        "index_case",
        "household_contact",
        "unclear",
        "not_applicable",
    }:
        population = "not_applicable"
    try:
        confidence = float(raw.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "population": population,
        "warning": str(raw.get("warning") or "").strip(),
        "confidence": max(0.0, min(1.0, confidence)),
        "reason": str(raw.get("reason") or "").strip(),
    }


def serialize_columns(columns: Any) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for column in list(columns or []):
        source = str(_read_value(column, "source", "") or "").strip()
        table = str(_read_value(column, "table", "") or "").strip()
        column_name = str(_read_value(column, "column", "") or "").strip()
        output_column = str(
            _read_value(column, "output_column", "") or ""
        ).strip()
        purpose = str(_read_value(column, "purpose", "") or "").strip()
        description = str(
            _read_value(column, "description", "") or ""
        ).strip()
        if not table or not column_name:
            continue
        entry: dict[str, Any] = {"table": table, "column": column_name}
        if source:
            entry["source"] = source
        if output_column:
            entry["output_column"] = output_column
        if purpose:
            entry["purpose"] = purpose
        if description:
            entry["description"] = description
        for field in _COLUMN_METADATA_FIELDS:
            value = _read_value(column, field, None)
            if value is not None and value != "":
                entry[field] = value
        serialized.append(entry)
    return serialized


def _sql_candidate_review_texts(
    candidate: Any,
    approved_selection: dict[str, Any],
) -> tuple[str, str]:
    candidate_source = str(
        _read_value(candidate, "source_question", "") or ""
    ).strip()
    candidate_goal = str(
        _read_value(candidate, "goal_text", "") or ""
    ).strip()
    candidate_question = str(
        _read_value(candidate, "question", "") or ""
    ).strip()
    selection_source = str(
        approved_selection.get("source_question") or ""
    ).strip()
    selection_goal = str(
        approved_selection.get("goal_text") or ""
    ).strip()
    source_question = (
        candidate_source or selection_source or candidate_question
    )
    goal_text = (
        candidate_goal
        or selection_goal
        or candidate_question
        or source_question
    )
    return source_question, goal_text


def _projection_aliases_to_selected_columns(
    sql: str,
    selected_columns: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    sql_text = str(sql or "").strip()
    if not sql_text:
        return {}
    selected_by_pair = {
        (
            str(column.get("table") or "").strip(),
            str(column.get("column") or "").strip(),
        ): dict(column)
        for column in selected_columns
        if str(column.get("column") or "").strip()
    }
    selected_by_column: dict[str, list[dict[str, Any]]] = {}
    for column in selected_columns:
        column_name = str(column.get("column") or "").strip()
        if column_name:
            selected_by_column.setdefault(column_name, []).append(
                dict(column)
            )

    def match(source_table: str, source_name: str) -> dict[str, Any] | None:
        matched = (
            selected_by_pair.get((source_table, source_name))
            if source_table
            else None
        )
        if matched is None:
            candidates = selected_by_column.get(source_name) or []
            if len(candidates) == 1:
                matched = candidates[0]
        return dict(matched) if matched is not None else None

    try:
        import sqlglot
        from sqlglot import exp

        expression = sqlglot.parse_one(sql_text, dialect="duckdb")
    except Exception:
        aliases: dict[str, dict[str, Any]] = {}
        for table_token, column_token, alias_token in re.findall(
            r'(?is)(?:"?([A-Za-z_][A-Za-z0-9_]*)"?\.)?"?([A-Za-z_][A-Za-z0-9_]*)"?\s+AS\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
            sql_text,
        ):
            matched = match(
                str(table_token or "").strip(),
                str(column_token or "").strip(),
            )
            output_name = str(alias_token or "").strip()
            if matched is not None and output_name:
                aliases[output_name] = matched
        return aliases

    select = expression.find(exp.Select)
    if select is None:
        return {}
    aliases: dict[str, dict[str, Any]] = {}
    for projection in list(select.expressions or []):
        output_name = str(
            getattr(projection, "alias_or_name", "") or ""
        ).strip()
        source_column = next(iter(projection.find_all(exp.Column)), None)
        if not output_name or source_column is None:
            continue
        matched = match(
            str(getattr(source_column, "table", "") or "").strip(),
            str(getattr(source_column, "name", "") or "").strip(),
        )
        if matched is not None:
            aliases[output_name] = matched
    return aliases


def _selected_columns_by_output_position(
    dataframe: Any,
    selected_columns: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    output_columns = [
        str(name or "").strip()
        for name in list(getattr(dataframe, "columns", []))
    ]
    approved_columns = [
        dict(column)
        for column in selected_columns
        if str(column.get("column") or "").strip()
    ]
    if not output_columns or len(output_columns) != len(approved_columns):
        return {}
    return {
        output_columns[index]: approved_columns[index]
        for index in range(len(output_columns))
        if output_columns[index]
    }


def _build_subset_schema(
    dataframe: Any,
    selected_columns: list[dict[str, Any]],
    *,
    sql: str,
) -> dict[str, dict[str, Any]]:
    selected_by_name = {
        str(column.get("column") or "").strip(): column
        for column in selected_columns
        if str(column.get("column") or "").strip()
    }
    selected_by_alias = _projection_aliases_to_selected_columns(
        sql,
        selected_columns,
    )
    selected_by_position = _selected_columns_by_output_position(
        dataframe,
        selected_columns,
    )
    schema: dict[str, dict[str, Any]] = {}
    dtypes = getattr(dataframe, "dtypes", None)
    for column_name in list(getattr(dataframe, "columns", [])):
        column_key = str(column_name)
        selected = (
            selected_by_name.get(column_key)
            or selected_by_alias.get(column_key)
            or selected_by_position.get(column_key)
            or {}
        )
        table_name = str(selected.get("table") or "").strip()
        reviewed_meta = _lookup_schema_variable_metadata(
            table_name,
            column_key,
        )
        if reviewed_meta is None:
            selected_name = str(selected.get("column") or "").strip()
            if selected_name:
                reviewed_meta = _lookup_schema_variable_metadata(
                    table_name,
                    selected_name,
                )
        meta: dict[str, Any] = {}
        description = str(
            (reviewed_meta or {}).get("description")
            or selected.get("description")
            or ""
        ).strip()
        if description:
            meta["description"] = description
        for field in (
            "values",
            "depends_on",
            "condition",
            "section_context",
        ):
            value = (reviewed_meta or {}).get(field)
            if value is not None and value != "":
                meta[field] = value
        if dtypes is not None:
            meta["dataType"] = str(dtypes[column_name])
        schema[column_key] = meta
    return schema


def persist_sql_subset_artifact(
    state: dict[str, Any],
    candidate: Any,
    approved_selection: dict[str, Any],
    execution_result: Any,
    *,
    selection_artifact_id: str | None,
    sql_candidate_artifact_id: str | None,
    plan_id: str | None = None,
    plan_version: int | None = None,
    sql_version: int | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    exact_sql: str | None = None,
    predecessor_dataset_id: str | None = None,
    predecessor_dataset_version: int | None = None,
    relationship_metrics: list[dict[str, Any]] | None = None,
    join_expansion: dict[str, float] | None = None,
    grain_columns: list[str] | None = None,
    runtime_root: Any = None,
    make_active: bool = True,
    stage_only: bool = False,
    artifact_version: int | None = None,
    artifact_status: str | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    StagedDatasetArtifact | None,
]:
    thread_id = str(
        dict(state.get("meta") or {}).get(MetaKeys.THREAD_ID) or ""
    ).strip()
    if not thread_id:
        raise ValueError(
            "DB-RAG SQL subset persistence requires a thread_id in state meta."
        )
    selected_tables = _string_list(
        _read_value(approved_selection, "tables", [])
        or _read_value(candidate, "tables", [])
    )
    selected_columns = serialize_columns(
        _read_value(approved_selection, "columns", [])
        or _read_value(candidate, "columns", [])
    )
    source_question, goal_text = _sql_candidate_review_texts(
        candidate,
        approved_selection,
    )
    resolved_dataset_name = (
        str(dataset_name).strip()
        if dataset_name is not None
        else generate_dataset_name(
            goal_text=goal_text,
            source_question=source_question,
            columns=selected_columns,
        )
    )
    population_scope = (
        _read_value(approved_selection, "population_scope", None)
        or _read_value(candidate, "population_scope", None)
    )
    population_assumption = (
        _read_value(approved_selection, "population_assumption", None)
        or _read_value(candidate, "population_assumption", None)
    )
    persisted_sql = (
        exact_sql
        if exact_sql is not None
        else str(
            _read_value(
                execution_result,
                "sql",
                _read_value(candidate, "sql", ""),
            )
            or ""
        ).strip()
    )
    provenance: dict[str, Any] = {
        "source": "db_rag_sql",
        "thread_id": thread_id,
        "source_question": source_question,
        "goal_text": goal_text,
        "name": resolved_dataset_name,
        "description": resolved_dataset_name,
        "sql": persisted_sql,
        "source_tables": _string_list(
            _read_value(execution_result, "source_tables", [])
            or _read_value(candidate, "tables", [])
        ),
        "selected_tables": selected_tables,
        "selected_columns": selected_columns,
        "selection_id": str(
            _read_value(
                approved_selection,
                "selection_id",
                _read_value(candidate, "selection_id", ""),
            )
            or ""
        ).strip(),
        "selection_artifact_id": str(
            selection_artifact_id or ""
        ).strip(),
        "sql_candidate_artifact_id": str(
            sql_candidate_artifact_id or ""
        ).strip(),
        "feedback_history": list(
            _read_value(approved_selection, "feedback_history", []) or []
        ),
    }
    if plan_id and plan_version is not None:
        provenance.update(
            {"plan_id": str(plan_id), "plan_version": int(plan_version)}
        )
    if sql_candidate_artifact_id and sql_version is not None:
        provenance.update(
            {
                "sql_id": str(sql_candidate_artifact_id),
                "sql_version": int(sql_version),
            }
        )
    if predecessor_dataset_id and predecessor_dataset_version is not None:
        provenance.update(
            {
                "predecessor_dataset_id": str(predecessor_dataset_id),
                "predecessor_dataset_version": int(
                    predecessor_dataset_version
                ),
            }
        )
    if relationship_metrics:
        provenance["relationship_metrics"] = [
            dict(metric) for metric in relationship_metrics
        ]
    if join_expansion:
        provenance["join_expansion"] = {
            str(name): float(ratio)
            for name, ratio in join_expansion.items()
        }
    if grain_columns:
        provenance["grain_columns"] = [
            str(column)
            for column in grain_columns
            if str(column).strip()
        ]
    if population_scope:
        provenance["population_scope"] = _normalize_population_scope(
            population_scope
        )
    if (
        isinstance(population_assumption, dict)
        and population_assumption
    ):
        provenance["population_assumption"] = dict(
            population_assumption
        )

    persistence_arguments = {
        "runtime_root": runtime_root or DEFAULT_RUNTIME_ROOT,
        "thread_id": thread_id,
        "dataset_id": str(dataset_id or "").strip()
        or f"subset-{uuid4().hex[:8]}",
        "kind": "subset",
        "dataframe": _read_value(execution_result, "dataframe"),
        "schema": _build_subset_schema(
            _read_value(execution_result, "dataframe"),
            selected_columns,
            sql=persisted_sql,
        ),
        "provenance": provenance,
        "artifact_version": artifact_version,
        "artifact_status": artifact_status,
    }
    if stage_only:
        staged = stage_dataset_artifact(**persistence_arguments)
        return state, staged.artifact, staged
    artifact = persist_dataset_artifact(**persistence_arguments)
    return (
        register_dataset_artifact(
            state,
            artifact,
            make_active=make_active,
        ),
        artifact,
        None,
    )


__all__ = [
    "DEFAULT_RUNTIME_ROOT",
    "persist_sql_subset_artifact",
    "serialize_columns",
]
