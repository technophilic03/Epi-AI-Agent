from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from .installer import InstalledStudy


_SAFE_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class StudyRegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1] = 1
    active: dict[str, str] = Field(default_factory=dict)

    @field_validator("active")
    @classmethod
    def validate_active(cls, value: dict[str, str]) -> dict[str, str]:
        for study_id, package_version in value.items():
            if not _SAFE_SEGMENT.fullmatch(study_id):
                raise ValueError("registry study_id must be a safe identifier segment")
            if not _SAFE_SEGMENT.fullmatch(package_version):
                raise ValueError("registry package_version must be a safe identifier segment")
        return value


def registry_path(studies_root: Path) -> Path:
    return Path(studies_root) / "registry.json"


def package_root(studies_root: Path, study_id: str, package_version: str) -> Path:
    if not _SAFE_SEGMENT.fullmatch(study_id) or not _SAFE_SEGMENT.fullmatch(package_version):
        raise ValueError("Study ID and package version must be safe identifier segments")
    return Path(studies_root) / "packages" / study_id / package_version


def load_registry(studies_root: Path) -> StudyRegistryFile:
    path = registry_path(studies_root)
    if not path.exists():
        return StudyRegistryFile()
    try:
        return StudyRegistryFile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid study registry: {path}") from error


def write_registry(studies_root: Path, registry: StudyRegistryFile) -> Path:
    path = registry_path(studies_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".registry-",
        suffix=".json",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    registry.model_dump(mode="json"),
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return path


def load_active_installations(studies_root: Path) -> tuple[InstalledStudy, ...]:
    from .installer import load_installed_study

    registry = load_registry(studies_root)
    active_installations: list[InstalledStudy] = []
    for study_id, package_version in sorted(registry.active.items()):
        installed = load_installed_study(
            package_root(studies_root, study_id, package_version)
        )
        if (installed.study_id, installed.package_version) != (
            study_id,
            package_version,
        ):
            raise ValueError(
                "Installed study record does not match registry: "
                f"{study_id}@{package_version}"
            )
        active_installations.append(installed)
    return tuple(active_installations)


def discover_studies(studies_root: Path):
    from db_rag.study import build_study_bundle
    from epi_agent.studies import StudyRegistry

    return StudyRegistry(
        build_study_bundle(installed)
        for installed in load_active_installations(studies_root)
    )
