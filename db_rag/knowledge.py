from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

class StudyEvidenceChunk(BaseModel):
    id: str
    source_id: str
    title: str
    section: str
    text: str
    path: str
    source_kind: Literal["publication"] = "publication"
    knowledge_type: str = ""
    knowledge_role: str = ""
    source_locator: str = ""
    indexed_path: str = ""
    evidence_ids: str = ""

    def embedding_text(self) -> str:
        values = [
            f"Title: {self.title}",
            f"Section: {self.section}",
        ]
        if self.knowledge_type:
            values.append(f"Knowledge type: {self.knowledge_type}")
        return "\n".join([*values, "", self.text])

    def chroma_metadata(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "section": self.section,
            "path": self.path,
            "source_kind": self.source_kind,
            "body_text": self.text,
            "knowledge_type": self.knowledge_type,
            "knowledge_role": self.knowledge_role,
            "source_locator": self.source_locator,
            "indexed_path": self.indexed_path,
            "evidence_ids": self.evidence_ids,
        }


class PublicationEvidenceHit(StudyEvidenceChunk):
    provenance: dict[str, str]


def _chunk_id(source_id: str, indexed_path: str, text: str) -> str:
    digest = sha256(
        f"{source_id}:{indexed_path}:{text}".encode("utf-8")
    ).hexdigest()
    return f"publication.{digest[:24]}"


def _publication_index_paths(root: Path) -> list[Path]:
    return sorted(
        {
            *root.rglob("doi_*.json"),
            *root.rglob("pmid_*.json"),
            *root.rglob("sha256_*.json"),
        }
    )


