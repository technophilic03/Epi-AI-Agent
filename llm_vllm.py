from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from utils.model_runtime_profiles import model_runtime_profile


def build_openai_llm(*, model_name: str, api_key: str) -> ChatOpenAI:
    resolved_key = str(api_key or "").strip()
    if not resolved_key:
        raise ValueError("OPENAI_API_KEY is required.")
    profile = model_runtime_profile(model_name)
    os.environ["OPENAI_API_KEY"] = resolved_key
    kwargs: dict[str, object] = {
        "model": profile.model_id,
        "timeout": profile.request_timeout_seconds,
        "max_retries": 0,
        "max_completion_tokens": profile.initial_output_tokens,
        "use_responses_api": True,
        "use_previous_response_id": True,
        "include_response_headers": True,
    }
    if profile.reasoning_effort is not None:
        kwargs["reasoning_effort"] = profile.reasoning_effort
    if profile.model_id == "gpt-5.4":
        kwargs["temperature"] = 0
        kwargs["top_p"] = 1.0
    return ChatOpenAI(**kwargs)


__all__ = ["build_openai_llm"]
