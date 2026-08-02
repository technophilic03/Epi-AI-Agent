from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError

from api.schemas import (
    AnalysisResultReviewView,
    DatasetPlanReviewView,
    DatasetReviewView,
    ModelOutputLimitInterrupt,
)

ARTIFACT_REVIEW_RULES = {
    "dataset_plan_review": {
        "kinds": {"dataset_plan"},
        "statuses": {"draft", "pending_review"},
    },
    "dataset_review": {
        "kinds": {
            "analysis_dataset",
            "dataset",
            "db_rag_result",
            "subset",
        },
        "statuses": {"pending_review"},
    },
    "analysis_result_review": {
        "kinds": {"analysis_run"},
        "statuses": {"pending_review"},
    },
}
PRIVATE_VIEW_KEY_PARTS = {
    "data_base64",
    "password",
    "path",
    "secret",
    "stderr",
    "stdout",
    "token",
}
MAX_REVIEW_VIEW_CHARS = 750_000
MAX_REVIEW_DEPTH = 8
MAX_TYPED_REVIEW_DEPTH = 16
MAX_REVIEW_ITEMS = 500
MAX_REVIEW_STRING_CHARS = 100_000
_REVIEW_VIEW_ADAPTERS = {
    "dataset_plan_review": TypeAdapter(DatasetPlanReviewView),
    "dataset_review": TypeAdapter(DatasetReviewView),
    "analysis_result_review": TypeAdapter(AnalysisResultReviewView),
}
_MODEL_OUTPUT_LIMIT_ADAPTER = TypeAdapter(ModelOutputLimitInterrupt)


class InvalidInterruptDecisionError(ValueError):
    pass


def _validate_bounded_value(
    value: Any,
    *,
    depth: int = 0,
    path: tuple[str, ...] = (),
    max_depth: int = MAX_REVIEW_DEPTH,
) -> None:
    if depth > max_depth:
        raise ValueError("Review view exceeds the maximum nesting depth.")
    if isinstance(value, dict):
        if len(value) > MAX_REVIEW_ITEMS:
            raise ValueError("Review view contains too many mapping items.")
        for raw_key, item in value.items():
            key = str(raw_key).casefold()
            if (
                key == "rows"
                and (not path or path[-1] != "dimensions")
            ) or any(
                part in key for part in PRIVATE_VIEW_KEY_PARTS
            ):
                raise ValueError("Review view contains a private field.")
            _validate_bounded_value(
                item,
                depth=depth + 1,
                path=(*path, key),
                max_depth=max_depth,
            )
        return
    if isinstance(value, list):
        if len(value) > MAX_REVIEW_ITEMS:
            raise ValueError("Review view contains too many list items.")
        for item in value:
            _validate_bounded_value(
                item,
                depth=depth + 1,
                path=path,
                max_depth=max_depth,
            )
        return
    if isinstance(value, str) and len(value) > MAX_REVIEW_STRING_CHARS:
        raise ValueError("Review view contains an oversized string.")
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError("Review view is not JSON serializable.")


def _artifact_record(state: dict | None, artifact_id: str) -> dict:
    artifacts = dict((state or {}).get("artifacts") or {})
    file_record = dict(artifacts.get("files") or {}).get(artifact_id)
    if isinstance(file_record, dict):
        content = file_record.get("content")
        return dict(content) if isinstance(content, dict) else {}
    dataset = dict(artifacts.get("datasets") or {}).get(artifact_id)
    return dict(dataset) if isinstance(dataset, dict) else {}


