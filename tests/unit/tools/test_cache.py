#!/usr/bin/env python3
"""
Unit tests for JSONFileCache module.

Tests the file-based JSON caching mechanism used for API responses.
"""

import json
import tempfile
from pathlib import Path

import pytest

from paper_scanner.tools.cache import JSONFileCache


class TestJSONFileCache:
    """Test suite for JSONFileCache class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance with temporary directory."""
        return JSONFileCache(temp_cache_dir)

    def test_init_creates_directory(self, temp_cache_dir):
        """Test that __init__ creates the cache directory."""
        new_dir = temp_cache_dir / "new_cache"
        assert not new_dir.exists()

        cache = JSONFileCache(new_dir)

        assert new_dir.exists()
        assert cache.cache_dir == new_dir

    def test_init_default_directory(self):
        """Test that __init__ uses default ~/.cache_files if not specified."""
        cache = JSONFileCache()
        expected_dir = Path.home() / ".cache_files"

        assert cache.cache_dir == expected_dir

    def test_expanduser_in_path(self, temp_cache_dir):
        """Test that paths with ~ are expanded correctly."""
        # We can't easily test ~ expansion, but we can test that it doesn't error
        cache = JSONFileCache(str(temp_cache_dir).replace(str(Path.home()), "~"))
        assert cache.cache_dir == temp_cache_dir

    def test_set_and_get_basic(self, cache):
        """Test basic set and get operations."""
        key = "test_doi_1"
        data = {"title": "Test Paper", "year": 2024}

        # Initially should return None
        assert cache.get(key) is None

        # Set the data
        result = cache.set(key, data)
        assert result is True

        # Get the data back
        retrieved = cache.get(key)
        assert retrieved == data

    def test_set_returns_false_on_error(self, cache):
        """Test that set returns False when there's an error."""
        # Make cache_dir read-only to cause a write error
        cache.cache_dir.chmod(0o444)

        try:
            result = cache.set("test_key", {"data": "test"})
            assert result is False
        finally:
            # Restore permissions for cleanup
            cache.cache_dir.chmod(0o755)

    def test_get_returns_none_on_missing_key(self, cache):
        """Test that get returns None for non-existent keys."""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_get_returns_none_on_corrupt_cache(self, cache):
        """Test that get returns None if cache file is corrupt."""
        key = "test_key"
        cache_path = cache._get_cache_path(key)

        # Write invalid JSON
        with open(cache_path, 'w') as f:
            f.write("{invalid json}")

        result = cache.get(key)
        assert result is None

    def test_cache_with_complex_data(self, cache):
        """Test caching complex nested data structures."""
        key = "complex_doi"
        data = {
            "title": "Complex Paper",
            "authors": [
                {"name": "John Doe", "email": "john@example.com"},
                {"name": "Jane Smith", "email": "jane@example.com"}
            ],
            "metadata": {
                "year": 2024,
                "venue": "Test Conference",
                "tags": ["ai", "ml", "nlp"]
            },
            "references": [
                {"doi": "10.1234/test1", "title": "Ref 1"},
                {"doi": "10.5678/test2", "title": "Ref 2"}
            ]
        }

        cache.set(key, data)
        retrieved = cache.get(key)

        assert retrieved == data
        assert retrieved["authors"][0]["name"] == "John Doe"
        assert "ai" in retrieved["metadata"]["tags"]

    def test_cache_with_special_characters_in_key(self, cache):
        """Test that keys with special characters are handled correctly."""
        # DOI with special characters
        key = "10.1038/s41586-020-2012-7"
        data = {"doi": key, "title": "Test"}

        cache.set(key, data)
        retrieved = cache.get(key)

        assert retrieved == data

    def test_multiple_keys_dont_collide(self, cache):
        """Test that different keys create different cache files."""
        keys = ["doi1", "doi2", "doi3"]
        data_list = [
            {"title": "Paper 1"},
            {"title": "Paper 2"},
            {"title": "Paper 3"}
        ]

        # Set all keys
        for key, data in zip(keys, data_list):
            cache.set(key, data)

        # Verify all keys retrieve correct data
        for key, expected_data in zip(keys, data_list):
            retrieved = cache.get(key)
            assert retrieved == expected_data

    def test_overwrite_existing_key(self, cache):
        """Test that setting an existing key overwrites the data."""
        key = "test_key"
        data1 = {"version": 1}
        data2 = {"version": 2}

        cache.set(key, data1)
        assert cache.get(key) == data1

        cache.set(key, data2)
        assert cache.get(key) == data2

    def test_clear_removes_all_cache(self, cache):
        """Test that clear removes all cache files."""
        # Add some cache entries
        for i in range(5):
            cache.set(f"key_{i}", {"data": i})

        # Verify files exist
        cache_files = list(cache.cache_dir.glob("*.json"))
        assert len(cache_files) == 5

        # Clear cache
        removed_count = cache.clear()
        assert removed_count == 5

        # Verify files are gone
        cache_files = list(cache.cache_dir.glob("*.json"))
        assert len(cache_files) == 0

    def test_clear_empty_cache(self, cache):
        """Test that clear on empty cache returns 0."""
        removed_count = cache.clear()
        assert removed_count == 0

    def test_get_cache_path_consistency(self, cache):
        """Test that same key always produces same cache path."""
        key = "test_doi"
        path1 = cache._get_cache_path(key)
        path2 = cache._get_cache_path(key)

        assert path1 == path2

    def test_get_cache_path_uses_md5(self, cache):
        """Test that cache path uses MD5 hash."""
        key = "10.1038/test-doi"
        path = cache._get_cache_path(key)

        # Should be in cache_dir with .json extension
        assert path.parent == cache.cache_dir
        assert path.suffix == ".json"
        # Should be a hash (32 character hex string)
        assert len(path.stem) == 32
        assert all(c in "0123456789abcdef" for c in path.stem)

    def test_cache_with_empty_dict(self, cache):
        """Test caching empty dictionary."""
        key = "empty_dict"
        data = {}

        cache.set(key, data)
        retrieved = cache.get(key)

        assert retrieved == {}

    def test_cache_with_none_values(self, cache):
        """Test caching data with None values."""
        key = "with_none"
        data = {"field1": "value", "field2": None, "field3": [1, None, 3]}

        cache.set(key, data)
        retrieved = cache.get(key)

        assert retrieved == data
        assert retrieved["field2"] is None

    def test_cache_preserves_json_types(self, cache):
        """Test that JSON types are preserved through cache."""
        key = "type_preservation"
        data = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }

        cache.set(key, data)
        retrieved = cache.get(key)

        assert isinstance(retrieved["integer"], int)
        assert isinstance(retrieved["float"], float)
        assert isinstance(retrieved["boolean"], bool)
        assert retrieved["null"] is None
        assert isinstance(retrieved["array"], list)
        assert isinstance(retrieved["object"], dict)

    def test_cache_file_permissions(self, cache):
        """Test that cache files are created with appropriate permissions."""
        key = "test_permissions"
        data = {"test": "data"}

        cache.set(key, data)
        cache_path = cache._get_cache_path(key)

        # File should be readable/writable by owner
        assert cache_path.stat().st_mode & 0o600

    def test_concurrent_keys_same_cache_dir(self, cache):
        """Test that multiple keys can coexist in same cache directory."""
        keys = [f"doi_{i}" for i in range(10)]

        for i, key in enumerate(keys):
            cache.set(key, {"index": i})

        for i, key in enumerate(keys):
            assert cache.get(key)["index"] == i

    def test_clear_returns_count(self, cache):
        """Test that clear returns accurate count of removed files."""
        # Add files
        for i in range(3):
            cache.set(f"key_{i}", {"data": i})

        # Clear should return 3
        count = cache.clear()
        assert count == 3

        # Add more files and clear
        for i in range(5):
            cache.set(f"key_{i}", {"data": i})

        count = cache.clear()
        assert count == 5

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
