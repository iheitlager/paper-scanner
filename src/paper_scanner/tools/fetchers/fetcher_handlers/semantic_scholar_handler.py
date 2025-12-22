"""
Semantic Scholar API Handler - Fetcher implementation for S2 API.

Rate Limits:
  - Free tier: 100 requests per 5 minutes
  - With API key: 5,000 requests per 5 minutes (request from S2)

Coverage: ~200M papers with rich metadata

API Documentation: https://api.semanticscholar.org/api-docs/graph
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

from paper_scanner.core.models import Citation
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler

console = Console(file=sys.stderr)


class SemanticScholarHandler(BaseFetcherHandler):
    """
    Semantic Scholar API handler for metadata fetching.

    Implements the BaseFetcherHandler interface for S2 API integration.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    # Fields to request from Semantic Scholar API
    FIELDS = [
        "paperId",
        "corpusId",
        "url",
        "title",
        "abstract",
        "venue",
        "year",
        "publicationDate",
        "publicationTypes",
        "externalIds",
        "authors",
        "citationCount",
        "influentialCitationCount",
        "s2FieldsOfStudy",
        "publicationVenue",
        "tldr",
        "openAccessPdf",
        "journal",
        "isOpenAccess",
    ]

    # Fields for citations endpoint
    CITATIONS_FIELDS = [
        "paperId",
        "title",
        "abstract",
        "authors",
        "year",
        "venue",
        "citationCount",
        "externalIds",
        "publicationTypes",
    ]

    def __init__(
        self,
        cache_dir: Path,
        api_key: Optional[str] = None,
        debug: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize Semantic Scholar handler.

        Args:
            cache_dir: Cache directory for API responses
            api_key: Optional Semantic Scholar API key for higher rate limits
            debug: Enable debug output
            verbose: Enable verbose output
        """
        super().__init__(cache_dir, debug=debug, verbose=verbose)
        self.api_key = api_key
        self.session = requests.Session()

        # Set headers
        headers = {"User-Agent": "paper-scanner/3.2.0"}
        if api_key:
            headers["x-api-key"] = api_key
        self.session.headers.update(headers)

    @property
    def name(self) -> str:
        """Return handler name."""
        return "semantic_scholar"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch paper metadata from Semantic Scholar API by DOI.

        Args:
            doi: Digital Object Identifier (normalized, without DOI: prefix)

        Returns:
            Raw API response dict, or None if not found/error
        """
        # Normalize DOI
        if doi.startswith("DOI:"):
            doi = doi[4:]
        if doi.startswith("10."):
            paper_id = doi
        else:
            # Try as-is (could be S2 paperId, ArXiv, etc.)
            paper_id = doi

        url = f"{self.BASE_URL}/paper/{paper_id}"
        params = {"fields": ",".join(self.FIELDS)}

        try:
            if self.debug:
                console.print(f"[dim]Fetching from S2: {url}[/dim]")

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 404:
                if self.debug:
                    console.print(f"[dim]Paper not found: {doi}[/dim]")
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.debug:
                console.print(f"[yellow]S2 API error for {doi}: {e}[/yellow]")
            return None

    def _fetch_cited_by_from_api(
        self, doi: str, limit: Optional[int] = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch forward citations (papers that cite this paper) from S2 API.

        Args:
            doi: Digital Object Identifier (normalized)
            limit: Maximum number of citations to fetch

        Returns:
            List of citation data dicts, or None if error
        """
        # Normalize DOI
        if doi.startswith("DOI:"):
            doi = doi[4:]
        if doi.startswith("10."):
            paper_id = doi
        else:
            paper_id = doi

        url = f"{self.BASE_URL}/paper/{paper_id}/citations"
        params = {
            "fields": ",".join(self.CITATIONS_FIELDS),
            "limit": limit or 100,
            "offset": 0,
        }

        try:
            if self.debug:
                console.print(f"[dim]Fetching citations from S2: {url}[/dim]")

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                if self.debug:
                    console.print(f"[dim]Paper not found: {doi}[/dim]")
                return None

            response.raise_for_status()
            data = response.json()

            # Extract list of citation objects from response
            if "data" in data:
                return data["data"]
            return None

        except requests.exceptions.RequestException as e:
            if self.debug:
                console.print(f"[yellow]S2 citations API error for {doi}: {e}[/yellow]")
            return None

    def _parse_cited_by(self, citation_data: Dict[str, Any]) -> Citation:
        """
        Parse a forward citation from S2 API response.

        Args:
            citation_data: Citation object from S2 API (contains citingPaper)

        Returns:
            Citation model instance
        """
        citing_paper = citation_data.get("citingPaper", {})

        # Extract DOI from externalIds
        external_ids = citing_paper.get("externalIds", {})
        doi = external_ids.get("DOI")

        # Extract authors
        authors = []
        for author in citing_paper.get("authors", []):
            if isinstance(author, dict):
                authors.append(author.get("name", ""))
            else:
                authors.append(str(author))

        # Create Citation model
        citation = Citation(
            doi=doi,
            title=citing_paper.get("title", ""),
            authors=authors,
            year=citing_paper.get("year"),
            venue=citing_paper.get("venue"),
            citation_count=citing_paper.get("citationCount", 0),
            is_influential=citation_data.get("isInfluential", False),
        )

        return citation

    def _extract_title(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract title from S2 API response."""
        title = api_data.get("title", "")
        if title:
            return self._clean_title(title)
        return None

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract from S2 API response."""
        return api_data.get("abstract")

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """Extract authors from S2 API response."""
        authors = []
        for author in api_data.get("authors", []):
            if isinstance(author, dict):
                name = author.get("name")
                if name:
                    authors.append(name)
            elif isinstance(author, str):
                authors.append(author)
        return authors

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """
        Extract keywords from S2 API response.

        S2 doesn't provide explicit keywords, but we can use fieldsOfStudy.
        """
        return []  # S2 doesn't provide keywords field

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """Extract topics (fields of study) from S2 API response."""
        topics = []
        for field in api_data.get("s2FieldsOfStudy", []):
            if isinstance(field, dict):
                category = field.get("category")
                if category:
                    topics.append(category)
            elif isinstance(field, str):
                topics.append(field)
        return topics

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract paper type from S2 API response."""
        types = api_data.get("publicationTypes", [])
        if types:
            if isinstance(types, list):
                return types[0]
            return str(types)
        return None

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from S2 API response."""
        year = api_data.get("year")
        if year:
            try:
                return int(year)
            except (TypeError, ValueError):
                return None
        return None

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract journal name from S2 API response."""
        # Try venue field first
        venue = api_data.get("venue")
        if venue:
            return venue

        # Try publicationVenue.name
        pub_venue = api_data.get("publicationVenue")
        if isinstance(pub_venue, dict):
            return pub_venue.get("name")

        # Try journal.name
        journal = api_data.get("journal")
        if isinstance(journal, dict):
            return journal.get("name")

        return None

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """Extract OpenAccess status from S2 API response."""
        is_oa = api_data.get("isOpenAccess")
        if is_oa is not None:
            return "open" if is_oa else "closed"
        return None

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract Semantic Scholar source key (paperId or corpusId)."""
        # Use paperId as source key
        paper_id = api_data.get("paperId")
        if paper_id:
            return f"s2:{paper_id}"

        corpus_id = api_data.get("corpusId")
        if corpus_id:
            return f"s2:{corpus_id}"

        return None

    def _extract_citations(self, api_data: Dict[str, Any]) -> List[Citation]:
        """
        Extract citations from S2 API response.

        Note: Forward citations (who cites this paper) need a separate API call.
        This extracts any citation data included in the paper metadata.

        Args:
            api_data: Paper metadata from S2 API

        Returns:
            List of Citation models
        """
        # S2 doesn't include full citation data in paper metadata
        # Citation fetching is done via _fetch_cited_by_from_api
        return []

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Find downloadable PDF URL from S2 API response.

        Args:
            api_data: Paper metadata from S2 API

        Returns:
            Download URL string, or None if no PDF available
        """
        # Check openAccessPdf field
        oa_pdf = api_data.get("openAccessPdf")
        if isinstance(oa_pdf, dict):
            url = oa_pdf.get("url")
            if url:
                return url

        return None

    def fetch_pdf(self, doi: str, timeout: int = 30) -> None:
        """
        Fetch PDF for a DOI.

        Semantic Scholar API doesn't provide direct PDF downloads.
        Use openAccessPdf URL if available, but cannot fully implement this.

        Args:
            doi: Digital Object Identifier

        Raises:
            NotImplementedError: PDF fetching not supported via S2 API
        """
        raise NotImplementedError(
            "Semantic Scholar API does not provide direct PDF downloads. "
            "Use openAccessPdf URL from metadata instead."
        )
