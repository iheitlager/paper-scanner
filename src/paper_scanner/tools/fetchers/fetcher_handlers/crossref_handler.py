"""
Crossref API handler - metadata and citations fetcher.

Fetches publication metadata and backward citations from Crossref API.
API docs: https://github.com/CrossRef/rest-api-doc
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import CitationDirection, PaperType
from paper_scanner.core.models import Citation, OpenAccessStatus
from paper_scanner.tools.documents.abstract_parser import AbstractParser
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler

# Polite pool per Crossref requirements
CROSSREF_API_URL = "https://api.crossref.org"
CROSSREF_POLITE_EMAIL = "i.heitlager@tue.nl"
CROSSREF_USER_AGENT = "paper-scanner/1.0 (mailto:{})".format(CROSSREF_POLITE_EMAIL)

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 10


class CrossrefHandler(BaseFetcherHandler):
    """Fetcher for Crossref API metadata and citations."""

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False):
        """Initialize Crossref handler."""
        super().__init__(cache_dir, debug=debug, verbose=verbose)
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
            # Normalize DOI, just in case
            normalized = DOI(doi).stem

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

        # TODO: remove this broad exception handling and just fail
        except requests.exceptions.RequestException:
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

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """
        Extract publication year from Crossref API data.
        
        Crossref provides year in multiple places with different formats:
        - published-print.date-parts: [[2026, 3]] (preferred)
        - published-online.date-parts: [[2026, 3]]
        - created.date-parts: [[2025, 10, 25]]
        - issued.date-parts: [[2026, 3]]
        """
        # Try published-print first
        if "published-print" in api_data:
            date_parts = api_data["published-print"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                year_parts = date_parts[0]
                if isinstance(year_parts, (list, tuple)) and len(year_parts) > 0:
                    try:
                        return int(year_parts[0])
                    except (ValueError, TypeError):
                        pass

        # Try published-online
        if "published-online" in api_data:
            date_parts = api_data["published-online"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                year_parts = date_parts[0]
                if isinstance(year_parts, (list, tuple)) and len(year_parts) > 0:
                    try:
                        return int(year_parts[0])
                    except (ValueError, TypeError):
                        pass

        # Try issued
        if "issued" in api_data:
            date_parts = api_data["issued"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                year_parts = date_parts[0]
                if isinstance(year_parts, (list, tuple)) and len(year_parts) > 0:
                    try:
                        return int(year_parts[0])
                    except (ValueError, TypeError):
                        pass

        # Try created
        if "created" in api_data:
            date_parts = api_data["created"].get("date-parts")
            if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                year_parts = date_parts[0]
                if isinstance(year_parts, (list, tuple)) and len(year_parts) > 0:
                    try:
                        return int(year_parts[0])
                    except (ValueError, TypeError):
                        pass

        return None

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract journal name from Crossref API data.
        
        Crossref provides journal in:
        - container-title: ["Journal Name"] (preferred for journal articles)
        - short-container-title: ["J. Name"]
        """
        # Try container-title first (standard BibTeX field for journals)
        container_title = api_data.get("container-title")
        if container_title:
            if isinstance(container_title, list) and len(container_title) > 0:
                return container_title[0].strip() if isinstance(container_title[0], str) else None
            elif isinstance(container_title, str):
                return container_title.strip() if container_title else None

        # Try short-container-title as fallback
        short_title = api_data.get("short-container-title")
        if short_title:
            if isinstance(short_title, list) and len(short_title) > 0:
                return short_title[0].strip() if isinstance(short_title[0], str) else None
            elif isinstance(short_title, str):
                return short_title.strip() if short_title else None

        return None

    def _extract_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract URL from Crossref API data.
        
        Crossref provides URL in:
        - resource.primary.URL: Primary/preferred URL to the resource
        - URL: Alternative location for URL field
        """
        # Try resource.primary.URL first (preferred)
        resource = api_data.get("resource")
        if resource and isinstance(resource, dict):
            primary = resource.get("primary")
            if primary and isinstance(primary, dict):
                url = primary.get("URL")
                if url and isinstance(url, str):
                    return url.strip() if url else None

        # Try top-level URL field as fallback
        url = api_data.get("URL")
        if url and isinstance(url, str):
            return url.strip() if url else None

        return None

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

        Tries alternative-id first (publisher-specific identifier like PII),
        falls back to DOI. Normalizes DOI using stem.
        """
        # Try alternative-id first (e.g., Elsevier PII)
        alternative_ids = api_data.get("alternative-id")
        if alternative_ids and isinstance(alternative_ids, list) and len(alternative_ids) > 0:
            return alternative_ids[0]

        # Fall back to DOI (normalized)
        doi = api_data.get("DOI")
        if doi:
            return DOI(doi).stem

        return None

    def _extract_isbn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISBN from Crossref API data.
        
        Crossref provides ISBNs in 'isbn' field (array of strings).
        """
        isbns = api_data.get("isbn")
        if isbns and isinstance(isbns, list) and len(isbns) > 0:
            return isbns[0]
        return None

    def _extract_issn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISSN from Crossref API data.
        
        Crossref provides ISSNs in 'issn' field (array of strings).
        """
        issns = api_data.get("issn")
        if issns and isinstance(issns, list) and len(issns) > 0:
            return issns[0]
        return None

    def _extract_pmid(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PubMed ID from Crossref API data.
        
        Crossref doesn't directly provide PMID. Check alternative identifiers.
        """
        # Crossref doesn't reliably provide PMID
        # Would need to check Crossref's alternative-id or look up via PubMed separately
        return None

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
        # Extract DOI and normalize, just in case
        doi = ref.get("DOI", None)
        if doi:
            doi = DOI(doi).stem

        # Extract title
        if "article-title" in ref:
            title = ref.get("article-title", "").strip()
        elif "title" in ref:
            title = ref.get("title", "").strip()
        else:
            title = ref.get("unstructured", "").strip()

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
        if ref.get("doi-asserted-by") == "publisher":
            confidence = 1.0
        else:
            confidence = self._calculate_citation_confidence(doi, title, year, authors)

        # Build Citation
        citation = Citation(
            doi=doi,
            direction=CitationDirection.BACKWARD,
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            volume=volume,
            issue=issue,
            pages=pages,
            publisher=publisher,
            extraction_method=self.name,
            confidence=confidence,
            raw_text=ref.get("unstructured"),
            raw_json=ref if not doi else None,
        )

        return citation

    def _calculate_citation_confidence(
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

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Find a downloadable PDF URL from Crossref metadata.

        Strategy:
        - Try link array for content with proper content-type
        - Prefer application/pdf over other content types
        - Skip resource.primary.URL as it often leads to paywalled landing pages

        Args:
            api_data: Crossref API response dict

        Returns:
            Download URL string, or None if no PDF link available
        """
        # Get link array for text-mining content with proper content-types
        links = api_data.get("link", [])
        if not links:
            return None

        # First pass: prefer application/pdf content-type
        for link in links:
            if link.get("content-type") == "application/pdf":
                return link.get("URL")

        # Second pass: take any URL if we didn't find PDF content-type
        for link in links:
            url = link.get("URL")
            if url and url.startswith("http"):
                return url

        return None

    def fetch_cited_by(self, doi: str) -> Tuple[List[Citation], bool]:
        """Not implemented - CrossrefHandler does not support forward citations.."""
        raise NotImplementedError("CrossrefHandler does not support forward citations.")

    def fetch_pdf(self, doi: str, timeout: int = 30):
        """Not implemented - CrossrefHandler only provides metadata and citations."""
        raise NotImplementedError("CrossrefHandler only provides metadata and citations via fetch_metadata and fetch_citations")

