"""Bounded client for PubMed's public NCBI E-utilities API."""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Callable
from xml.etree import ElementTree

import httpx


_EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_REQUEST_TIMEOUT_SECONDS = 20.0
_MAX_TITLE_CHARS = 1_000
_MAX_ABSTRACT_CHARS = 6_000
_MAX_AUTHORS = 20


class PubMedConfigurationError(RuntimeError):
    """The local deployment has not identified itself to NCBI."""


class PubMedRequestError(RuntimeError):
    """NCBI could not complete a PubMed request."""


@dataclass(frozen=True)
class PubMedSettings:
    email: str
    api_key: str | None
    tool: str

    @classmethod
    def from_environment(cls) -> "PubMedSettings":
        return cls(
            email=os.getenv("NCBI_EMAIL", "").strip(),
            api_key=os.getenv("NCBI_API_KEY", "").strip() or None,
            tool=os.getenv("NCBI_TOOL", "report-agent").strip() or "report-agent",
        )


def is_pubmed_configured() -> bool:
    """Return whether this deployment can identify itself to NCBI."""

    return bool(PubMedSettings.from_environment().email)


def _text(element: ElementTree.Element | None, *, limit: int) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())[:limit]


def _article_date(article: ElementTree.Element) -> str:
    for path in (
        "./MedlineCitation/Article/ArticleDate",
        "./MedlineCitation/Article/Journal/JournalIssue/PubDate",
    ):
        date = article.find(path)
        if date is None:
            continue
        parts = [_text(date.find(part), limit=16) for part in ("Year", "Month", "Day")]
        populated = [part for part in parts if part]
        if populated:
            return "-".join(populated)
        value = _text(date.find("MedlineDate"), limit=64)
        if value:
            return value
    return ""


def _authors(article: ElementTree.Element) -> list[str]:
    authors: list[str] = []
    for author in article.findall("./MedlineCitation/Article/AuthorList/Author")[:_MAX_AUTHORS]:
        collective = _text(author.find("CollectiveName"), limit=200)
        if collective:
            authors.append(collective)
            continue
        last_name = _text(author.find("LastName"), limit=100)
        fore_name = _text(author.find("ForeName"), limit=100)
        name = " ".join(part for part in (fore_name, last_name) if part)
        if name:
            authors.append(name)
    return authors


def _article_from_xml(article: ElementTree.Element) -> dict[str, Any]:
    pmid = _text(article.find("./MedlineCitation/PMID"), limit=32)
    title = _text(article.find("./MedlineCitation/Article/ArticleTitle"), limit=_MAX_TITLE_CHARS)
    journal = _text(article.find("./MedlineCitation/Article/Journal/Title"), limit=500)
    abstract_parts: list[str] = []
    for paragraph in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
        text = _text(paragraph, limit=_MAX_ABSTRACT_CHARS)
        if not text:
            continue
        label = str(paragraph.attrib.get("Label") or "").strip()
        abstract_parts.append(f"{label}: {text}" if label else text)
    doi = ""
    for identifier in article.findall("./PubmedData/ArticleIdList/ArticleId"):
        if str(identifier.attrib.get("IdType") or "").lower() == "doi":
            doi = _text(identifier, limit=500)
            break
    return {
        "pmid": pmid,
        "source_id": f"pubmed:{pmid}",
        "title": title,
        "journal": journal,
        "publication_date": _article_date(article),
        "authors": _authors(article),
        "doi": doi,
        "abstract": "\n\n".join(abstract_parts)[:_MAX_ABSTRACT_CHARS],
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


class PubMedClient:
    """Synchronous E-utilities client with NCBI-compliant per-client pacing."""

    def __init__(
        self,
        *,
        settings_factory: Callable[[], PubMedSettings] = PubMedSettings.from_environment,
        request: Callable[..., httpx.Response] = httpx.get,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings_factory = settings_factory
        self._request = request
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_request_at: float | None = None

    def _get(self, endpoint: str, params: dict[str, str | int]) -> httpx.Response:
        settings = self._settings_factory()
        if not settings.email:
            raise PubMedConfigurationError(
                "NCBI_EMAIL is required before using PubMed search."
            )
        interval = 0.1 if settings.api_key else (1.0 / 3.0)
        if self._last_request_at is not None:
            remaining = interval - (self._monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        payload: dict[str, str | int] = {
            "tool": settings.tool,
            "email": settings.email,
            **params,
        }
        if settings.api_key:
            payload["api_key"] = settings.api_key
        try:
            response = self._request(
                f"{_EUTILS_BASE_URL}/{endpoint}",
                params=payload,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise PubMedRequestError(f"PubMed request failed: {error}") from error
        self._last_request_at = self._monotonic()
        return response

    def search(
        self,
        *,
        query: str,
        limit: int,
        published_after: str | None = None,
        published_before: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
        }
        if published_after or published_before:
            params["datetype"] = "pdat"
        if published_after:
            params["mindate"] = published_after.replace("-", "/")
        if published_before:
            params["maxdate"] = published_before.replace("-", "/")
        search = self._get("esearch.fcgi", params).json().get("esearchresult") or {}
        ids = [str(value) for value in list(search.get("idlist") or [])][:limit]
        if not ids:
            return []
        summary = self._get(
            "esummary.fcgi",
            {"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        ).json().get("result") or {}
        records: list[dict[str, Any]] = []
        for pmid in ids:
            record = dict(summary.get(pmid) or {})
            if not record:
                continue
            authors = [
                str(author.get("name") or "")[:200]
                for author in list(record.get("authors") or [])[:_MAX_AUTHORS]
                if isinstance(author, dict) and str(author.get("name") or "").strip()
            ]
            doi = ""
            for identifier in list(record.get("articleids") or []):
                if isinstance(identifier, dict) and identifier.get("idtype") == "doi":
                    doi = str(identifier.get("value") or "")[:500]
                    break
            records.append(
                {
                    "pmid": pmid,
                    "source_id": f"pubmed:{pmid}",
                    "title": str(record.get("title") or "")[:_MAX_TITLE_CHARS],
                    "journal": str(record.get("fulljournalname") or record.get("source") or "")[:500],
                    "publication_date": str(record.get("pubdate") or "")[:64],
                    "authors": authors,
                    "doi": doi,
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
            )
        return records

    def open_article(self, pmid: str) -> dict[str, Any]:
        response = self._get(
            "efetch.fcgi",
            {"db": "pubmed", "id": pmid, "retmode": "xml"},
        )
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as error:
            raise PubMedRequestError("PubMed returned invalid article XML.") from error
        article = root.find("./PubmedArticle")
        if article is None:
            raise PubMedRequestError(f"PubMed did not return article {pmid}.")
        result = _article_from_xml(article)
        if result["pmid"] != pmid:
            raise PubMedRequestError(f"PubMed returned an unexpected article for {pmid}.")
        return result
