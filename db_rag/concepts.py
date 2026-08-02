from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DbRagConcept:
    concept_id: str
    label: str
    retrieval_probe: str
