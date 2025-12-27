"""
Test suite for Fetcher metadata fetching functionality.

Tests metadata fetching, caching, error handling, and integration scenarios.
"""

from unittest.mock import patch

from paper_scanner.core.models import Paper
from paper_scanner.tools.fetchers.fetcher import Fetcher


class TestFetcherMetadataFetching:
    """Test metadata fetching."""

    def test_fetch_paper_success(self, tmp_path):
        """Test successful metadata fetch with real Crossref handler."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        mock_paper = Paper(cite_key="test2024", title="Test", doi="10.1234/test")
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(mock_paper, False),
        ):
            result, cache_hit, handler = fetcher.fetch_paper("10.1234/test")
            assert result is not None
            assert result.title == "Test"
            assert cache_hit is False

    def test_fetch_paper_cache_hit(self, tmp_path):
        """Test cache hit detection."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        mock_paper = Paper(cite_key="test2024", title="Test", doi="10.1234/test")
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(mock_paper, True),
        ):
            result, cache_hit, handler = fetcher.fetch_paper("10.1234/test")
            assert result is not None
            assert cache_hit is True

    def test_fetch_paper_not_found(self, tmp_path):
        """Test metadata not found returns None."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(None, False),
        ):
            result, cache_hit, handler = fetcher.fetch_paper("10.9999/nonexistent")
            assert result is None
            assert cache_hit is False

    def test_fetch_paper_handler_exception(self, tmp_path):
        """Test handler exception is caught and logged."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            side_effect=Exception("Test error"),
        ):
            result, cache_hit, handler = fetcher.fetch_paper("10.1234/test")
            assert result is None
            assert cache_hit is False
