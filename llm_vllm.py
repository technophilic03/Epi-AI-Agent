from __future__ import annotations

import os

from utils.model_runtime_profiles import (
    ModelRuntimeProfile,
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    PROVIDER_OPENAI_COMPATIBLE,
    model_runtime_profile,
)


_COMPAT_PLACEHOLDER_KEY = "not-needed"


def resolve_provider_api_key(
    profile: ModelRuntimeProfile,
    *,
    api_key: str | None = None,
) -> str:
    resolved = str(api_key or "").strip()
    if not resolved and profile.api_key_env:
        resolved = str(os.getenv(profile.api_key_env, "") or "").strip()
    if not resolved:
        if profile.api_key_required:
            env_name = profile.api_key_env or "the provider API key"
            raise ValueError(f"{env_name} is required.")
        resolved = _COMPAT_PLACEHOLDER_KEY
    return resolved


def _build_openai_chat_llm(profile: ModelRuntimeProfile, api_key: str):
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, object] = {
        "model": profile.served_model_id,
        "api_key": api_key,
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


def _build_anthropic_chat_llm(profile: ModelRuntimeProfile, api_key: str):
    from langchain_anthropic import ChatAnthropic

    # Claude 5-family models run adaptive thinking by default and reject
    # sampling parameters, budget_tokens, and OpenAI-only kwargs — send none.
    return ChatAnthropic(
        model=profile.served_model_id,
        api_key=api_key,
        timeout=profile.request_timeout_seconds,
        max_retries=0,
        max_tokens=profile.initial_output_tokens,
    )


def _build_openai_compatible_chat_llm(profile: ModelRuntimeProfile, api_key: str):
    from langchain_openai import ChatOpenAI

    # Plain chat-completions mode: OpenAI-compatible servers (e.g. vLLM)
    # generally do not implement the Responses API, response chaining,
    # or reasoning_effort.
    return ChatOpenAI(
        model=profile.served_model_id,
        api_key=api_key,
        base_url=profile.base_url,
        timeout=profile.request_timeout_seconds,
        max_retries=0,
        max_tokens=profile.initial_output_tokens,
    )


def build_chat_llm(*, model_name: str, api_key: str | None = None):
    """Build the provider-correct LangChain chat model for a profiled model."""
    profile = model_runtime_profile(model_name)
    resolved_key = resolve_provider_api_key(profile, api_key=api_key)
    if profile.provider == PROVIDER_ANTHROPIC:
        return _build_anthropic_chat_llm(profile, resolved_key)
    if profile.provider == PROVIDER_OPENAI_COMPATIBLE:
        return _build_openai_compatible_chat_llm(profile, resolved_key)
    if profile.provider == PROVIDER_OPENAI:
        return _build_openai_chat_llm(profile, resolved_key)
    raise ValueError(f"Unsupported model provider: {profile.provider}")


def build_openai_llm(*, model_name: str, api_key: str):
    """Deprecated alias kept for existing call sites; dispatches by provider."""
    return build_chat_llm(model_name=model_name, api_key=api_key)


__all__ = ["build_chat_llm", "build_openai_llm", "resolve_provider_api_key"]
