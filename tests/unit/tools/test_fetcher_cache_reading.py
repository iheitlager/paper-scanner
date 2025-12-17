"""
Tests for BaseFetcherHandler cache integration.

Validates that the base class caching behavior works correctly at the handler level.
Focus is on cache interaction patterns, not low-level JSONFileCache (tested in test_cache.py).

Uses a minimal DummyHandler to test generic cache behavior independently of any
specific API implementation (Crossref, etc).
"""

from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.models import Paper, Author
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler


class DummyHandler(BaseFetcherHandler):
    """Minimal handler implementation for testing base class cache behavior."""

    @property
    def name(self) -> str:
        """Handler name."""
        return "dummy"

    def _fetch_from_api(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Mock API fetch - returns minimal test data."""
        return {
            "id": identifier,
            "title": f"Test Paper {identifier}",
            "abstract": f"Abstract for {identifier}",
            "authors": [{"name": "Test Author"}],
        }

    def _extract_abstract(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract abstract."""
        return api_data.get("abstract")

    def _extract_authors(self, api_data: Dict[str, Any]) -> list:
        """Extract authors."""
        return [
            Author(
                family_name="TestAuthor",
                given_name="Test",
                full_name="Test TestAuthor"
            )
        ]

    def _extract_keywords(self, api_data: Dict[str, Any]) -> list:
        """Extract keywords."""
        return []

    def _extract_topics(self, api_data: Dict[str, Any]) -> list:
        """Extract topics."""
        return []

    def _extract_paper_type(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract paper type."""
        return "journal_article"

    def _extract_year(self, api_data: Dict[str, Any]) -> Optional[int]:
        """Extract year."""
        return 2025

    def _extract_journal(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract journal."""
        return "Test Journal"

    def _extract_oa_status(self, api_data: Dict[str, Any]) -> Optional[Any]:
        """Extract OA status."""
        return None

    def _extract_source_key(self, api_data: Dict[str, Any]) -> Optional[str]:
        """Extract source key."""
        return api_data.get("id")

    def _extract_citations(self, api_response: Dict[str, Any]) -> list:
        """Mock citation extraction."""
        return []


class TestBaseCacheIntegration:
    """Test BaseFetcherHandler cache behavior using DummyHandler."""

    @pytest.fixture
    def dummy_handler(self, tmp_path) -> DummyHandler:
        """Create a dummy handler with temp cache directory."""
        return DummyHandler(cache_dir=tmp_path)

    def test_fetch_paper_cache_miss_then_hit(self, dummy_handler):
        """Test cache miss on first fetch_paper, then cache hit on second."""
        identifier = "10.1000/test-id-1"

        with patch.object(
            dummy_handler, "_fetch_from_api", wraps=dummy_handler._fetch_from_api
        ) as mock_api:
            # First call - cache miss
            paper1, hit1 = dummy_handler.fetch_paper(identifier)
            assert hit1 is False, "First call should be cache miss"
            assert mock_api.call_count == 1
            assert paper1 is not None
            assert paper1.source_key == identifier

            # Second call - cache hit
            paper2, hit2 = dummy_handler.fetch_paper(identifier)
            assert hit2 is True, "Second call should be cache hit"
            assert mock_api.call_count == 1, "API should not be called again"
            assert paper2.source_key == paper1.source_key
            assert paper2.title == paper1.title

    def test_fetch_citations_shares_cache_with_metadata(self, dummy_handler):
        """Test that fetch_citations uses same cache as fetch_paper."""
        identifier = "10.1000/test-id-2"

        with patch.object(
            dummy_handler, "_fetch_from_api", wraps=dummy_handler._fetch_from_api
        ) as mock_api:
            # First call - fetch metadata (populates cache)
            paper, hit1 = dummy_handler.fetch_paper(identifier)
            assert hit1 is False
            assert mock_api.call_count == 1

            # Second call - fetch citations (should reuse cached data)
            citations, hit2 = dummy_handler.fetch_citations(identifier)
            assert hit2 is True, "fetch_citations should hit cache from fetch_paper"
            assert mock_api.call_count == 1, "No additional API call should occur"

    def test_cache_persists_across_handler_instances(self, tmp_path):
        """Test that cache is shared across different handler instances."""
        identifier = "10.1000/test-id-3"

        # Create first handler and populate cache
        handler1 = DummyHandler(cache_dir=tmp_path)
        paper1, hit1 = handler1.fetch_paper(identifier)
        assert hit1 is False

        # Create second handler with same cache dir
        handler2 = DummyHandler(cache_dir=tmp_path)
        with patch.object(
            handler2, "_fetch_from_api", return_value=None
        ) as mock_api:
            paper2, hit2 = handler2.fetch_paper(identifier)
            assert hit2 is True, "Should hit cache from handler1"
            assert mock_api.call_count == 0, "API should not be called"
            assert paper2.source_key == paper1.source_key

    def test_cache_handles_none_response(self, dummy_handler):
        """Test cache behavior when API returns None."""
        identifier = "10.1000/test-id-14"

        with patch.object(dummy_handler, "_fetch_from_api", return_value=None):
            paper1, hit1 = dummy_handler.fetch_paper(identifier)
            assert hit1 is False
            assert paper1 is None

            # Second call - API returns None again (not cached, None is not cached)
            paper2, hit2 = dummy_handler.fetch_paper(identifier)
            assert hit2 is False, "None responses are not cached"
            assert paper2 is None

    def test_different_identifiers_use_different_cache_entries(self, dummy_handler):
        """Test that different identifiers produce different cache entries."""
        id1 = "10.1000/test-id-1"
        id2 = "10.1000/test-id-2"

        with patch.object(
            dummy_handler, "_fetch_from_api", wraps=dummy_handler._fetch_from_api
        ) as mock_api:
            paper1, _ = dummy_handler.fetch_paper(id1)
            assert mock_api.call_count == 1
            assert paper1.source_key == id1

            paper2, _ = dummy_handler.fetch_paper(id2)
            assert mock_api.call_count == 2, "Different ID should trigger new API call"
            assert paper2.source_key == id2
            assert paper2.source_key != paper1.source_key

    def test_cache_file_path_consistency(self, dummy_handler):
        """Test that same identifier always produces same cache file path."""
        identifier = "10.1000/test-id-6"

        path1 = dummy_handler._cache._get_cache_path(identifier)
        path2 = dummy_handler._cache._get_cache_path(identifier)

        assert path1 == path2, "Same identifier should always map to same cache path"

    def test_cache_returns_tuple_with_hit_flag(self, dummy_handler):
        """Test that fetch_paper returns tuple of (Paper, cache_hit_bool)."""
        identifier = "10.1000/test-id-7"

        result1 = dummy_handler.fetch_paper(identifier)
        assert isinstance(result1, tuple), "Should return tuple"
        assert len(result1) == 2, "Tuple should have 2 elements"
        paper1, hit1 = result1
        assert isinstance(hit1, bool), "Second element should be boolean"
        assert hit1 is False, "First call should be cache miss"
        assert paper1 is not None

        result2 = dummy_handler.fetch_paper(identifier)
        paper2, hit2 = result2
        assert hit2 is True, "Second call should be cache hit"

    def test_fetch_citations_returns_tuple(self, dummy_handler):
        """Test that fetch_citations also returns tuple with hit flag."""
        identifier = "10.1000/test-id-8"

        result = dummy_handler.fetch_citations(identifier)
        assert isinstance(result, tuple), "Should return tuple"
        assert len(result) == 2, "Tuple should have 2 elements"
        citations, hit = result
        assert isinstance(hit, bool), "Second element should be boolean"
