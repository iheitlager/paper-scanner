"""
CORE API handler - PDF fetcher for research papers.

Fetches PDF downloads from CORE API (core.ac.uk).
API docs: https://core.ac.uk/documentation
"""

from pathlib import Path
from typing import Optional, Dict, Any
import sys
import os

import requests
from rich.console import Console

from paper_scanner.core.models import PDFInfo
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.core.doi import DOI

console = Console(file=sys.stderr)

# CORE API endpoints
CORE_API_URL = "https://api.core.ac.uk/v3/search/works"

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 10


class COREHandler(BaseFetcherHandler):
    """Fetcher for CORE API PDF downloads."""

    def __init__(self, cache_dir: Path, debug: bool = False, verbose: bool = False, api_key: Optional[str] = None):
        """
        Initialize CORE handler.
        
        Args:
            cache_dir: Cache directory for API responses
            debug: Enable debug output
            verbose: Enable verbose output
            api_key: CORE API key (optional, some endpoints don't require it)
        """
        super().__init__(cache_dir, debug=debug, verbose=verbose)
        self.api_key = api_key or os.getenv("CORE_API_KEY")
        self.session = requests.Session()

    @property
    def name(self) -> str:
        """Fetcher name."""
        return "core"

    def _fetch_from_api(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata from CORE API using DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            API response data, or None if not found
        """
        if not self.api_key:
            raise ValueError("CORE API key is required for metadata fetching.")

        try:
            # Normalize DOI
            normalized = DOI(doi).stem

            # Search works by DOI via CORE API
            # CORE works endpoint: /works/search
            params = {
                "q": f"doi:{normalized}",
                "limit": 1,
                "offset": 0,
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = self.session.get(CORE_API_URL, params=params, timeout=REQUEST_TIMEOUT, headers=headers)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # CORE returns results in 'results' array
            if data.get("status") == "OK" and data.get("results"):
                # Return the first result
                return data["results"][0]

            return None

        except requests.exceptions.RequestException as e:
            if self.debug:
                console.print(f"[yellow]CORE API error: {e}[/yellow]")
            return None

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """CORE doesn't provide abstracts in metadata fetch."""
        return None

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """CORE doesn't provide author data in metadata fetch."""
        return []

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """CORE doesn't provide keywords in metadata fetch."""
        return []

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """CORE doesn't provide topics in metadata fetch."""
        return []

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """CORE doesn't provide paper type in metadata fetch."""
        return None

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """CORE doesn't provide year in metadata fetch."""
        return None

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """CORE doesn't provide journal in metadata fetch."""
        return None

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """CORE doesn't provide OA status in metadata fetch."""
        return None

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract CORE ID from API response."""
        return api_data.get("id")

    def _extract_citations(self, api_data: Dict[str, Any]) -> list:
        """CORE doesn't provide citations in metadata fetch."""
        return []

    def _find_download_url(self, api_data: Dict[str, Any]) -> Optional[str]:
        """
        Find downloadable PDF URL from CORE metadata.

        CORE provides direct download links in the API response.

        Args:
            api_data: API response data

        Returns:
            Download URL if available, None otherwise
        """
        # CORE provides 'downloadUrl' in the response
        download_url = api_data.get("downloadUrl")
        if download_url and isinstance(download_url, str):
            return download_url

        # Alternative: 'fullTextUrl' might contain download URL
        full_text_url = api_data.get("fullTextUrl")
        if full_text_url and isinstance(full_text_url, str):
            return full_text_url

        # Alternative: 'sourceFulltextUrls' might contain download URLs
        source_fulltext_urls = api_data.get("sourceFulltextUrls")
        if source_fulltext_urls and isinstance(source_fulltext_urls, str):
            return source_fulltext_urls

        # Try 'links' array (some versions)
        links = api_data.get("links", [])
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    url = link.get("url")
                    link_type = link.get("type", "").lower()
                    # Look for PDF or download links
                    if url and (link_type in ["pdf", "download"]):
                        return url

        return None
