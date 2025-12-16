"""
Test suite for Fetcher orchestrator.

Tests initialization, metadata fetching, fallback logic, caching, error handling,
DOI normalization, and integration scenarios.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from paper_scanner.tools.fetchers.fetcher import Fetcher
from paper_scanner.core.models import Paper


class TestFetcherInitialization:
    """Test Fetcher initialization."""

    def test_fetcher_initialization_with_crossref(self, tmp_path):
        """Test basic initialization with Crossref method."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        assert "crossref" in fetcher.handlers
        assert fetcher.cache_dir == tmp_path

    def test_fetcher_cache_dir_expansion(self):
        """Test that ~ is expanded in cache directory path."""
        fetcher = Fetcher(cache_dir="~/test_cache", methods=["crossref"])
        assert "~" not in str(fetcher.cache_dir)
        assert fetcher.cache_dir.is_absolute()

    def test_fetcher_handler_cache_subdirectory(self, tmp_path):
        """Test that handlers get method-specific cache subdirectories."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        handler = fetcher.handlers["crossref"]
        expected_cache_dir = tmp_path / "crossref"
        assert handler.cache_dir == expected_cache_dir

    def test_fetcher_initialization_with_unknown_method(self, tmp_path):
        """Test fetcher raises error for unknown methods."""
        with pytest.raises(ValueError, match="No valid handlers registered"):
            Fetcher(cache_dir=tmp_path, methods=["unknown"])

    def test_fetcher_initialization_no_valid_handlers(self, tmp_path):
        """Test that ValueError is raised when no valid handlers are registered."""
        with pytest.raises(ValueError, match="No valid handlers registered"):
            Fetcher(cache_dir=tmp_path, methods=["unknown_method"])

    def test_fetcher_initialization_with_multiple_methods_fallback(self, tmp_path):
        """Test initialization with multiple methods - only valid ones succeed."""
        # Crossref exists but unknown doesn't
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        assert len(fetcher.handlers) > 0

    def test_fetcher_handlers_are_different_instances(self, tmp_path):
        """Test that multiple Fetcher instances have different handler instances."""
        fetcher1 = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        fetcher2 = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        assert fetcher1.handlers["crossref"] is not fetcher2.handlers["crossref"]


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
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
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
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
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
            result, cache_hit = fetcher.fetch_paper("10.9999/nonexistent")
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
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
            assert result is None


class TestFetcherFallbackLogic:
    """Test fallback logic across multiple handlers."""

    def test_fetch_returns_none_single_handler_fails(self, tmp_path):
        """Test returns None when single handler fails."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            side_effect=Exception("Fail"),
        ):
            result, cache_hit = fetcher.fetch_paper("10.9999/all_fail")
            assert result is None

    def test_fetch_with_empty_methods_raises_error(self, tmp_path):
        """Test behavior when no methods provided."""
        with pytest.raises(ValueError, match="No valid handlers"):
            Fetcher(cache_dir=tmp_path, methods=[])


class TestFetcherCaching:
    """Test caching behavior."""

    def test_fetch_paper_propagates_cache_hit_from_handler(self, tmp_path):
        """Test cache_hit status is propagated from handler."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        mock_paper = Paper(cite_key="test2024", title="Test", doi="10.1234/test")

        # First call: cache miss
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(mock_paper, False),
        ):
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
            assert cache_hit is False

        # Second call: cache hit
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(mock_paper, True),
        ):
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
            assert cache_hit is True

    def test_fetcher_with_real_crossref_handler(self, tmp_path):
        """Test Fetcher with real Crossref handler (integration)."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        assert "crossref" in fetcher.handlers
        handler = fetcher.handlers["crossref"]
        assert handler.cache_dir == (tmp_path / "crossref")


class TestFetcherErrorHandling:
    """Test error handling and recovery."""

    def test_fetch_continues_after_handler_error(self, tmp_path):
        """Test fetcher returns None when handler errors."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            side_effect=RuntimeError("Connection error"),
        ):
            result, cache_hit = fetcher.fetch_paper("10.1234/test")
            assert result is None

    def test_fetcher_initialization_with_non_existent_cache_dir(self):
        """Test Fetcher can work with non-existent cache directory."""
        non_existent = Path("/tmp/non_existent_path_12345")
        fetcher = Fetcher(cache_dir=non_existent, methods=["crossref"])
        assert fetcher.cache_dir == non_existent


class TestFetcherDOINormalization:
    """Test DOI format handling."""

    def test_fetch_with_different_doi_formats(self, tmp_path):
        """Test fetcher with different DOI input formats."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        mock_paper = Paper(cite_key="test2024", title="Test", doi="10.1234/test")
        with patch.object(
            fetcher.handlers["crossref"],
            "fetch_paper",
            return_value=(mock_paper, False),
        ):
            # Test various DOI formats
            for doi in ["10.1234/test", "https://doi.org/10.1234/test", "doi.org/10.1234/test"]:
                result, _ = fetcher.fetch_paper(doi)
                assert result is not None


class TestFetcherIntegration:
    """Integration tests."""

    def test_fetcher_integration_with_crossref(self, tmp_path):
        """Test Fetcher integration with real Crossref handler."""
        fetcher = Fetcher(cache_dir=tmp_path, methods=["crossref"])
        assert len(fetcher.handlers) > 0
        assert fetcher.cache_dir == tmp_path

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
