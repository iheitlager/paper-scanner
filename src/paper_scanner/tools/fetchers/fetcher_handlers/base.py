"""
Base fetcher handler - abstract interface for API-specific implementations.

Each API (Crossref, OpenAlex, etc.) implements this interface to provide
consistent metadata extraction and translation to Paper model.
"""

import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.doi import DOI
from paper_scanner.core.models import Citation, Paper, PDFInfo
from paper_scanner.core.cache import JSONFileCache, create_404_marker, is_404_marker

console = Console(file=sys.stderr)

class BaseFetcherHandler(ABC):
    """
    Abstract base for API-specific metadata fetchers.

    Subclasses implement API calls and field translation logic.
    """

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False):
        """
        Initialize handler with cache directory.

        Args:
            cache_dir: Directory for caching API responses (e.g., ~/.cache/paper-scanner/crossref/)
            debug: Enable debug output
            verbose: Enable verbose output
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir_json = self.cache_dir / self.name
        self.cache_dir_json.mkdir(parents=True, exist_ok=True)
        self._jsoncache = JSONFileCache(self.cache_dir_json)
        self.debug = debug
        self.verbose = verbose

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this fetcher (e.g., 'crossref')"""
        pass

    @abstractmethod
    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch raw API response for DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Raw API response as dict, or None if not found

        Raises:
            Exception: On API errors
        """
        pass

    def _extract_title(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract from API response"""
        return api_data.get("title", "")

    @abstractmethod
    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract from API response"""
        pass

    @abstractmethod
    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """Extract authors from API response"""
        pass

    @abstractmethod
    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """Extract keywords from API response"""
        pass

    @abstractmethod
    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """Extract topics from API response"""
        pass

    @abstractmethod
    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract paper type from API response"""
        pass

    @abstractmethod
    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from API response"""
        pass

    @abstractmethod
    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract journal name from API response"""
        pass

    def _extract_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract URL from API response.
        
        Default implementation returns None.
        Subclasses can override for API-specific handling.
        """
        return None

    def _extract_isbn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISBN from API response.
        
        Default implementation returns None.
        Subclasses can override for API-specific handling.
        """
        return None

    def _extract_issn(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract ISSN from API response.
        
        Default implementation returns None.
        Subclasses can override for API-specific handling.
        """
        return None

    def _extract_pmid(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract PubMed ID from API response.
        
        Default implementation returns None.
        Subclasses can override for API-specific handling.
        """
        return None

    @abstractmethod
    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """Extract OpenAccessStatus from API response"""
        pass

    @abstractmethod
    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract source-specific ID from API response"""
        pass

    @abstractmethod
    def _extract_citations(self, api_data: Dict[str, Any]) -> List[Citation]:
        """
        Extract citations from API response and convert to Citation models.

        Args:
            api_data: API response dict (same as used for metadata extraction)

        Returns:
            List of Citation objects
        """
        pass

    @abstractmethod
    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Find a downloadable PDF URL from API response.

        Handler-specific implementation to extract download URL from metadata.

        Args:
            api_data: API response dict

        Returns:
            Download URL string, or None if no PDF available
        """
        pass

    def _extract_cite_key(self, api_data: Dict[str, Any]) -> str:
        """
        Generate a cite key from API data.

        Default implementation uses uuid.

        Args:
            api_data: API response dict

        Returns:
            Generated cite key string
        """
        doi = api_data.get("DOI", "")
        if doi:
            return f"doi_{DOI(doi).md5[:8]}"
        return "unknown_cite_key"

    def _extract_publisher(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract publisher from API response.
        
        Default implementation returns None.
        Subclasses can override for API-specific handling.
        """
        return api_data.get("publisher")

    def fetch_cited_by(self, doi: str, limit: Optional[int] = 100) -> Tuple[List[Citation], bool]:
        """
        Fetch and parse forward citations for a given DOI.

        Tries handlers in order until one succeeds.
        Caches 404 responses to reduce API calls for non-existent entries.

        Args:
            doi: Digital Object Identifier
            limit: Maximum number of citations to fetch
        Returns:
            Tuple of (citations list, cache_hit: bool)
        """
        key = f"{doi}_fwd" # this is going to be mangled to md5
        api_data = self._jsoncache.get(key)
        
        if api_data is not None:
            # Check if this is a 404 marker
            if is_404_marker(api_data):
                if self.debug:
                    console.print(f"[dim]Cache hit (404) for forward citations of {doi}[/dim]")
                return [], True
            # Check if cached empty list
            if isinstance(api_data, list) and len(api_data) == 0:
                return [], True
            return [self._parse_cited_by(c) for c in api_data], True

        api_data = self._fetch_cited_by_from_api(doi, limit)
        if api_data is None or (isinstance(api_data, list) and len(api_data) == 0):
            # Cache the 404/empty response
            if self.debug:
                console.print(f"[dim]Caching 404 for forward citations of {doi}[/dim]")
            self._jsoncache.set(key, create_404_marker(key=key, url=f"https://doi.org/{doi}"))
            return [], False

        if self.debug:
            console.print(f"[dim]Caching {len(api_data)} forward citations for {doi} with key {key}[/dim]")
        self._jsoncache.set(key, api_data)
        citations = [self._parse_cited_by(c) for c in api_data]
        return citations, False

    def fetch_metadata(self, doi: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Fetch metadata for a DOI from cache or API.

        Checks cache first, then API, storing result in cache.
        Caches 404 responses to reduce API calls for non-existent entries.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (API response dict or None, cache_hit: bool)
        """
        # Check cache
        api_data = self._jsoncache.get(doi)
        if api_data is not None:
            # Check if this is a 404 marker
            if is_404_marker(api_data):
                return None, True
            return api_data, True

        api_data = self._fetch_from_api(doi)
        if api_data is None:
            self._jsoncache.set(doi, create_404_marker(key=doi, url=f"https://doi.org/{doi}"))
            return None, False

        if self.debug:
            console.print(f"[dim]Caching metadata for {doi}[/dim]")

        self._jsoncache.set(doi, api_data)
        return api_data, False

    def fetch_paper(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch Paper from DOI.

        Uses fetch_metadata to get API data, then translates to Paper model.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        api_data, cache_hit = self.fetch_metadata(doi)
        if api_data is None:
            return None, cache_hit

        paper = self._translate_to_paper(doi, api_data)
        return paper, cache_hit


    def fetch_citations(self, doi: str) -> Tuple[List[Citation], bool]:
        """
        Fetch citations and parse into Citation models.

        Reuses the same cache as fetch_paper since citations are
        part of the API response (e.g., Crossref includes references in work record).

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (List[Citation] models, cache_hit: bool)
        """
        api_data, cache_hit = self.fetch_metadata(doi)
        if api_data is None:
            return [], False

        citations = self._extract_citations(api_data)
        return citations, cache_hit

    def fetch_pdf(self, doi: str, timeout: int = 30) -> Optional[PDFInfo]:
        """
        Fetch PDF for a DOI and download to temporary location.

        Gets metadata, finds download URL, and downloads PDF to temp folder.

        Args:
            doi: Digital Object Identifier

        Returns:
            PDFInfo with file path and metadata, or None if not found
        """
        import tempfile

        import requests

        # Get metadata (uses cache)
        api_data, _ = self.fetch_metadata(doi)
        if api_data is None:
            return None

        # Find download URL (handler-specific)
        download_url = self._find_download_url(api_data)
        if not download_url:
            return None

        # Download to temporary folder
        try:
            response = requests.get(download_url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Check if we got HTML instead of PDF (common with paywalled content)
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                if self.debug:
                    console.print(f"[yellow]Got HTML page instead of PDF from {download_url}[/yellow]")
                return None

            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(response.content)
                pdf_path = Path(tmp_file.name)

                # Return PDFInfo with download source (handler name)
                return PDFInfo(
                    file_path=str(pdf_path),
                    file_size_bytes=pdf_path.stat().st_size,
                    download_source=self.name,
                    download_url=download_url,
                    downloaded_at=datetime.now(),
                )
        except Exception as e:
            if self.debug:
                console.print(f"[yellow]Failed to download PDF from {download_url}: {e}[/yellow]")
            return None

    def _translate_to_paper(self, doi: str, api_data: Dict[str, Any]) -> Paper:
        """
        Translate API response into Paper model.

        Args:
            doi: The DOI (normalized)
            api_data: Raw API response

        Returns:
            Paper model instance
        """
        from paper_scanner.core.enum import DiscoveryMethod
        from paper_scanner.core.models import Discovery

        # Extract fields
        title = self._extract_title(api_data)
        if isinstance(title, list):
            title = title[0] if title else ""

        # Clean up title: remove newlines and HTML tags
        title = self._clean_title(title)

        abstract = self._extract_abstract(api_data)
        authors = self._extract_authors(api_data)
        keywords = self._extract_keywords(api_data)
        topics = self._extract_topics(api_data)
        paper_type = self._extract_paper_type(api_data)
        oa_status = self._extract_oa_status(api_data)
        source_key = self._extract_source_key(api_data)

        # Extract other fields using new extraction methods
        year = self._extract_year(api_data)
        journal = self._extract_journal(api_data)
        url = self._extract_url(api_data)
        isbn = self._extract_isbn(api_data)
        issn = self._extract_issn(api_data)
        pmid = self._extract_pmid(api_data)
        publisher = self._extract_publisher(api_data)
        volume = api_data.get("volume")
        number = api_data.get("issue")
        pages = api_data.get("pages")
        language = api_data.get("language", "en")
        publication_date = api_data.get("publication_date")

        # Extract citations
        citations = self._extract_citations(api_data)

        # Generate cite key from author + year
        cite_key = self._generate_cite_key(authors, year, doi)

        # Create Paper model
        paper = Paper(
            cite_key=cite_key,
            source_key=source_key,
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            keywords=keywords,
            topics=topics,
            year=year,
            journal=journal,
            url=url,
            isbn=isbn,
            issn=issn,
            pmid=pmid,
            publisher=publisher,
            volume=volume,
            number=number,
            pages=pages,
            publication_date=publication_date,
            language=language,
            paper_type=paper_type,
            oa_status=oa_status,
            citations=citations,
            discovery=Discovery(
                method=DiscoveryMethod.API,
                source_database=self.name,
                record_update=datetime.now(),
            ),
            raw_json=api_data,
        )

        return paper

    def _generate_cite_key(self, authors: list, year: Optional[int], doi: str) -> str:
        """
        Generate cite key using MD5 hash of DOI.

        Deterministic and unique: same DOI always produces same cite_key.
        Falls back to random UUID if no DOI provided.
        """
        import uuid

        if doi:
            # Hash the normalized DOI for reproducibility
            hash_input = DOI(doi).md5
            return "doi_" + hash_input[:8]

        # Fallback: random UUID if no DOI
        return str(uuid.uuid4())[:8]

    def _clean_title(self, title: str) -> str:
        """
        Clean title by removing newlines, HTML tags, and excess whitespace.

        Args:
            title: Raw title string (may contain newlines, HTML markup)

        Returns:
            Cleaned title string
        """
        import re

        if not title or not isinstance(title, str):
            return title

        # Remove HTML tags like <scp>, <i>, <b>, <sup>, <sub>, etc.
        title = re.sub(r'<[^>]+>', '', title)

        # Replace newlines and excessive whitespace with single space
        title = re.sub(r'\s+', ' ', title)

        # Strip leading/trailing whitespace
        title = title.strip()

        return title

    def merge_papers(self, target: Paper, source: Paper, overwrite: bool = False) -> None:
        """
        Merge metadata from enriched Paper into target Paper.

        Only updates fields that are empty in the target.
        """
        if (overwrite or not target.abstract) and source.abstract:
            target.abstract = source.abstract

        if (overwrite or not target.title) and source.title:
            target.title = source.title

        if (overwrite or not target.keywords) and source.keywords:
            target.keywords = source.keywords

        if (overwrite or not target.topics) and source.topics:
            target.topics = source.topics

        if (overwrite or not target.authors) and source.authors:
            target.authors = source.authors

        if (overwrite or not target.year) and source.year:
            target.year = source.year

        if (overwrite or not target.journal) and source.journal:
            target.journal = source.journal

        if (overwrite or not target.url) and source.url:
            target.url = source.url

        if (overwrite or not target.isbn) and source.isbn:
            target.isbn = source.isbn

        if (overwrite or not target.issn) and source.issn:
            target.issn = source.issn

        if (overwrite or not target.pmid) and source.pmid:
            target.pmid = source.pmid

        if (overwrite or not target.publisher) and source.publisher:
            target.publisher = source.publisher

        if (overwrite or not target.volume) and source.volume:
            target.volume = source.volume

        if (overwrite or not target.number) and source.number:
            target.number = source.number

        if (overwrite or not target.pages) and source.pages:
            target.pages = source.pages

        if (overwrite or not target.publication_date) and source.publication_date:
            target.publication_date = source.publication_date

        if (overwrite or not target.paper_type) and source.paper_type:
            target.paper_type = source.paper_type

        if (overwrite or not target.oa_status) and source.oa_status:
            target.oa_status = source.oa_status

        if (overwrite or not target.raw_json) and source.raw_json:
            target.raw_json = source.raw_json

        # Update timestamps
        target.updated_at = datetime.now()

    def __str__(self) -> str:
        return f"<FetcherHandler: {self.name}>"
