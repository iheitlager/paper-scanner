"""
Base fetcher handler - abstract interface for API-specific implementations.

Each API (Crossref, OpenAlex, etc.) implements this interface to provide
consistent metadata extraction and translation to Paper model.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import hashlib
import json
import logging

from paper_scanner.core.models import Paper

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

    def fetch_and_parse(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch metadata and parse into Paper model.

        Checks cache first, then API, storing result in cache.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        # Check cache
        cache_file = self._get_cache_file(doi)
        if cache_file.exists():
            api_data = self._load_from_cache(cache_file)
            paper = self._translate_to_paper(doi, api_data) if api_data else None
            return paper, True

        # Fetch from API
        api_data = self._fetch_from_api(doi)
        if api_data is None:
            return None, False

        # Save to cache
        self._save_to_cache(cache_file, api_data)

        # Translate to Paper
        paper = self._translate_to_paper(doi, api_data)
        return paper, False

    def _translate_to_paper(self, doi: str, api_data: Dict[str, Any]) -> Paper:
        """
        Translate API response into Paper model.

        Args:
            doi: The DOI (normalized)
            api_data: Raw API response

        Returns:
            Paper model instance
        """
        from paper_scanner.core.models import Author, Discovery
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
        Generate cite key from author and year.

        Strategy:
        1. {first_author_family_name}_{year} (e.g., "smith_2020")
        2. If no author: {first_word_of_title}_{year}
        3. If no year: Use DOI slug
        4. If nothing: Use random UUID
        """
        if authors and year:
            family_name = authors[0].family_name.lower().replace(" ", "_")
            return f"{family_name}_{year}"

        # Fallback: will be regenerated by application
        return f"doi_{doi.replace('/', '_').replace('.', '_')[:30]}"

    def _get_cache_file(self, doi: str) -> Path:
        """Get cache file path for DOI (MD5 hash of lowercase DOI)."""
        # Normalize DOI
        normalized = doi.lower().strip()
        if normalized.startswith("doi:"):
            normalized = normalized[4:]
        if normalized.startswith("https://doi.org/"):
            normalized = normalized[16:]

        # Hash it
        md5_hash = hashlib.md5(normalized.encode()).hexdigest()
        return self.cache_dir / f"{md5_hash}.json"

    def _load_from_cache(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        """Load API response from cache."""
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_file}: {e}")
            return None

    def _save_to_cache(self, cache_file: Path, api_data: Dict[str, Any]) -> None:
        """Save API response to cache."""
        try:
            with open(cache_file, "w") as f:
                json.dump(api_data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_file}: {e}")