def _publication_index_chunks(path: Path) -> list[StudyEvidenceChunk]:
    from .publication_index import PublicationDesignIndex

    publication = PublicationDesignIndex.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if publication.review_status.status != "manually_verified":
        return []
    evidence = list(publication.evidence_items)
    chunks: list[StudyEvidenceChunk] = []

    def add(
        *,
        knowledge_type: str,
        indexed_path: str,
        section: str,
        text: str,
    ) -> None:
        normalized = " ".join(str(text or "").split())
        if not normalized:
            return
        supporting = [
            item
            for item in evidence
            if any(
                supported_path == indexed_path
                or supported_path.startswith(f"{indexed_path}.")
                or supported_path.startswith(f"{indexed_path}[")
                or indexed_path.startswith(f"{supported_path}.")
                or indexed_path.startswith(f"{supported_path}[")
                for supported_path in item.supports_paths
            )
        ]
        locators = sorted(
            {item.source_locator.label() for item in supporting}
        )
        evidence_ids = [item.evidence_id for item in supporting]
        chunks.append(
            StudyEvidenceChunk(
                id=_chunk_id(
                    publication.publication_id,
                    indexed_path,
                    normalized,
                ),
                source_id=publication.publication_id,
                title=publication.citation.title,
                section=section,
                text=normalized,
                path=path.name,
                knowledge_type=knowledge_type,
                knowledge_role="historical_study_design_reference",
                source_locator="; ".join(locators),
                indexed_path=indexed_path,
                evidence_ids=json.dumps(
                    evidence_ids,
                    separators=(",", ":"),
                ),
            )
        )

    add(
        knowledge_type="retrieval_summary",
        indexed_path="retrieval_summary",
        section="Retrieval summary",
        text=publication.retrieval_summary,
    )
    context = publication.study_context
    add(
        knowledge_type="study_context",
        indexed_path="study_context",
        section="Parent study and analytic subset",
        text=(
            f"Parent study: {context.parent_study_name or 'not reported'}. "
            f"Cohort or site: {context.cohort_or_site or 'not reported'}. "
            f"Relationship: "
            f"{context.relationship_to_parent_study or 'not reported'}. "
            f"Publication analytic subset: "
            f"{context.publication_analytic_subset or 'not reported'}."
        ),
    )
    design = publication.design_reference
    add(
        knowledge_type="analytic_population",
        indexed_path="design_reference.analytic_population",
        section="Analytic population",
        text=(
            f"Analytic population: "
            f"{design.analytic_population or 'not reported'}. "
            f"Comparison population: "
            f"{design.comparison_population or 'not reported'}. "
            f"Unit of analysis: {design.unit_of_analysis or 'not reported'}."
        ),
    )
    add(
        knowledge_type="study_design",
        indexed_path="design_reference",
        section="Study design",
        text=(
            f"Design types: {', '.join(design.design_types)}. "
            f"Time orientation: "
            f"{design.time_structure.orientation or 'not reported'}. "
            f"Enrollment period: "
            f"{design.enrollment_period.description or 'not reported'}."
        ),
    )
    add(
        knowledge_type="eligibility",
        indexed_path="design_reference.eligibility",
        section="Eligibility",
        text=(
            f"Inclusion: {'; '.join(design.eligibility.inclusion)}. "
            f"Exclusion: {'; '.join(design.eligibility.exclusion)}."
        ),
    )
    for index, domain in enumerate(publication.data_reference.data_domains):
        add(
            knowledge_type="data_domain",
            indexed_path=f"data_reference.data_domains[{index}]",
            section=f"Data domain: {domain.domain}",
            text=(
                f"Domain: {domain.domain}. Concepts: "
                f"{'; '.join(domain.variables_or_concepts)}. "
                f"Collection timepoints: "
                f"{'; '.join(domain.collection_timepoints) or 'not reported'}. "
                f"Source: {domain.source or 'not reported'}. "
                f"Availability claim: {domain.availability_claim}."
            ),
        )
    for index, definition in enumerate(
        publication.data_reference.operational_definitions
    ):
        add(
            knowledge_type="operational_definition",
            indexed_path=(
                f"data_reference.operational_definitions[{index}]"
            ),
            section=f"Operational definition: {definition.concept}",
            text=(
                f"{definition.concept}: {definition.definition} "
                f"Definition role: {definition.definition_role}. "
                f"Timepoint: {definition.timepoint or 'not reported'}. "
                f"Warning: {definition.definition_warning}"
            ),
        )
    for index, pattern in enumerate(
        publication.analysis_reference.analysis_patterns
    ):
        add(
            knowledge_type="analysis_pattern",
            indexed_path=f"analysis_reference.analysis_patterns[{index}]",
            section=f"Analysis pattern: {pattern.analysis_pattern}",
            text=(
                f"{pattern.description} Inputs: {'; '.join(pattern.inputs)}. "
                f"Outputs: {'; '.join(pattern.outputs)}. "
                f"Database relevance: {pattern.database_relevance}. "
                f"Reproducibility: {pattern.reproducibility_claim}."
            ),
        )
    for index, question in enumerate(
        publication.database_question_templates
    ):
        add(
            knowledge_type="database_question_template",
            indexed_path=f"database_question_templates[{index}]",
            section=f"Database question: {question.question_family}",
            text=(
                f"Question: {question.question} Scientific basis: "
                f"{question.scientific_basis} Required elements: "
                f"{'; '.join(question.required_elements)}. Required linkages: "
                f"{'; '.join(question.required_linkages) or 'none'}. "
                f"Database support: {question.database_support}. Cautions: "
                f"{'; '.join(question.important_cautions)}."
            ),
        )
    for index, constraint in enumerate(
        publication.applicability_constraints
    ):
        add(
            knowledge_type="applicability_constraint",
            indexed_path=f"applicability_constraints[{index}]",
            section=f"Applicability constraint: {constraint.type}",
            text=(
                f"{constraint.constraint} Severity: {constraint.severity}."
            ),
        )
    return chunks


def parse_study_evidence(root: Path) -> list[StudyEvidenceChunk]:
    if not root.exists():
        return []
    return [
        chunk
        for path in _publication_index_paths(root)
        for chunk in _publication_index_chunks(path)
    ]
