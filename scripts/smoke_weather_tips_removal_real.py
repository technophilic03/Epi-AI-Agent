#!/usr/bin/env python3
"""Verify weather-tips removal at the production registry boundary."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from epi_agent.agent import build_general_epi_agent_registry
from epi_agent.runtimes.python import LocalPythonRuntime
from utils.attachment_artifacts import LocalAttachmentStore
from utils.attachment_readers import AttachmentReaderService


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="epi-weather-tips-removal-"
    ) as temporary:
        runtime_root = Path(temporary)
        service = AttachmentReaderService(
            LocalAttachmentStore(runtime_root),
            runtime_root=runtime_root,
        )
        registry = build_general_epi_agent_registry(
            service=service,
            python_runtime=LocalPythonRuntime(runtime_root=runtime_root),
            runtime_root=runtime_root,
            include_db_rag=False,
        )
        names = {
            schema["function"]["name"] for schema in registry.model_schemas()
        }

    if "general-query_weather" not in names:
        raise RuntimeError("general-query_weather is missing")
    if "general-get_weather_tips" in names:
        raise RuntimeError("general-get_weather_tips is still registered")

    print("PASS: live weather remains and seasonal weather tips are removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
