from __future__ import annotations

from typing import Any


def _nested_stored_artifact(record: dict[str, Any]) -> dict[str, Any]:
    content = record.get("content")
    return dict(content) if isinstance(content, dict) else {}


def _is_executor_output(record: dict[str, Any]) -> bool:
    return (
        record.get("producer") == "executor"
        and record.get("kind") in {"text", "figure"}
    )


def _is_epi_analysis_output(record: dict[str, Any]) -> bool:
    nested = _nested_stored_artifact(record)
    return (
        record.get("producer") == "epi_agent"
        and record.get("kind") in {"analysis_run", "figure", "table"}
        and nested.get("kind") == record.get("kind")
    )


def is_published_artifact(
    artifact: dict[str, Any] | None,
) -> bool:
    record = dict(artifact or {})
    if _is_executor_output(record):
        return record.get("status") == "approved"
    if _is_epi_analysis_output(record):
        nested_status = _nested_stored_artifact(record).get("status")
        return record.get("status") == nested_status == "active"
    return True
