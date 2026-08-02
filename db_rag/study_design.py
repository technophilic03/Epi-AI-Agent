from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


_CANONICAL_FILENAME = "report.study-design.json"


class StudyPopulation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_label: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(min_length=1)
    definition: str = Field(min_length=1)


class StudyRelationship(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    type: str = Field(min_length=1)
    from_population: str = Field(alias="from", min_length=1)
    to_population: str = Field(alias="to", min_length=1)
    description: str = Field(min_length=1)

class StudyPopulations(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index_case: StudyPopulation
    household_contact: StudyPopulation


class StudyDesignDocument(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    schema_ref: str = Field(alias="$schema", min_length=1)
    schema_version: str = Field(min_length=1)
    study_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    study_purpose: str = Field(min_length=1)
    populations: StudyPopulations
    relationships: tuple[StudyRelationship, ...] = Field(min_length=1)
    authoritative_for: tuple[str, ...] = Field(min_length=1)
    enrollment_criteria: tuple[str, ...] = ()
    follow_up_timepoints: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    specimen_domains: tuple[str, ...] = ()
    linkage_rules: tuple[str, ...] = ()
    terminology: dict[str, str] = Field(default_factory=dict)
    analysis_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_relationship_populations(self) -> "StudyDesignDocument":
        known_populations = {"index_case", "household_contact"}
        if any(
            relationship.from_population not in known_populations
            or relationship.to_population not in known_populations
            for relationship in self.relationships
        ):
            raise ValueError("relationships must reference defined populations")
        return self


class LocalStudyDesign:
    def __init__(self, document: StudyDesignDocument, *, source_path: Path) -> None:
        self._document = document
        self.source_path = source_path

    @classmethod
    def from_root(cls, root: Path) -> "LocalStudyDesign":
        resolved = Path(root).expanduser().resolve()
        return cls.from_path(resolved / _CANONICAL_FILENAME)

    @classmethod
    def from_path(cls, path: Path) -> "LocalStudyDesign":
        resolved = Path(path).expanduser().resolve()
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
            document = StudyDesignDocument.model_validate(payload)
        except (OSError, json.JSONDecodeError, TypeError, ValidationError, ValueError) as error:
            raise ValueError(
                f"Study design path must contain a valid document: {resolved}"
            ) from error
        return cls(document, source_path=resolved)

    @property
    def study_id(self) -> str:
        return self._document.study_id

    @property
    def label(self) -> str:
        return self._document.label

    @property
    def document(self) -> StudyDesignDocument:
        return self._document

    def render_context(self) -> str:
        populations = self._document.populations
        relationships = " ".join(
            relationship.description
            for relationship in self._document.relationships
        )
        authoritative_for = ", ".join(self._document.authoritative_for)
        return (
            "Authoritative study design for the active study "
            f"{self._document.label} ({self._document.study_id}): "
            f"{self._document.study_purpose} "
            f"Cohort A / {populations.index_case.canonical_label} "
            f"({', '.join(populations.index_case.aliases)}): "
            f"{populations.index_case.definition} "
            f"Cohort B / {populations.household_contact.canonical_label} "
            f"({', '.join(populations.household_contact.aliases)}): "
            f"{populations.household_contact.definition} "
            f"Relationship: {relationships} "
            f"Use this design as authoritative for: {authoritative_for}."
        )


__all__ = [
    "LocalStudyDesign",
    "StudyDesignDocument",
    "StudyPopulation",
    "StudyPopulations",
    "StudyRelationship",
]
