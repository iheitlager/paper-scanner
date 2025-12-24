"""
Comprehensive unit tests for paper_scanner.tools.cache module.

Tests the JSONFileCache class including:
- Cache initialization and directory creation
- Getting/setting cache entries
- Cache key hashing
- Cache clearing
- Error handling
- Edge cases
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_scanner.core import doi
from paper_scanner.core.cache import CacheError, JSONFileCache


class TestCacheInitialization:
    """Tests for cache initialization and setup."""

    def test_cache_init_with_custom_dir(self, tmp_path):
        """Test cache initialization with custom directory."""
        cache_dir = tmp_path / "custom_cache"
        cache = JSONFileCache(cache_dir=cache_dir)

        assert cache.cache_dir == cache_dir
        assert cache_dir.exists()

    def test_cache_init_creates_directory(self, tmp_path):
        """Test that cache initialization creates directory if it doesn't exist."""
        cache_dir = tmp_path / "nested" / "cache" / "dir"
        cache = JSONFileCache(cache_dir=cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_cache_init_with_none_uses_default(self, tmp_path):
        """Test that None cache_dir uses default ~/.cache_files."""
        with patch.object(Path, 'home', return_value=tmp_path):
            cache = JSONFileCache(cache_dir=None)
            expected = tmp_path / ".cache_files"
            assert cache.cache_dir == expected
            assert expected.exists()

    def test_cache_init_expands_user_path(self, tmp_path):
        """Test that ~ is expanded in cache_dir path."""
        # Create a test path with ~ notation
        test_cache_path = str(tmp_path / ".my_cache")
        cache = JSONFileCache(cache_dir=test_cache_path)
        # Verify the path exists and is properly set
        assert cache.cache_dir.exists()
        assert ".my_cache" in str(cache.cache_dir)

    def test_cache_init_existing_directory(self, tmp_path):
        """Test cache initialization with existing directory."""
        cache = JSONFileCache(cache_dir=tmp_path)
        cache2 = JSONFileCache(cache_dir=tmp_path)

        assert cache.cache_dir == cache2.cache_dir
        assert tmp_path.exists()


class TestCacheKeyPath:
    """Tests for cache key to path conversion."""

    def test_get_cache_path_returns_json_file(self, tmp_path):
        """Test that _get_cache_path returns a .json file."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        path = cache._get_cache_path(key)

        assert path.suffix == ".json"
        assert path.parent == tmp_path

    def test_get_cache_path_consistent_for_same_key(self, tmp_path):
        """Test that same key always generates same cache path."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        path1 = cache._get_cache_path(key)
        path2 = cache._get_cache_path(key)

        assert path1 == path2

    def test_get_cache_path_different_for_different_keys(self, tmp_path):
        """Test that different keys generate different cache paths."""
        cache = JSONFileCache(cache_dir=tmp_path)

        path1 = cache._get_cache_path("10.1234/doi1")
        path2 = cache._get_cache_path("10.1234/doi2")

        assert path1 != path2

    def test_get_cache_path_uses_doi_md5_hash(self, tmp_path):
        """Test that cache path uses DOI MD5 hash."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        with patch.object(doi.DOI, 'md5', "testhash123"):
            path = cache._get_cache_path(key)
            assert "testhash123" in path.name

    def test_get_cache_path_handles_special_characters(self, tmp_path):
        """Test that paths with special characters are handled correctly."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # DOI with special characters
        keys = [
            "10.1234/test.doi",
            "10.1234/test/doi/with/slashes",
            "10.1234/test-doi-with-dashes",
            "10.1234/test_doi_with_underscores",
        ]

        paths = [cache._get_cache_path(key) for key in keys]

        # All paths should be valid and different
        assert len(paths) == len(set(paths))
        for path in paths:
            assert path.suffix == ".json"


class TestCacheGet:
    """Tests for cache get functionality."""

    def test_get_returns_none_for_missing_key(self, tmp_path):
        """Test that get returns None when key doesn't exist."""
        cache = JSONFileCache(cache_dir=tmp_path)
        # Use a valid DOI format (10.prefix/suffix)
        result = cache.get("10.9999/nonexistent")

        assert result is None

    def test_get_returns_cached_data(self, tmp_path):
        """Test that get returns previously cached data."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test Paper", "authors": ["Author 1"]}

        # Manually save data
        cache.set(key, test_data)

        # Get and verify
        result = cache.get(key)
        assert result == test_data

    def test_get_returns_complex_nested_data(self, tmp_path):
        """Test that get returns complex nested JSON structures."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {
            "metadata": {
                "title": "Test",
                "nested": {
                    "deep": {
                        "value": [1, 2, 3],
                        "bool": True,
                        "null": None,
                    }
                }
            },
            "list": [1, 2, 3],
            "number": 42.5,
        }

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data

    def test_get_raises_error_on_corrupted_json(self, tmp_path):
        """Test that get raises CacheError when JSON is corrupted."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # Create corrupted cache file
        cache_path = cache._get_cache_path(key)
        cache_path.write_text("{ invalid json }")

        with pytest.raises(CacheError) as exc_info:
            cache.get(key)

        assert "Error loading cache" in str(exc_info.value)
        assert key in str(exc_info.value)

    def test_get_raises_error_on_file_read_error(self, tmp_path):
        """Test that get raises CacheError on file read errors."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache.set(key, {"data": "test"})

        with patch("builtins.open", side_effect=IOError("Read error")):
            with pytest.raises(CacheError) as exc_info:
                cache.get(key)

            assert "Error loading cache" in str(exc_info.value)

    def test_get_handles_permission_error(self, tmp_path):
        """Test that get handles permission errors gracefully."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache.set(key, {"data": "test"})
        cache_path = cache._get_cache_path(key)

        # Make file unreadable
        cache_path.chmod(0o000)

        try:
            with pytest.raises(CacheError):
                cache.get(key)
        finally:
            # Restore permissions for cleanup
            cache_path.chmod(0o644)

    def test_get_empty_json_object(self, tmp_path):
        """Test that get correctly handles empty JSON objects."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache.set(key, {})
        result = cache.get(key)

        assert result == {}

    def test_get_empty_json_arrays(self, tmp_path):
        """Test that get correctly handles structures with empty arrays."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"items": [], "count": 0}

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data


class TestCacheSet:
    """Tests for cache set functionality."""

    def test_set_creates_cache_file(self, tmp_path):
        """Test that set creates a cache file."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test"}

        result = cache.set(key, test_data)

        assert result is True
        cache_path = cache._get_cache_path(key)
        assert cache_path.exists()

    def test_set_returns_true_on_success(self, tmp_path):
        """Test that set returns True on successful write."""
        cache = JSONFileCache(cache_dir=tmp_path)
        result = cache.set("10.1234/test.doi", {"data": "test"})

        assert result is True

    def test_set_saves_valid_json(self, tmp_path):
        """Test that set saves valid JSON that can be parsed."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {"title": "Test", "year": 2023}

        cache.set(key, test_data)
        cache_path = cache._get_cache_path(key)

        # Verify file contains valid JSON
        with open(cache_path, 'r') as f:
            loaded = json.load(f)

        assert loaded == test_data

    def test_set_overwrites_existing_cache(self, tmp_path):
        """Test that set overwrites existing cache entry."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        cache.set(key, {"version": 1})
        cache.set(key, {"version": 2})

        result = cache.get(key)
        assert result == {"version": 2}

    def test_set_handles_complex_nested_structures(self, tmp_path):
        """Test that set correctly handles complex nested data."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {
            "metadata": {
                "nested": {
                    "deep": {
                        "values": [1, 2, 3],
                        "flags": {"a": True, "b": False},
                    }
                }
            },
            "numbers": [1.5, 2.5, 3.5],
            "strings": ["a", "b", "c"],
            "null_value": None,
        }

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data

    def test_set_raises_error_on_write_failure(self, tmp_path):
        """Test that set raises CacheError on write failure."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        with patch("builtins.open", side_effect=IOError("Write error")):
            with pytest.raises(CacheError) as exc_info:
                cache.set(key, {"data": "test"})

            assert "Error saving cache" in str(exc_info.value)

    def test_set_handles_permission_error(self, tmp_path):
        """Test that set handles permission errors gracefully."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Make cache directory read-only
        tmp_path.chmod(0o555)

        try:
            with pytest.raises(CacheError):
                cache.set("10.1234/test.doi", {"data": "test"})
        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(0o755)

    def test_set_empty_object(self, tmp_path):
        """Test that set correctly saves empty objects."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        result = cache.set(key, {})
        assert result is True

        retrieved = cache.get(key)
        assert retrieved == {}

    def test_set_preserves_data_types(self, tmp_path):
        """Test that set preserves different JSON data types."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        test_data = {
            "string": "value",
            "int": 42,
            "float": 3.14,
            "bool_true": True,
            "bool_false": False,
            "null": None,
            "array": [1, "two", 3.0, None],
        }

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data
        assert isinstance(result["int"], int)
        assert isinstance(result["float"], float)
        assert isinstance(result["bool_true"], bool)
        assert isinstance(result["bool_false"], bool)
        assert result["null"] is None


class TestCacheClear:
    """Tests for cache clearing functionality."""

    def test_clear_removes_all_cache_files(self, tmp_path):
        """Test that clear removes all cache files."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Create multiple cache entries
        for i in range(5):
            key = f"10.1234/test.doi.{i}"
            cache.set(key, {"id": i})

        # Verify files exist
        assert len(list(tmp_path.glob("*.json"))) == 5

        # Clear cache
        count = cache.clear()

        assert count == 5
        assert len(list(tmp_path.glob("*.json"))) == 0

    def test_clear_returns_count(self, tmp_path):
        """Test that clear returns the correct count of deleted files."""
        cache = JSONFileCache(cache_dir=tmp_path)

        cache.set("10.1234/test1", {"data": 1})
        cache.set("10.1234/test2", {"data": 2})
        cache.set("10.1234/test3", {"data": 3})

        count = cache.clear()
        assert count == 3

    def test_clear_empty_cache_returns_zero(self, tmp_path):
        """Test that clear on empty cache returns 0."""
        cache = JSONFileCache(cache_dir=tmp_path)

        count = cache.clear()
        assert count == 0

    def test_clear_ignores_non_json_files(self, tmp_path):
        """Test that clear only removes JSON files."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Create cache entries
        cache.set("10.1234/test1", {"data": 1})
        cache.set("10.1234/test2", {"data": 2})

        # Create a non-JSON file
        non_json = tmp_path / "readme.txt"
        non_json.write_text("Not a cache file")

        # Clear cache
        count = cache.clear()

        assert count == 2
        assert non_json.exists()

    def test_clear_handles_errors_gracefully(self, tmp_path):
        """Test that clear handles file deletion errors."""
        cache = JSONFileCache(cache_dir=tmp_path)
        cache.set("10.1234/test", {"data": 1})

        # Mock unlink to raise an error
        with patch.object(Path, 'unlink', side_effect=OSError("Delete error")):
            with pytest.raises(CacheError) as exc_info:
                cache.clear()

            assert "Error clearing cache" in str(exc_info.value)

    def test_clear_removes_multiple_files_despite_partial_failure(self, tmp_path):
        """Test clear behavior when some files fail to delete."""
        cache = JSONFileCache(cache_dir=tmp_path)

        cache.set("10.1234/test1", {"data": 1})
        cache.set("10.1234/test2", {"data": 2})

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 2


class TestCacheIntegration:
    """Integration tests for cache functionality."""

    def test_cache_set_get_roundtrip(self, tmp_path):
        """Test complete set/get roundtrip with realistic data."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1016/j.test.2023.001"

        original_data = {
            "DOI": key,
            "title": "Test Paper",
            "authors": [
                {"name": "Author One", "affiliation": "University A"},
                {"name": "Author Two", "affiliation": "University B"},
            ],
            "year": 2023,
            "abstract": "This is a test abstract.",
            "keywords": ["AI", "ML", "Testing"],
        }

        # Set
        assert cache.set(key, original_data) is True

        # Get
        retrieved_data = cache.get(key)

        assert retrieved_data == original_data

    def test_cache_multiple_independent_entries(self, tmp_path):
        """Test cache with multiple independent entries."""
        cache = JSONFileCache(cache_dir=tmp_path)

        entries = {
            "10.1234/doi1": {"paper": 1, "title": "Paper 1"},
            "10.1234/doi2": {"paper": 2, "title": "Paper 2"},
            "10.1234/doi3": {"paper": 3, "title": "Paper 3"},
        }

        # Set all entries
        for key, data in entries.items():
            cache.set(key, data)

        # Verify all entries
        for key, expected_data in entries.items():
            retrieved = cache.get(key)
            assert retrieved == expected_data

    def test_cache_persistence_across_instances(self, tmp_path):
        """Test that cache persists across different cache instances."""
        key = "10.1234/test.doi"
        test_data = {"persistent": True}

        # First instance sets data
        cache1 = JSONFileCache(cache_dir=tmp_path)
        cache1.set(key, test_data)

        # Second instance retrieves data
        cache2 = JSONFileCache(cache_dir=tmp_path)
        retrieved = cache2.get(key)

        assert retrieved == test_data

    def test_cache_workflow(self, tmp_path):
        """Test a complete cache workflow."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Set multiple entries with valid DOI format
        for i in range(10):
            # Use valid DOI format: 10.prefix/suffix
            cache.set(f"10.5555/article{i}", {"id": i, "data": f"item_{i}"})

        # Verify all entries exist
        for i in range(10):
            result = cache.get(f"10.5555/article{i}")
            assert result is not None
            assert result["id"] == i

        # Update one entry
        cache.set("10.5555/article5", {"id": 5, "data": "updated_item_5"})
        assert cache.get("10.5555/article5")["data"] == "updated_item_5"

        # Clear all
        deleted = cache.clear()
        assert deleted == 10

        # Verify all cleared
        for i in range(10):
            result = cache.get(f"10.5555/article{i}")
            assert result is None


class TestCacheErrorHandling:
    """Tests for error handling and edge cases."""

    def test_cache_error_exception_message(self):
        """Test that CacheError properly captures error messages."""
        msg = "Test error message"
        error = CacheError(msg)

        assert str(error) == msg

    def test_cache_with_invalid_doi_raises_error(self, tmp_path):
        """Test that invalid DOI format raises ValueError."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Empty DOI should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            cache.set("", {"data": "test"})

        assert "empty" in str(exc_info.value).lower()

    def test_cache_with_special_characters_in_data(self, tmp_path):
        """Test cache with special characters in data."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        test_data = {
            "title": "Test with 中文 and émojis 🎉",
            "special": "Test with \n newlines \t and \r carriage returns",
            "unicode": "Тестирование",
        }

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data

    def test_cache_large_data_structure(self, tmp_path):
        """Test cache with large nested data structures."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # Create a large nested structure
        test_data = {
            "level1": {
                f"level2_{i}": {
                    f"level3_{j}": {
                        "data": f"value_{i}_{j}",
                        "items": list(range(10)),
                    }
                    for j in range(5)
                }
                for i in range(5)
            }
        }

        cache.set(key, test_data)
        result = cache.get(key)

        assert result == test_data