def validate_bounded_review_view(
    view: Any,
    *,
    max_depth: int = MAX_REVIEW_DEPTH,
) -> dict[str, Any]:
    if not isinstance(view, dict):
        raise ValueError("Review view must be an object.")
    _validate_bounded_value(view, max_depth=max_depth)
    serialized = json.dumps(
        view,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    if len(serialized) > MAX_REVIEW_VIEW_CHARS:
        raise ValueError("Review view exceeds the serialized size limit.")
    return view


def _typed_bounded_view(interrupt_type: str, view: Any) -> bool:
    adapter = _REVIEW_VIEW_ADAPTERS.get(interrupt_type)
    if adapter is None:
        return False
    try:
        adapter.validate_python(view)
        validate_bounded_review_view(view, max_depth=MAX_TYPED_REVIEW_DEPTH)
    except (TypeError, ValueError, ValidationError):
        return False
    return True


def project_review_interrupt(
    interrupt_event: object,
    state: dict | None,
) -> dict | None:
    interrupt_id = str(getattr(interrupt_event, "id", "") or "").strip()
    value = getattr(interrupt_event, "value", None)
    if not interrupt_id or not isinstance(value, dict):
        return None
    interrupt_type = str(value.get("type") or "")

    if interrupt_type in ARTIFACT_REVIEW_RULES:
        if set(value) != {"type", "artifact", "view"}:
            return None
        identity = value.get("artifact")
        view = value.get("view")
        if not isinstance(identity, dict) or not _typed_bounded_view(
            interrupt_type,
            view,
        ):
            return None
        if set(identity) != {
            "id",
            "kind",
            "version",
            "expected_status",
        }:
            return None
        artifact_id = str(identity.get("id") or "").strip()
        kind = str(identity.get("kind") or "").strip()
        version = identity.get("version")
        status = str(identity.get("expected_status") or "").strip()
        rule = ARTIFACT_REVIEW_RULES[interrupt_type]
        if (
            not artifact_id
            or kind not in rule["kinds"]
            or not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
            or status not in rule["statuses"]
        ):
            return None
        stored = _artifact_record(state, artifact_id)
        if (
            stored.get("id") != artifact_id
            or stored.get("kind") != kind
            or stored.get("version") != version
            or stored.get("status") != status
        ):
            return None
        return {"id": interrupt_id, **value}

    if interrupt_type == "agent_clarification":
        raw_question = value.get("question")
        raw_reason = value.get("reason", "")
        if not isinstance(raw_question, str) or not isinstance(raw_reason, str):
            return None
        question = raw_question.strip()
        reason = raw_reason.strip()
        if not question or len(question) > 2_000 or len(reason) > 2_000:
            return None
        raw_options = value.get("options")
        if not isinstance(raw_options, list) or not 2 <= len(raw_options) <= 8:
            return None
        options: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        seen_labels: set[str] = set()
        for raw_option in raw_options:
            if not isinstance(raw_option, dict) or set(raw_option) != {"id", "label"}:
                return None
            raw_option_id = raw_option.get("id")
            raw_label = raw_option.get("label")
            if not isinstance(raw_option_id, str) or not isinstance(raw_label, str):
                return None
            option_id = raw_option_id.strip()
            label = raw_label.strip()
            if (
                not option_id
                or not label
                or len(option_id) > 64
                or len(label) > 500
                or option_id.casefold() in seen_ids
                or label.casefold() in seen_labels
            ):
                return None
            seen_ids.add(option_id.casefold())
            seen_labels.add(label.casefold())
            options.append({"id": option_id, "label": label})
        return {
            "id": interrupt_id,
            "type": interrupt_type,
            "question": question,
            "reason": reason,
            "options": options,
        }

    if interrupt_type == "model_output_limit":
        try:
            projected = _MODEL_OUTPUT_LIMIT_ADAPTER.validate_python(
                {"id": interrupt_id, **value}
            )
        except ValidationError:
            return None
        if projected.actions != ("continue", "cancel"):
            return None
        return projected.model_dump(mode="json")

    return None


def validate_resume_decision(
    interrupt: dict,
    decision: dict,
) -> dict:
    if not isinstance(decision, dict):
        raise InvalidInterruptDecisionError("Review decision must be an object.")
    interrupt_type = str(interrupt.get("type") or "")
    action = str(decision.get("action") or "").strip().casefold()
    if interrupt_type == "agent_clarification":
        if set(decision) == {"action"} and action == "cancel":
            return {"action": "cancel"}
        if set(decision) != {"action", "answer"} or action != "answer":
            raise InvalidInterruptDecisionError(
                "Clarification accepts action=cancel or action=answer with answer."
            )
        answer = str(decision.get("answer") or "").strip()
        if not answer:
            raise InvalidInterruptDecisionError(
                "Clarification answer cannot be empty."
            )
        return {"action": "answer", "answer": answer}

    if interrupt_type == "model_output_limit":
        if set(decision) != {"action"} or action not in {
            "continue",
            "cancel",
        }:
            raise InvalidInterruptDecisionError(
                "Model output recovery accepts only action=continue or "
                "action=cancel."
            )
        return {"action": action}

    review_types = {
        "dataset_plan_review",
        "dataset_review",
        "analysis_result_review",
    }
    if interrupt_type not in review_types:
        raise InvalidInterruptDecisionError("Interrupt type is not resumable.")
    if action not in {"approve", "revise", "cancel"}:
        raise InvalidInterruptDecisionError(
            "Review action must be approve, revise, or cancel."
        )

    allowed = {"action"}
    normalized: dict[str, object] = {"action": action}
    if action == "revise":
        allowed.add("feedback")
        feedback = str(decision.get("feedback") or "").strip()
        if not feedback:
            raise InvalidInterruptDecisionError(
                "Revision feedback cannot be empty."
            )
        normalized["feedback"] = feedback
    if (
        interrupt_type == "dataset_plan_review"
        and action in {"approve", "revise"}
        and "selected_column_keys" in decision
    ):
        allowed.add("selected_column_keys")
        raw_keys = decision.get("selected_column_keys")
        if not isinstance(raw_keys, list) or any(
            not isinstance(value, str) or not value.strip()
            for value in raw_keys
        ):
            raise InvalidInterruptDecisionError(
                "selected_column_keys must contain nonempty strings."
            )
        selected = [value.strip() for value in raw_keys]
        if len(selected) != len(set(selected)):
            raise InvalidInterruptDecisionError(
                "selected_column_keys must be unique."
            )
        normalized["selected_column_keys"] = selected
    unexpected = set(decision) - allowed
    if unexpected:
        raise InvalidInterruptDecisionError(
            "Decision contains fields not accepted by this review type."
        )
    return normalized
