"""
JSON file caching for API responses, particularly Crossref API.

This module provides a simple file-based caching mechanism for storing
API responses keyed by content hash (e.g., DOI).
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class JSONFileCache:
    """
    Simple JSON file-based cache for API responses.
    
    Uses MD5 hash of the key (e.g., DOI) to create cache file names,
    avoiding filesystem restrictions on special characters.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory to store cache files.
                      Defaults to ~/.cache_files if not provided.
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache_files"
        
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """
        Get cache file path for a key.
        
        Uses MD5 hash of the key to avoid filesystem restrictions
        on special characters (e.g., slashes in DOIs).
        
        Args:
            key: The key to cache (e.g., DOI)
            
        Returns:
            Path object for the cache file
        """
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Load cached value from file.
        
        Args:
            key: The key to look up (e.g., DOI)
            
        Returns:
            Cached JSON data if found, None otherwise
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Error loading cache for {key}: {e}")
            return None
    
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
            logger.debug(f"Error saving cache for {key}: {e}")
            return False
    
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
            logger.warning(f"Error clearing cache: {e}")
        
        return count
