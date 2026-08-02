from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re

from pydantic import ValidationError

from db_rag.knowledge import (
    PublicationEvidenceHit,
    StudyEvidenceChunk,
    parse_study_evidence,
)
from db_rag.publication_index import (
    PublicationDesignIndex,
    PublicationIndexIngestionManifest,
)


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(value.casefold())


def _index_paths(root: Path) -> list[Path]:
    return sorted(
        {
            *root.glob("doi_*.json"),
            *root.glob("pmid_*.json"),
            *root.glob("sha256_*.json"),
        }
    )


def _validated_chunks(root: Path) -> list[StudyEvidenceChunk]:
    manifest_path = root / "ingestion-manifest.json"
    try:
        manifest = PublicationIndexIngestionManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, ValueError) as exc:
        raise ValueError("Invalid publication ingestion manifest.") from exc

    paths = _index_paths(root)
    actual_names = {path.name for path in paths}
    manifest_names = {document.index_filename for document in manifest.documents}
    if actual_names != manifest_names:
        raise ValueError(
            "Publication ingestion manifest document set does not match index files."
        )

    document_by_name = {
        document.index_filename: document for document in manifest.documents
    }
    for path in paths:
        document = document_by_name[path.name]
        try:
            publication = PublicationDesignIndex.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid publication index: {path.name}.") from exc
        if hashlib.sha256(path.read_bytes()).hexdigest() != document.index_sha256:
            raise ValueError(f"Invalid publication index hash: {path.name}.")
        if (
            publication.publication_id != document.publication_id
            or publication.review_status.status != document.review_status
        ):
            raise ValueError(f"Invalid publication index identity: {path.name}.")

    return parse_study_evidence(root)


def _hit(chunk: StudyEvidenceChunk) -> PublicationEvidenceHit:
    provenance = {
        "authority": "publication_knowledge",
        "source_id": chunk.source_id,
        "path": chunk.path,
        "section": chunk.section,
    }
    for key in (
        "knowledge_type",
        "knowledge_role",
        "source_locator",
        "indexed_path",
        "evidence_ids",
    ):
        value = str(getattr(chunk, key) or "")
        if value:
            provenance[key] = value
    return PublicationEvidenceHit(
        **chunk.model_dump(mode="python"),
        provenance=provenance,
    )


@dataclass(frozen=True)
class LocalPublicationKnowledge:
    _chunks: tuple[StudyEvidenceChunk, ...]
    _document_frequency: dict[str, int]

    @classmethod
    def from_root(cls, root: Path) -> "LocalPublicationKnowledge":
        resolved = Path(root).expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError("Publication knowledge root is unavailable.")
        chunks = tuple(_validated_chunks(resolved))
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            document_frequency.update(
                set(
                    _tokens(
                        " ".join(
                            [
                                chunk.title,
                                chunk.section,
                                chunk.knowledge_type,
                                chunk.text,
                            ]
                        )
                    )
                )
            )
        return cls(chunks, dict(document_frequency))

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[PublicationEvidenceHit]:
        if limit < 1:
            return []
        query_tokens = _tokens(query)
        if not query_tokens or not self._chunks:
            return []
        unique_query_tokens = set(query_tokens)
        total_chunks = len(self._chunks)
        scored: list[tuple[float, StudyEvidenceChunk]] = []
        for chunk in self._chunks:
            term_frequency = Counter(
                _tokens(
                    " ".join(
                        [
                            chunk.title,
                            chunk.section,
                            chunk.knowledge_type,
                            chunk.text,
                        ]
                    )
                )
            )
            score = sum(
                (
                    1.0
                    + math.log(
                        total_chunks
                        / self._document_frequency[token]
                    )
                )
                * (1.0 + math.log(term_frequency[token]))
                for token in query_tokens
                if term_frequency[token]
            )
            title_overlap = len(unique_query_tokens & set(_tokens(chunk.title)))
            section_overlap = len(
                unique_query_tokens & set(_tokens(chunk.section))
            )
            knowledge_type_overlap = len(
                unique_query_tokens & set(_tokens(chunk.knowledge_type))
            )
            score += 2.0 * title_overlap
            score += 1.5 * section_overlap
            score += 1.5 * knowledge_type_overlap
            if score > 0:
                scored.append((score, chunk))
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].source_id,
                item[1].indexed_path,
                item[1].id,
            )
        )
        return [_hit(chunk) for _score, chunk in scored[:limit]]

    def open_source(
        self,
        source_id: str,
        *,
        limit: int = 10,
    ) -> list[PublicationEvidenceHit]:
        if limit < 1:
            return []
        chunks = sorted(
            (
                chunk
                for chunk in self._chunks
                if chunk.source_id == source_id
            ),
            key=lambda chunk: (chunk.indexed_path, chunk.id),
        )
        return [_hit(chunk) for chunk in chunks[:limit]]


__all__ = ["LocalPublicationKnowledge"]
