"""
JSON file caching for API responses, particularly Crossref API.

This module provides a simple file-based caching mechanism for storing
API responses keyed by content hash (e.g., DOI).

Supports 404 caching to reduce API calls for non-existent entries.
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

from paper_scanner.core import doi
from paper_scanner.core.exceptions import PaperScannerError

# 404 Cache Marker - indicates an item was not found at the API
NOT_FOUND_MARKER = {"ITEM": "404 - NOT FOUND", "LAST-CHECKED": None, "URL": None}


def create_404_marker(key: str, url: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a 404 marker for caching not-found responses.

    Args:
        url: Optional URL that was checked and returned 404

    Returns:
        Dictionary with 404 marker
    """
    return {
        "ITEM": "404 - NOT FOUND",
        "LAST-CHECKED": datetime.now().isoformat(),
        "URL": url,
        "KEY": key,
    }


def is_404_marker(data: Any) -> bool:
    """
    Check if cached data is a 404 marker.

    Args:
        data: Cached data to check

    Returns:
        True if data is a 404 marker, False otherwise
    """
    return (
        isinstance(data, dict)
        and data.get("ITEM") == "404 - NOT FOUND"
        and "LAST-CHECKED" in data
        and "URL" in data
        and "KEY" in data
    )


class CacheError(PaperScannerError):
    """Custom exception for cache-related errors."""
    pass

class JSONFileCache:
    """
    Simple JSON file-based cache for API responses.

    Uses MD5 hash of the key (e.g., DOI) to create cache file names,
    avoiding filesystem restrictions on special characters.
    """

    def __init__(self, cache_dir: Optional[Path] = None, default_ttl: Optional[Union[int, timedelta]] = 30):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files.
                      Defaults to $XDG_CACHE_HOME/paper-scanner/api/ if not provided.
            default_ttl: Default time-to-live for cache entries in days.
                         Can be int (days) or timedelta. Defaults to 30 days.
        """
        from paper_scanner.core.paths import get_json_cache_dir
        cache_dir = get_json_cache_dir(cache_dir)

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = timedelta(days=default_ttl) if isinstance(default_ttl, int) else default_ttl


    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a key.

        Uses MD5 hash of the normalized key to avoid filesystem restrictions
        on special characters (e.g., slashes in DOIs).

        Args:
            key: The key to cache (e.g., DOI)

        Returns:
            Path object for the cache file
        """
        key_hash = doi.DOI(key).md5
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str, ttl: Optional[Union[int, timedelta]] = -1) -> Optional[Dict[str, Any]]:
        """
        Load cached value if it exists and hasn't exceeded its time-to-live.

        Args:
            key: The key to look up (e.g., DOI)
            ttl: Time-to-live (int = days, timedelta = custom duration, 0 = never expire, None = use default)

        Returns:
            Cached JSON data if found and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        # Convert ttl to timedelta
        if ttl == -1: # Never expires
            ttl_delta = None
        elif ttl is None: # Take default
            ttl_delta = self.default_ttl
        else: # take what we got or transform into days
            ttl_delta = timedelta(days=ttl) if isinstance(ttl, int) else ttl

        # Check expiration only if ttl_delta is positive
        if ttl_delta and ttl_delta.total_seconds() > 0:
            file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if file_age > ttl_delta:
                cache_path.unlink()
                return None

        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise CacheError(f"Error loading cache for {key}: {e}")

    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """
        Save value to cache.

        Args:
            key: The key to cache (e.g., DOI)
            data: The JSON-serializable data to cache

        Returns:
            True if successful, False otherwise
        """
        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            return True
        except Exception as e:
            raise CacheError(f"Error saving cache for {key}: {e}")

    def clear(self) -> int:
        """
        Clear all cache files.

        Returns:
            Number of files deleted
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
        except Exception as e:
            raise CacheError(f"Error clearing cache: {e}")

        return count


class PDFCache:
    """
    File-based cache for PDF files.

    Stores PDFs using MD5 hash of the DOI as the filename,
    allowing efficient retrieval and management of cached PDFs.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize PDF cache.

        Args:
            cache_dir: Directory to store cached PDFs.
                      Defaults to $XDG_CACHE_HOME/paper-scanner/pdf/ if not provided.
        """
        from paper_scanner.core.paths import get_pdf_cache_dir
        cache_dir = get_pdf_cache_dir(cache_dir)

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a PDF key.

        Uses MD5 hash of the normalized key (DOI) to create cache filenames.

        Args:
            key: The key to cache (e.g., DOI)

        Returns:
            Path object for the cached PDF file
        """
        key_hash = doi.DOI(key).md5
        return self.cache_dir / f"{key_hash}.pdf"

    def get(self, key: str) -> Optional[Path]:
        """
        Get cached PDF path if it exists and is readable.

        Args:
            key: The key to look up (e.g., DOI)

        Returns:
            Path to the cached PDF if found and readable, None otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        if not cache_path.is_file():
            return None

        try:
            # Validate that file is readable
            with open(cache_path, 'rb') as f:
                f.read(1)  # Try to read at least 1 byte
            return cache_path
        except Exception:
            return None

    def set(self, key: str, tmp_path: Path, move: bool = True) -> Optional[Path]:
        """
        Move a PDF from temporary location to cache.

        Args:
            key: The key to cache (e.g., DOI)
            tmp_path: Path to the temporary PDF file

        Returns:
            Path to the cached PDF if successful, None otherwise
        """
        tmp_path = Path(tmp_path)

        if not tmp_path.exists():
            raise CacheError(f"Temporary file does not exist: {tmp_path}")

        if not tmp_path.is_file():
            raise CacheError(f"Temporary path is not a file: {tmp_path}")

        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            return cache_path

        try:
            if move:
                shutil.move(str(tmp_path), str(cache_path))
            else:
                shutil.copy2(str(tmp_path), str(cache_path))
            return cache_path
        except Exception as e:
            raise CacheError(f"Error moving PDF to cache for {key}: {e}")

    def clear(self) -> int:
        """
        Clear all cached PDF files.

        Returns:
            Number of files deleted
        """
        count = 0
        try:
            for cache_file in self.cache_dir.glob("*.pdf"):
                cache_file.unlink()
                count += 1
        except Exception as e:
            raise CacheError(f"Error clearing PDF cache: {e}")

        return count
