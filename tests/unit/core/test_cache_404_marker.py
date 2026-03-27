"""
Unit tests for 404 caching functionality in JSONFileCache.

Tests the 404 marker creation, detection, and cache behavior with not-found entries.
"""

from datetime import datetime

from paper_scanner.core.cache import (
    JSONFileCache,
    create_404_marker,
    is_404_marker,
)


class TestCreate404Marker:
    """Tests for creating 404 markers."""

    def test_create_404_marker_without_url(self):
        """Test creating a 404 marker without URL."""
        marker = create_404_marker(key="10.1234/test.doi")

        assert marker["ITEM"] == "404 - NOT FOUND"
        assert marker["KEY"] == "10.1234/test.doi"
        assert "LAST-CHECKED" in marker
        assert marker["URL"] is None
        assert isinstance(marker["LAST-CHECKED"], str)

    def test_create_404_marker_with_url(self):
        """Test creating a 404 marker with URL."""
        url = "https://doi.org/10.1234/test"
        marker = create_404_marker(key="10.1234/test.doi", url=url)

        assert marker["ITEM"] == "404 - NOT FOUND"
        assert marker["KEY"] == "10.1234/test.doi"
        assert marker["URL"] == url
        assert "LAST-CHECKED" in marker

    def test_404_marker_timestamp_is_iso_format(self):
        """Test that 404 marker timestamp is in ISO format."""
        marker = create_404_marker(key="10.1234/test.doi")

        # Should be parseable as ISO datetime
        timestamp = marker["LAST-CHECKED"]
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)


class TestIs404Marker:
    """Tests for detecting 404 markers."""

    def test_is_404_marker_with_valid_marker(self):
        """Test detecting a valid 404 marker."""
        marker = create_404_marker(key="10.1234/test.doi")
        assert is_404_marker(marker) is True

    def test_is_404_marker_with_url(self):
        """Test detecting a 404 marker with URL."""
        marker = create_404_marker(key="10.1234/test.doi", url="https://doi.org/10.1234/test")
        assert is_404_marker(marker) is True

    def test_is_404_marker_with_normal_dict(self):
        """Test that normal dicts are not detected as 404 markers."""
        normal_dict = {"ITEM": "Something", "title": "Test"}
        assert is_404_marker(normal_dict) is False

    def test_is_404_marker_with_missing_fields(self):
        """Test that incomplete 404 markers are not detected."""
        incomplete = {"ITEM": "404 - NOT FOUND"}
        assert is_404_marker(incomplete) is False

    def test_is_404_marker_with_non_dict(self):
        """Test that non-dict values are not detected as 404 markers."""
        assert is_404_marker(None) is False
        assert is_404_marker("404") is False
        assert is_404_marker(404) is False
        assert is_404_marker([]) is False


class TestCache404Behavior:
    """Tests for cache behavior with 404 markers."""

    def test_cache_404_marker(self, tmp_path):
        """Test caching and retrieving a 404 marker."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        marker = create_404_marker(key=key, url="https://doi.org/10.1234/test.doi")

        # Store marker
        cache.set(key, marker)

        # Retrieve marker
        retrieved = cache.get(key, ttl=-1)  # Never expire for this test

        assert retrieved is not None
        assert is_404_marker(retrieved)
        assert retrieved["URL"] == "https://doi.org/10.1234/test.doi"

    def test_get_404_marker_returns_marker_not_none(self, tmp_path):
        """Test that get returns the marker dict, not None (distinction is important)."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"
        marker = create_404_marker(key=key)

        cache.set(key, marker)
        retrieved = cache.get(key, ttl=-1)

        # get() returns the marker, not None
        assert retrieved is not None
        assert is_404_marker(retrieved)

    def test_multiple_404_markers(self, tmp_path):
        """Test caching multiple 404 markers."""
        cache = JSONFileCache(cache_dir=tmp_path)
        keys = ["10.1234/doi1", "10.1234/doi2", "10.1234/doi3"]

        # Cache 404 markers for all keys
        for key in keys:
            marker = create_404_marker(key=key, url=f"https://doi.org/{key}")
            cache.set(key, marker)

        # Verify all are cached as 404s
        for key in keys:
            retrieved = cache.get(key, ttl=-1)
            assert is_404_marker(retrieved)

    def test_404_marker_with_ttl_expiration(self, tmp_path):
        """Test that 404 markers respect TTL like normal cache entries."""
        import os

        cache = JSONFileCache(cache_dir=tmp_path, default_ttl=1)  # 1 day TTL
        key = "10.1234/test.doi"
        marker = create_404_marker(key=key)

        cache.set(key, marker)

        # Verify it's cached
        retrieved = cache.get(key, ttl=1)
        assert is_404_marker(retrieved)

        # Set file mtime to 2 days ago
        cache_path = cache._get_cache_path(key)
        past_time = datetime.now() - __import__("datetime").timedelta(days=2)
        timestamp = past_time.timestamp()
        os.utime(cache_path, (timestamp, timestamp))

        # Should expire now
        retrieved = cache.get(key, ttl=1)
        assert retrieved is None
        assert not cache_path.exists()


class TestCache404Integration:
    """Integration tests for 404 caching with normal cache behavior."""

    def test_cache_normal_data_then_404(self, tmp_path):
        """Test caching normal data, then replacing with 404 marker."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # First, cache normal data
        normal_data = {"title": "Test Paper", "year": 2023}
        cache.set(key, normal_data)

        retrieved = cache.get(key, ttl=-1)
        assert retrieved == normal_data
        assert not is_404_marker(retrieved)

        # Then, replace with 404 marker
        marker = create_404_marker(key=key)
        cache.set(key, marker)

        retrieved = cache.get(key, ttl=-1)
        assert is_404_marker(retrieved)

    def test_distinguish_404_marker_from_empty_dict(self, tmp_path):
        """Test that 404 markers can be distinguished from empty dicts."""
        cache = JSONFileCache(cache_dir=tmp_path)

        # Cache empty dict
        cache.set("10.1234/empty", {})
        empty_result = cache.get("10.1234/empty", ttl=-1)
        assert empty_result == {}
        assert not is_404_marker(empty_result)

        # Cache 404 marker
        cache.set("10.1234/notfound", create_404_marker(key="10.1234/notfound"))
        marker_result = cache.get("10.1234/notfound", ttl=-1)
        assert is_404_marker(marker_result)

    def test_distinguish_404_marker_from_null_response(self, tmp_path):
        """Test that 404 markers are stored while None returns are not."""
        cache = JSONFileCache(cache_dir=tmp_path)
        key = "10.1234/test.doi"

        # When API returns None (404), we store a marker
        marker = create_404_marker(key=key)
        cache.set(key, marker)

        # get() should return the marker, not None
        retrieved = cache.get(key, ttl=-1)
        assert retrieved is not None
        assert is_404_marker(retrieved)
