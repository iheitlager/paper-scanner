"""
Base fetcher handler - abstract interface for API-specific implementations.

Each API (Crossref, OpenAlex, etc.) implements this interface to provide
consistent metadata extraction and translation to Paper model.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime

from paper_scanner.core.models import Paper, Citation
from paper_scanner.tools.cache import JSONFileCache
from paper_scanner.core.doi import DOI

class BaseFetcherHandler(ABC):
    """
    Abstract base for API-specific metadata fetchers.

    Subclasses implement API calls and field translation logic.
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize handler with cache directory.

        Args:
            cache_dir: Directory for caching API responses (e.g., ~/.cache/paper-scanner/crossref/)
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = JSONFileCache(self.cache_dir)

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
            return f"doi_{doi.replace('/', '_')}"
        return "unknown_cite_key"


    def fetch_paper(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch Paper from doi.

        Checks cache first, then API, storing result in cache.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        # Check cache
        api_data = self._cache.get(doi)
        if api_data is not None:
            paper = self._translate_to_paper(doi, api_data)
            return paper, True

        api_data = self._fetch_from_api(doi)
        if api_data is None:
            return None, False

        self._cache.set(doi, api_data)

        paper = self._translate_to_paper(doi, api_data)
        return paper, False

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
        # Check cache - same key as fetch_paper
        api_data = self._cache.get(doi)

        if api_data is not None:
            citations = self._extract_citations(api_data)
            return citations, True

        # Fetch full API data (includes citations)
        api_data = self._fetch_from_api(doi)
        if api_data is None:
            return [], False

        # Cache the full API response
        self._cache.set(doi, api_data)
        citations = self._extract_citations(api_data)

        return citations, False

    def _translate_to_paper(self, doi: str, api_data: Dict[str, Any]) -> Paper:
        """
        Translate API response into Paper model.

        Args:
            doi: The DOI (normalized)
            api_data: Raw API response

        Returns:
            Paper model instance
        """
        from paper_scanner.core.models import Discovery
        from paper_scanner.core.enum import DiscoveryMethod

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
        publisher = api_data.get("publisher")
        volume = api_data.get("volume")
        number = api_data.get("issue")
        pages = api_data.get("pages")
        language = api_data.get("language", "en")
        publication_date = api_data.get("publication_date")

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


    def __str__(self) -> str:
        return f"<FetcherHandler: {self.name}>"
