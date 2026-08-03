"""Central runtime defaults for the native OpenAI application."""

from collections.abc import Mapping

from utils.model_runtime_profiles import (
    MODEL_RUNTIME_PROFILES,
    configured_model_profiles,
    model_runtime_profile,
)


AVAILABLE_OPENAI_MODELS = tuple(MODEL_RUNTIME_PROFILES)

DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"

DEFAULT_TEMPERATURE = 0.0
TEMPERATURE_RANGE = (0.0, 1.0)
TEMPERATURE_STEP = 0.05

DEFAULT_TOP_P = 1.0
TOP_P_RANGE = (0.5, 1.0)
TOP_P_STEP = 0.05

DEFAULT_EPI_AGENT_MAX_ITERATIONS = 50
DEFAULT_MAX_AUTO_STEPS = 4
MAX_AUTO_STEPS_RANGE = (1, 8)

DEFAULT_EXECUTION_TIMEOUT_SEC = 60
EXECUTION_TIMEOUT_RANGE = (5, 120)
EXECUTION_TIMEOUT_STEP = 5


def configured_epi_agent_max_iterations(
    environ: Mapping[str, str],
) -> int:
    name = "REPORT_AGENT_MAX_ITERATIONS"
    if name not in environ:
        return DEFAULT_EPI_AGENT_MAX_ITERATIONS
    configured = str(environ[name]).strip()
    try:
        value = int(configured)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a positive integer"
        ) from exc
    if value < 1 or str(value) != configured:
        raise ValueError(f"{name} must be a positive integer")
    return value


def configured_openai_models(environ: Mapping[str, str]) -> tuple[str, ...]:
    models = tuple(
        profile.model_id for profile in configured_model_profiles(environ)
    )
    default_model = str(environ.get("OPENAI_MODEL", "")).strip()
    if default_model not in models:
        raise ValueError("OPENAI_MODEL must be included in REPORT_AGENT_ALLOWED_MODELS")
    return models


def configured_title_model(environ: Mapping[str, str]) -> str:
    title_model = str(environ.get("REPORT_AGENT_TITLE_MODEL", "")).strip()
    return model_runtime_profile(title_model).model_id
