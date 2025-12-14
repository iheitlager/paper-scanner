"""
Crossref API handler - metadata and citations fetcher.

Fetches publication metadata and backward citations from Crossref API.
API docs: https://github.com/CrossRef/rest-api-doc
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

import requests

from paper_scanner.core.models import OpenAccessStatus, Citation
from paper_scanner.core.enum import PaperType
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.documents.abstract_parser import AbstractParser
from paper_scanner.tools.doi import DOI

logger = logging.getLogger(__name__)

# Polite pool per Crossref requirements
CROSSREF_API_URL = "https://api.crossref.org"
CROSSREF_POLITE_EMAIL = "i.heitlager@tue.nl"
CROSSREF_USER_AGENT = "paper-scanner/1.0 (mailto:{})".format(CROSSREF_POLITE_EMAIL)

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 10


class CrossrefHandler(BaseFetcherHandler):
    """Fetcher for Crossref API metadata and citations."""

    def __init__(self, cache_dir: Path):
        """Initialize Crossref handler."""
        super().__init__(cache_dir)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": CROSSREF_USER_AGENT})

    @property
    def name(self) -> str:
        """Fetcher name."""
        return "crossref"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch from Crossref API.

        Args:
            doi: Digital Object Identifier

        Returns:
            Works object from Crossref, or None if not found
        """
        try:
            # Normalize DOI
            normalized = doi.lower().strip()
            if normalized.startswith("doi:"):
                normalized = normalized[4:]
            if normalized.startswith("https://doi.org/"):
                normalized = normalized[16:]

            # Call API
            url = f"{CROSSREF_API_URL}/works/{normalized}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # Crossref wraps result in "message"
            if data.get("status") == "ok" and "message" in data:
                return data["message"]

            return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Crossref API error for {doi}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {doi} from Crossref: {e}")
            return None

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract - Crossref provides in 'abstract' field."""
        abstract = api_data.get("abstract")
        if abstract and isinstance(abstract, str):
            # Use AbstractParser to clean up any markup
            return AbstractParser.clean(abstract)
        return None

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """Extract authors from Crossref format."""
        from paper_scanner.core.models import Author

        authors = []
        author_list = api_data.get("author", [])

        for author_data in author_list:
            given = author_data.get("given", "").strip()
            family = author_data.get("family", "").strip()

            if family:
                # Construct full_name from given and family names
                full_name = f"{given} {family}".strip() if given else family
                author = Author(
                    given_name=given or None,
                    family_name=family,
                    full_name=full_name,
                    affiliation=None,  # Crossref doesn't provide reliable affiliation
                )
                authors.append(author)

        return authors

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """
        Extract keywords from Crossref.

        Crossref provides keywords in 'subject' field (array of strings).
        These are classification subjects, not keywords, but usable as fallback.
        """
        subjects = api_data.get("subject", [])
        if isinstance(subjects, list):
            return [s.strip() for s in subjects if isinstance(s, str) and s.strip()]
        return []

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """
        Extract topics - Crossref doesn't provide topics.

        Topics come from semantic analysis (OpenAlex, etc.).
        """
        return []

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract paper type from Crossref 'type' field.

        Maps Crossref types to PaperType enum.
        Crossref types: journal-article, proceedings-article, book, report, etc.
        """
        crossref_type = api_data.get("type", "").lower()

        # Mapping Crossref types to our PaperType enum
        type_mapping = {
            "journal-article": PaperType.JOURNAL_ARTICLE,
            "proceedings-article": PaperType.CONFERENCE_PAPER,
            "book": PaperType.BOOK,
            "book-chapter": PaperType.BOOK_CHAPTER,
            "report": PaperType.TECHNICAL_REPORT,
            "dataset": PaperType.DATASET,
            "preprint": PaperType.PREPRINT,
        }

        mapped_type = type_mapping.get(crossref_type)
        return mapped_type.value if mapped_type else None

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[OpenAccessStatus]:
        """
        Extract OA status from Crossref.

        Crossref provides 'is-referenced-by-count' but NOT direct OA info.
        OA detection should use Unpaywall or other sources.
        """
        # Crossref doesn't provide OA status directly
        return None

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract source-specific key from Crossref.

        Use DOI as source key since Crossref's primary identifier is DOI.
        """
        doi = api_data.get("DOI")
        return doi if doi else None

    def _extract_citations(self, api_data: Dict[str, Any]) -> List[Citation]:
        """
        Extract Citation objects from Crossref reference list.

        Args:
            api_data: Full API response dict with 'reference' field

        Returns:
            List of Citation objects
        """
        citations = []
        references = api_data.get("reference", [])

        for idx, ref in enumerate(references):
            try:
                citation = self._parse_reference(ref, idx)
                if citation:
                    citations.append(citation)
            except Exception as e:
                logger.warning(f"Failed to parse reference {idx}: {e}")
                continue

        return citations

    def _parse_reference(self, ref: Dict[str, Any], idx: int) -> Optional[Citation]:
        """
        Parse single Crossref reference into Citation model.

        Args:
            ref: Reference dict from Crossref
            idx: Index in references list (for logging)

        Returns:
            Citation object or None if parsing fails
        """
        # Extract DOI
        doi = ref.get("DOI", None)
        if doi:
            doi = DOI(doi).stem

        # Extract title
        title = ref.get("unstructured", "").strip()
        if not title and "article-title" in ref:
            title = ref.get("article-title", "").strip()

        # Extract first author
        authors = []
        author_str = ref.get("author", "")
        if author_str:
            authors = [author_str.strip()]

        # Extract year
        year = None
        year_val = ref.get("year")
        if year_val:
            try:
                year = int(year_val)
            except (ValueError, TypeError):
                pass

        # Extract journal
        journal = (ref.get("journal-title") or "").strip() or (ref.get("container-title") or "").strip()

        # Extract volume, issue, pages
        volume = (ref.get("volume") or "").strip() or None
        issue = (ref.get("issue") or "").strip() or None
        first_page = (ref.get("first-page") or "").strip() or None
        last_page = (ref.get("last-page") or "").strip() or None

        pages = None
        if first_page and last_page:
            pages = f"{first_page}-{last_page}"
        elif first_page:
            pages = first_page

        # Extract publisher
        publisher = (ref.get("publisher") or "").strip() or None

        # Calculate confidence
        confidence = self._calculate_confidence(doi, title, year, authors)

        # Build Citation
        citation = Citation(
            doi=doi,
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            volume=volume,
            issue=issue,
            pages=pages,
            publisher=publisher,
            extraction_method="crossref",
            confidence=confidence,
            raw_text=ref.get("unstructured"),
        )

        return citation

    def _calculate_confidence(
        self,
        doi: Optional[str],
        title: Optional[str],
        year: Optional[int],
        authors: List[str],
    ) -> float:
        """
        Calculate extraction confidence score.

        Args:
            doi: DOI (if present)
            title: Title (if present)
            year: Year (if present)
            authors: Authors list

        Returns:
            Confidence score 0.0-1.0
        """
        score = 0.5  # Base score for any citation

        if doi:
            score += 0.35  # DOI present adds 0.35
        if title and len(title) > 10:
            score += 0.1  # Meaningful title adds 0.1
        if year:
            score += 0.05  # Year adds 0.05

        return min(score, 1.0)  # Cap at 1.0
