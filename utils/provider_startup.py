from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI


class ProviderCredentialError(RuntimeError):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def verify_openai_credentials(
    api_key: str,
    *,
    client_factory: Callable[..., Any] = OpenAI,
) -> None:
    normalized_key = str(api_key or "").strip()
    if not normalized_key:
        raise ProviderCredentialError(
            "missing",
            "An OpenAI API key is required.",
        )
    try:
        client_factory(
            api_key=normalized_key,
            max_retries=0,
            timeout=10.0,
        ).models.list()
    except (APIConnectionError, APITimeoutError) as error:
        raise ProviderCredentialError(
            "network",
            "OpenAI could not be reached. Check your network and try again.",
        ) from error
    except APIStatusError as error:
        status_code = int(error.status_code)
        messages = {
            401: (
                "authentication",
                "OpenAI rejected the API key. Paste a valid key and try again.",
            ),
            403: (
                "authorization",
                "The OpenAI API key is not authorized for this project.",
            ),
            429: (
                "temporary",
                "OpenAI temporarily rejected the credential check. Try again shortly.",
            ),
        }
        kind, message = messages.get(
            status_code,
            (
                "provider",
                f"OpenAI credential check failed with HTTP status {status_code}.",
            ),
        )
        raise ProviderCredentialError(kind, message) from error


def verify_active_provider(
    provider: str,
    api_key: str,
    *,
    openai_checker: Callable[[str], None] = verify_openai_credentials,
) -> None:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "openai":
        openai_checker(api_key)
        return
    if not normalized_provider:
        raise ProviderCredentialError(
            "provider",
            "An active AI provider must be configured.",
        )
    raise ProviderCredentialError(
        "provider",
        "Startup verification is not configured for the active provider.",
    )


__all__ = [
    "ProviderCredentialError",
    "verify_active_provider",
    "verify_openai_credentials",
]
