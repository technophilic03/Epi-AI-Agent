"""Bounded observations of provider response status and token usage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import AIMessage


class ModelResponseProtocolError(RuntimeError):
    """The provider returned response metadata the runtime cannot resume."""


@dataclass(frozen=True)
class ModelResponseObservation:
    status: Literal["complete", "incomplete"]
    incomplete_reason: str | None
    response_id: str
    provider_request_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int

    def as_checkpoint_record(self) -> dict[str, object]:
        return {
            "status": self.status,
            "incomplete_reason": self.incomplete_reason,
            "response_id": self.response_id,
            "provider_request_id": self.provider_request_id,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


def observe_model_response(
    message: AIMessage,
) -> ModelResponseObservation:
    metadata = dict(message.response_metadata or {})
    status = str(metadata.get("status") or "complete").strip().casefold()
    if status == "completed":
        status = "complete"
    if status not in {"complete", "incomplete"}:
        raise ModelResponseProtocolError(
            f"Unsupported model response status: {status}"
        )
    response_id = str(metadata.get("id") or message.id or "").strip()
    if status == "incomplete" and not response_id.startswith("resp_"):
        raise ModelResponseProtocolError(
            "Incomplete response has no resumable response ID"
        )
    incomplete_details = dict(
        metadata.get("incomplete_details") or {}
    )
    headers = dict(metadata.get("headers") or {})
    usage = dict(message.usage_metadata or {})
    output_details = dict(usage.get("output_token_details") or {})
    return ModelResponseObservation(
        status=status,
        incomplete_reason=(
            str(incomplete_details.get("reason") or "").strip() or None
        ),
        response_id=response_id,
        provider_request_id=str(
            headers.get("x-request-id") or ""
        ).strip(),
        model_id=str(
            metadata.get("model") or metadata.get("model_name") or ""
        ).strip(),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        reasoning_tokens=int(output_details.get("reasoning") or 0),
    )


__all__ = [
    "ModelResponseObservation",
    "ModelResponseProtocolError",
    "observe_model_response",
]
