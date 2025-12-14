"""
Base fetcher handler - abstract interface for API-specific implementations.

Each API (Crossref, OpenAlex, etc.) implements this interface to provide
consistent metadata extraction and translation to Paper model.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
import logging

from paper_scanner.core.models import Paper, Citation
from paper_scanner.tools.cache import JSONFileCache

logger = logging.getLogger(__name__)


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


    def fetch_metadata(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch metadata and parse into Paper model.

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

        Reuses the same cache as fetch_metadata since citations are
        part of the API response (e.g., Crossref includes references in work record).

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (List[Citation] models, cache_hit: bool)
        """
        # Check cache - same key as fetch_metadata
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

    def fetch_and_parse(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch metadata and parse into Paper model.

        Deprecated: Use fetch_metadata() instead.
        Checks cache first, then API, storing result in cache.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        return self.fetch_metadata(doi)

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
        title = api_data.get("title", "")
        if isinstance(title, list):
            title = title[0] if title else ""

        abstract = self._extract_abstract(api_data)
        authors = self._extract_authors(api_data)
        keywords = self._extract_keywords(api_data)
        topics = self._extract_topics(api_data)
        paper_type = self._extract_paper_type(api_data)
        oa_status = self._extract_oa_status(api_data)
        source_key = self._extract_source_key(api_data)

        # Extract other fields (implemented in subclasses or generically)
        year = api_data.get("year")
        journal = api_data.get("journal")
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
        import hashlib
        import uuid
        
        if doi:
            # Hash the normalized DOI for reproducibility
            hash_input = doi.lower().strip()
            return "doi_" + hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        # Fallback: random UUID if no DOI
        return str(uuid.uuid4())[:8]

    def __str__(self) -> str:
        return f"<FetcherHandler: {self.name}>"
