from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage


def _has_tool_call_metadata(message: BaseMessage) -> bool:
    direct_tool_calls = getattr(message, "tool_calls", None)
    if isinstance(direct_tool_calls, list) and bool(direct_tool_calls):
        return True

    invalid_tool_calls = getattr(message, "invalid_tool_calls", None)
    if isinstance(invalid_tool_calls, list) and bool(invalid_tool_calls):
        return True

    additional_kwargs = dict(getattr(message, "additional_kwargs", {}) or {})
    tool_calls = additional_kwargs.get("tool_calls")
    return isinstance(tool_calls, list) and bool(tool_calls)


def compact_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Drop blank assistant turns that should not influence later prompts/UI."""
    compacted: list[BaseMessage] = []
    for msg in messages or []:
        if (
            isinstance(msg, AIMessage)
            and not str(getattr(msg, "content", "") or "").strip()
            and not _has_tool_call_metadata(msg)
        ):
            continue
        compacted.append(msg)
    return compacted
