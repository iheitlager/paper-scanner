"""
Manual handler - local cache for user-curated papers from bibtex files.

No API calls—purely cache-based retrieval. Papers loaded from bibtex files
with custom citation fields (cites, citedby, studytype, lastchecked) are
cached and served via the standard handler interface.
"""

from typing import Any, Dict, List, Optional

from paper_scanner.core.models import Author, Citation
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler


class ManualHandler(BaseFetcherHandler):
    """Local cache handler for user-curated papers from bibtex files."""

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False):
        """Initialize Manual handler."""
        super().__init__(cache_dir, debug=debug, verbose=verbose)

    @property
    def name(self) -> str:
        """Fetcher name."""
        return "manual"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        No API calls for manual handler - only cache-based retrieval.
        
        The base class fetch_metadata() handles all caching logic.
        Return None to indicate no API data available.

        Args:
            doi: Digital Object Identifier

        Returns:
            None (no API calls made)
        """
        return None

    def _extract_title(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract title from cached data."""
        return api_data.get("title")

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract from cached data."""
        return api_data.get("abstract")

    def _extract_authors(self, api_data: Dict[str, Any]) -> List[Author]:
        """Extract authors from cached data and convert to Author objects."""
        authors_raw = api_data.get("authors", [])
        if not isinstance(authors_raw, list):
            return []

        authors = []
        for author_str in authors_raw:
            if isinstance(author_str, dict):
                # Already an Author dict, convert to Author object
                authors.append(Author(**author_str))
            elif isinstance(author_str, Author):
                # Already an Author object
                authors.append(author_str)
            elif isinstance(author_str, str):
                # String - convert to Author object
                author_obj = self._string_to_author(author_str)
                if author_obj:
                    authors.append(author_obj)

        return authors

    @staticmethod
    def _string_to_author(author_str: str) -> Optional[Author]:
        """
        Convert author string to Author object.

        Handles formats like:
        - "Smith, John" -> family_name="Smith", given_name="John"
        - "John Smith" -> given_name="John", family_name="Smith"
        - "Smith" -> family_name="Smith"

        Args:
            author_str: Author string in various formats

        Returns:
            Author object or None if string is empty
        """
        if not author_str or not isinstance(author_str, str):
            return None

        author_str = author_str.strip()
        if not author_str:
            return None

        # Try "LastName, FirstName" format
        if "," in author_str:
            parts = author_str.split(",", 1)
            family_name = parts[0].strip()
            given_name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            return Author(
                family_name=family_name,
                given_name=given_name,
                full_name=author_str,
            )

        # Try "FirstName LastName" format
        parts = author_str.split()
        if len(parts) >= 2:
            given_name = " ".join(parts[:-1])
            family_name = parts[-1]
            return Author(
                family_name=family_name,
                given_name=given_name,
                full_name=author_str,
            )

        # Single name fallback
        return Author(
            family_name=parts[0] if parts else author_str,
            full_name=author_str,
        )

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """Extract keywords from cached data."""
        keywords = api_data.get("keywords", [])
        return keywords if isinstance(keywords, list) else []

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """Extract topics from cached data."""
        topics = api_data.get("topics", [])
        return topics if isinstance(topics, list) else []

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract paper type from cached data."""
        return api_data.get("paper_type")

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from cached data."""
        year = api_data.get("year")
        return int(year) if year else None

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract journal name from cached data."""
        return api_data.get("journal")

    def _extract_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract URL from cached data."""
        return api_data.get("url")

    def _extract_isbn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract ISBN from cached data."""
        return api_data.get("isbn")

    def _extract_issn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract ISSN from cached data."""
        return api_data.get("issn")

    def _extract_pmid(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract PubMed ID from cached data."""
        return api_data.get("pmid")

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """Extract OA status from cached data."""
        return api_data.get("oa_status")

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract source key from cached data."""
        return api_data.get("source_key")

    def _extract_citations(self, api_data: Dict[str, Any]) -> List[Citation]:
        """Extract citations from cached data and convert to Citation objects."""
        citations_raw = api_data.get("citations", [])
        if not isinstance(citations_raw, list):
            return []

        citations = []
        for citation_item in citations_raw:
            if isinstance(citation_item, dict):
                # Convert dict to Citation object
                try:
                    citation = Citation(**citation_item)
                    citations.append(citation)
                except Exception:
                    # Skip invalid citations
                    pass
            elif isinstance(citation_item, Citation):
                # Already a Citation object
                citations.append(citation_item)

        return citations

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract download URL from cached data."""
        return api_data.get("download_url")
