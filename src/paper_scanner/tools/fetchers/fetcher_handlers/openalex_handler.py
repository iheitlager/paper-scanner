"""
OpenAlex API handler - metadata and citations fetcher.

Fetches publication metadata from OpenAlex API with better abstract/keyword coverage.
API docs: https://docs.openalex.org/
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import CitationDirection, PaperType
from paper_scanner.core.models import Citation, OpenAccessStatus
from paper_scanner.tools.documents.abstract_parser import AbstractParser
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler

console = Console(file=sys.stderr)

# OpenAlex API configuration
OPENALEX_API_URL = "https://api.openalex.org"
OPENALEX_USER_AGENT = "paper-scanner/1.0 (mailto:i.heitlager@tue.nl)"

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 10


class OpenAlexHandler(BaseFetcherHandler):
    """Fetcher for OpenAlex API metadata and citations."""

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False):
        """Initialize OpenAlex handler."""
        super().__init__(cache_dir, debug=debug, verbose=verbose)
        self.session = requests.Session()
        # TODO: Improve this
        self.session.headers.update({"User-Agent": OPENALEX_USER_AGENT})

    @property
    def name(self) -> str:
        """Fetcher name."""
        return "openalex"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch from OpenAlex API using DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Work object from OpenAlex, or None if not found
        """
        # Normalize DOI
        normalized = DOI(doi).uri

        # OpenAlex uses doi: prefix in URL
        # Endpoint: /works/doi:{doi}
        url = f"{OPENALEX_API_URL}/works/{normalized}"
        if self.verbose:
            console.print(f"Fetching OpenAlex data for DOI {normalized} from {url}")

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if self.debug:
                console.print(f"[dim]Response status code: {response.status_code}[/dim]")
                console.print(f"[dim]Response content: {response.text}[/dim]")

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # OpenAlex returns work directly (no wrapper)
            return data

        except requests.exceptions.RequestException:
            return None

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract abstract from OpenAlex.

        OpenAlex provides abstract in 'abstract_inverted_index' field.
        This is an inverted index format that needs reconstruction.
        """
        inverted_index = api_data.get("abstract_inverted_index")

        if not inverted_index:
            return None

        try:
            # Reconstruct abstract from inverted index
            # Format: {"word": [position1, position2], ...}
            word_positions = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))

            # Sort by position and join
            word_positions.sort(key=lambda x: x[0])
            abstract = " ".join(word for _, word in word_positions)

            # Clean up with AbstractParser
            return AbstractParser.clean(abstract)

        except Exception:
            return None

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """
        Extract authors from OpenAlex format.
        
        OpenAlex provides rich author data including ORCID and affiliations.
        """
        from paper_scanner.core.models import Author

        authors = []
        authorships = api_data.get("authorships", [])

        for authorship in authorships:
            author_data = authorship.get("author", {})

            display_name = author_data.get("display_name", "").strip()

            if display_name:
                # Extract affiliation (first one if multiple)
                affiliations = authorship.get("institutions", [])
                affiliation = None
                if affiliations and len(affiliations) > 0:
                    affiliation = affiliations[0].get("display_name")

                # Try to split into given/family names
                # OpenAlex doesn't always provide this split
                name_parts = display_name.split()
                given_name = None
                family_name = display_name

                if len(name_parts) > 1:
                    given_name = " ".join(name_parts[:-1])
                    family_name = name_parts[-1]

                author = Author(
                    given_name=given_name,
                    family_name=family_name,
                    full_name=display_name,
                    affiliation=affiliation,
                )
                authors.append(author)

        return authors

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """
        Extract keywords from OpenAlex concepts.
        
        OpenAlex provides 'concepts' field with scored topics.
        We take high-scoring concepts (score > 0.3) as keywords.
        """
        concepts = api_data.get("concepts", [])
        keywords = []

        for concept in concepts:
            # Filter by score threshold
            score = concept.get("score", 0)
            if score > 0.3:  # Only include concepts with >30% relevance
                display_name = concept.get("display_name", "").strip()
                if display_name:
                    keywords.append(display_name)

        return keywords

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """
        Extract topics from OpenAlex.
        
        OpenAlex provides 'topics' field (newer feature).
        Falls back to broader 'concepts' if topics not available.
        """
        topics = []

        # Try topics field first (newer OpenAlex feature)
        topic_list = api_data.get("topics", [])
        for topic in topic_list:
            display_name = topic.get("display_name", "").strip()
            if display_name:
                topics.append(display_name)

        # If no topics, fall back to high-level concepts
        if not topics:
            concepts = api_data.get("concepts", [])
            for concept in concepts:
                # Only include top-level (level 0-1) high-scoring concepts
                level = concept.get("level", 999)
                score = concept.get("score", 0)
                if level <= 1 and score > 0.5:
                    display_name = concept.get("display_name", "").strip()
                    if display_name:
                        topics.append(display_name)

        return topics

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract paper type from OpenAlex 'type' field.
        
        Maps OpenAlex types to PaperType enum.
        OpenAlex types: article, book, dataset, paratext, etc.
        """
        openalex_type = api_data.get("type", "").lower()

        # Mapping OpenAlex types to our PaperType enum
        type_mapping = {
            "article": PaperType.JOURNAL_ARTICLE,
            "book": PaperType.BOOK,
            "book-chapter": PaperType.BOOK_CHAPTER,
            "dataset": PaperType.DATASET,
            "dissertation": PaperType.THESIS,
            "report": PaperType.TECHNICAL_REPORT,
            "preprint": PaperType.PREPRINT,
        }

        # OpenAlex doesn't distinguish conference papers well
        # Check if it's in proceedings
        type_crossref = api_data.get("type_crossref")
        if type_crossref == "proceedings-article":
            return PaperType.CONFERENCE_PAPER.value

        mapped_type = type_mapping.get(openalex_type)
        return mapped_type.value if mapped_type else None

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """
        Extract publication year from OpenAlex.
        
        OpenAlex provides 'publication_year' field directly.
        Falls back to 'publication_date' if needed.
        """
        # Try publication_year first (simplest)
        year = api_data.get("publication_year")
        if year and isinstance(year, int):
            return year

        # Try publication_date
        pub_date = api_data.get("publication_date")
        if pub_date and isinstance(pub_date, str):
            try:
                # Format: "2024-01-15"
                return int(pub_date.split("-")[0])
            except (ValueError, IndexError):
                pass

        return None

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract journal name from OpenAlex.
        
        OpenAlex provides journal in 'primary_location.source.display_name'.
        """
        primary_location = api_data.get("primary_location")
        if not primary_location:
            return None

        source = primary_location.get("source")
        if not source:
            return None

        display_name = source.get("display_name")
        if display_name and isinstance(display_name, str):
            return display_name.strip()

        return None

    def _extract_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract URL from OpenAlex.
        
        OpenAlex provides multiple URL options:
        - primary_location.landing_page_url (preferred)
        - doi (as fallback, convert to URL)
        """
        # Try primary_location landing page
        primary_location = api_data.get("primary_location")
        if primary_location:
            landing_page = primary_location.get("landing_page_url")
            if landing_page and isinstance(landing_page, str):
                return landing_page.strip()

        # Try best_oa_location as fallback
        best_oa = api_data.get("best_oa_location")
        if best_oa:
            landing_page = best_oa.get("landing_page_url")
            if landing_page and isinstance(landing_page, str):
                return landing_page.strip()

        # Fallback to DOI URL
        doi = api_data.get("doi")
        if doi:
            return f"https://doi.org/{DOI(doi).stem}"

        return None

    def _extract_isbn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISBN from OpenAlex.
        
        OpenAlex doesn't directly provide ISBN in standard format.
        Would need to check ids field for isbn: prefix.
        """
        # OpenAlex doesn't reliably provide ISBN
        return None

    def _extract_issn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISSN from OpenAlex.
        
        OpenAlex provides ISSN in primary_location.source.issn field.
        """
        primary_location = api_data.get("primary_location")
        if not primary_location:
            return None

        source = primary_location.get("source")
        if not source:
            return None

        # ISSN can be a list or single string
        issn = source.get("issn")
        if issn:
            if isinstance(issn, list) and len(issn) > 0:
                return issn[0]
            elif isinstance(issn, str):
                return issn.strip()

        return None

    def _extract_pmid(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PubMed ID from OpenAlex.
        
        OpenAlex provides pmid in 'ids.pmid' field.
        Format: "https://pubmed.ncbi.nlm.nih.gov/12345678"
        """
        ids = api_data.get("ids", {})
        pmid_url = ids.get("pmid")

        if pmid_url and isinstance(pmid_url, str):
            # Extract numeric ID from URL
            try:
                return pmid_url.split("/")[-1]
            except (ValueError, IndexError):
                pass

        return None

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[OpenAccessStatus]:
        """
        Extract Open Access status from OpenAlex.
        
        OpenAlex provides comprehensive OA information:
        - open_access.is_oa: boolean
        - open_access.oa_status: "gold", "green", "hybrid", "bronze", "closed"
        """
        oa_info = api_data.get("open_access", {})

        is_oa = oa_info.get("is_oa", False)
        oa_status_str = oa_info.get("oa_status", "closed").lower()

        return OpenAccessStatus(
            is_oa=is_oa,
            oa_status=oa_status_str,
            source=self.name,
        )

    def _extract_publisher(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract publisher from OpenAlex.
        
        OpenAlex provides publisher in 'publisher' field.
        """
        publisher = api_data.get("primary_location", {}).get("source", {}).get("host_organization_name")
        if publisher and isinstance(publisher, str):
            return publisher.strip()

        publisher = api_data.get("best_oa_location", {}).get("source", {}).get("host_organization_name")
        if publisher and isinstance(publisher, str):
            return publisher.strip()

        return None

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract source-specific key from OpenAlex.
        
        Uses OpenAlex work ID (format: W1234567890).
        Falls back to DOI if work ID not available.
        """
        # Try OpenAlex ID first
        openalex_id = api_data.get("id")
        if openalex_id:
            # Extract just the ID part from URL
            # Format: "https://openalex.org/W2741809807"
            try:
                return openalex_id.split("/")[-1]
            except (ValueError, IndexError):
                pass

        # Fall back to DOI
        doi = api_data.get("doi")
        if doi:
            return DOI(doi).stem

        return None

    def _extract_citations(self, api_data: Dict[str, Any]) -> List[Citation]:
        """
        Extract Citation objects from OpenAlex referenced works.

        OpenAlex provides 'referenced_works' field (list of OpenAlex IDs).
        Unlike Crossref, this only gives IDs, not full citation metadata.
        We would need additional API calls to get full citation details.

        For now, we return empty list since we'd need to fetch each reference.
        Consider implementing batch fetching if needed.
        """
        # OpenAlex provides referenced_works as list of IDs
        # Example: ["W2741809807", "W2123456789"]
        # Would require additional API calls to get full citation data

        # For basic implementation, we can create minimal citations with just IDs
        citations = []
        referenced_works = api_data.get("referenced_works", [])

        for idx, work_id in enumerate(referenced_works):
            try:
                # Extract OpenAlex ID
                openalex_id = work_id.split("/")[-1] if "/" in work_id else work_id

                # Create minimal citation with just ID
                # In a full implementation, you'd fetch the work details
                citation = Citation(
                    doi=None,  # Would need to fetch
                    source_key=openalex_id,
                    direction=CitationDirection.BACKWARD,
                    title=None,  # Would need to fetch
                    authors=[],  # Would need to fetch
                    year=None,  # Would need to fetch
                    journal=None,
                    volume=None,
                    issue=None,
                    pages=None,
                    publisher=None,
                    extraction_method=self.name,
                    confidence=0.5,  # Medium confidence since we only have ID
                    raw_text=openalex_id,
                    raw_json={"openalex_id": openalex_id},
                )
                citations.append(citation)
            except Exception:
                continue

        return citations

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PDF download URL from OpenAlex metadata.
        
        OpenAlex API responses include:
        - "open_access" object with "pdf_url", "is_oa"
        - "has_fulltext" boolean

        Args:
            api_data: OpenAlex API response metadata

        Returns:
            URL string if found, None otherwise
        """
        # TODO: Investigate OpenAlex metadata structure for PDF URLs
        # Check ~/.paper-scanner/openalex/ for sample responses

        # Placeholder implementation
        return None

    def _fetch_cited_by_from_api(self, doi: str, limit: int = 100) -> Dict[str, Any]:
        """
        Fetch and parse forward citations for a given DOI.

        Args:
            doi: Digital Object Identifier
        Returns:
            Tuple of (citations list, cache_hit: bool)
        """

        metadata, _ = self.fetch_metadata(doi)
        if not metadata:
            return []

        source_key = self._extract_source_key(metadata)

        # Call API
        try:
            # OpenAlex uses filter query: cites:<openalex_id>
            url = (
                f"{OPENALEX_API_URL}/works?"
                f"filter=cites:{source_key}&"
                f"per-page={min(limit, 200)}"
            )

            response = self.session.get(url, timeout=10)
            if self.debug:
                console.print(f"[dim]Response status code: {response.status_code}[/dim]")
                console.print(f"[dim]Response content: {response.text}[/dim]")

            if response.status_code == 404:  # 404: Not Found
                return []

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            return results
        except requests.exceptions.RequestException as e:
            console.print(f"[red]OpenAlex API error for {doi}: {e}[/red]")
            return []

    def _parse_cited_by(self, work: Dict[str, Any]) -> Citation:
        """
        Parse a single forward citation from OpenAlex API work object.

        Args:
            work: Single OpenAlex work object
        Returns:
            Citation object
        """
        try:
            doi = DOI(work.get("doi")).stem if work.get("doi") else None
            source_key = work.get("id").split("/")[-1] if work.get("id") else None
            title = work.get("title")
            year = work.get("publication_year")

            # Extract authors
            authors = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name")
                if name:
                    authors.append(name)

            # Extract journal
            journal = None
            primary_location = work.get("primary_location")
            if primary_location:
                source = primary_location.get("source")
                if source:
                    journal = source.get("display_name")

            citation = Citation(
                doi=doi,
                source_key=source_key,
                direction=CitationDirection.FORWARD,
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                extraction_method=self.name,
                confidence=0.8,  # Medium-high confidence
                raw_json=work,
            )
            return citation
        except Exception:
            return None
