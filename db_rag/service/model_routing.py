from __future__ import annotations

from typing import Any

from llm_vllm import build_chat_llm


def build_db_rag_openai_llm(model: str | None) -> Any | None:
    resolved = str(model or "").strip()
    if not resolved:
        return None
    # The factory resolves the provider and its API key from the profile.
    return build_chat_llm(model_name=resolved)
