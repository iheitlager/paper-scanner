"""
Integration tests for CrossrefHandler.

Tests handler-level behavior including unified cache and workflow integration.
Focus: API fetch, cache behavior, and method workflows (metadata + citations).
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefHandler,
)
from paper_scanner.core.models import Paper


class TestCrossrefHandlerInitialization:
    """Test handler initialization and basic setup."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a CrossrefHandler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    def test_handler_initialization(self, handler):
        """Test handler initializes with cache directory."""
        assert handler.cache_dir.exists()
        assert handler.name == "crossref"

    def test_cache_file_path_generation(self, handler):
        """Test cache file path is generated correctly."""
        doi = "10.1145/3025453.3025761"
        cache_file = handler._cache._get_cache_path(doi)

        # Should be MD5 hash of normalized DOI
        assert cache_file.parent == handler._cache.cache_dir
        assert cache_file.suffix == ".json"
        assert len(cache_file.stem) == 32  # MD5 hex string length

    def test_cache_file_normalization(self, handler):
        """Test cache file path is same for different DOI formats."""
        doi1 = "10.1145/3025453.3025761"
        doi2 = "DOI:10.1145/3025453.3025761"
        doi3 = "https://doi.org/10.1145/3025453.3025761"

        file1 = handler._cache._get_cache_path(doi1)
        file2 = handler._cache._get_cache_path(doi2)
        file3 = handler._cache._get_cache_path(doi3)

        # All should normalize to same file
        assert file1 == file2 == file3


class TestCrossrefAPIFetch:
    """Test API fetch behavior."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a CrossrefHandler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.requests.Session.get")
    def test_fetch_from_api_success(self, mock_get, handler):
        """Test successful API fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "message": {
                "title": "Test Article",
                "DOI": "10.1145/3025453.3025761",
                "author": [{"given": "John", "family": "Smith"}],
                "published-online": {"date-parts": [[2020, 1, 15]]},
            },
        }
        mock_get.return_value = mock_response

        result = handler._fetch_from_api("10.1145/3025453.3025761")
        assert result is not None
        assert result["title"] == "Test Article"

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.requests.Session.get")
    def test_fetch_from_api_not_found(self, mock_get, handler):
        """Test API fetch for non-existent DOI."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = handler._fetch_from_api("10.1145/invalid")
        assert result is None


class TestCrossrefUnifiedCache:
    """Test unified caching between metadata and citations."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a CrossrefHandler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_metadata_then_citations_uses_cache(self, mock_fetch, handler):
        """Test that fetch_citations uses cache populated by fetch_metadata."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Test Paper",
            "reference": [
                {
                    "DOI": "10.1234/test1",
                    "article-title": "Reference 1",
                }
            ]
        }
        
        # First fetch metadata
        paper, meta_hit = handler.fetch_metadata(doi)
        assert meta_hit is False
        assert mock_fetch.call_count == 1
        
        # Then fetch citations - should reuse cache
        citations, cite_hit = handler.fetch_citations(doi)
        assert cite_hit is True
        assert mock_fetch.call_count == 1  # No additional call

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_citations_then_metadata_uses_cache(self, mock_fetch, handler):
        """Test that fetch_metadata uses cache populated by fetch_citations."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Test Paper",
            "reference": [],
            "author": [{"given": "John", "family": "Smith"}],
            "abstract": "Test abstract",
            "type": "journal-article",
        }
        
        # First fetch citations
        citations, cite_hit = handler.fetch_citations(doi)
        assert cite_hit is False
        assert mock_fetch.call_count == 1
        
        # Then fetch metadata - should reuse cache
        paper, meta_hit = handler.fetch_metadata(doi)
        assert meta_hit is True
        assert mock_fetch.call_count == 1  # No additional call

    def test_cache_persists_across_instances(self, cache_dir):
        """Test cache is shared across different handler instances."""
        doi = "10.1145/3025453.3025761"
        
        # Create first handler and populate cache
        handler1 = CrossrefHandler(cache_dir=cache_dir)
        api_data = {
            "DOI": doi,
            "title": "Test Paper",
        }
        success = handler1._cache.set(doi, api_data)
        assert success
        
        # Create second handler with same cache dir
        handler2 = CrossrefHandler(cache_dir=cache_dir)
        with patch.object(
            handler2, "_fetch_from_api", return_value=None
        ) as mock_api:
            paper, hit = handler2.fetch_metadata(doi)
            assert hit is True  # Should hit cache from handler1
            assert mock_api.call_count == 0  # API not called
            assert paper.title == "Test Paper"


class TestCrossrefBackwardCompatibility:
    """Test backward compatibility with old method names."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a CrossrefHandler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_and_parse_delegates_to_fetch_metadata(self, mock_fetch, handler):
        """Test fetch_and_parse delegates to fetch_metadata."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Test Paper",
            "author": [{"given": "John", "family": "Smith"}],
            "abstract": "Abstract",
            "type": "journal-article",
        }
        
        # Old API should work
        paper, cache_hit = handler.fetch_and_parse(doi)
        assert paper is not None
        assert paper.title == "Test Paper"
        assert cache_hit is False

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_and_parse_citations_delegates_to_fetch_citations(self, mock_fetch, handler):
        """Test fetch_and_parse_citations delegates to fetch_citations."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "reference": [
                {"DOI": "10.1234/test1", "article-title": "Ref 1"}
            ]
        }
        
        # Old API should work
        citations, cache_hit = handler.fetch_and_parse_citations(doi)
        assert len(citations) >= 0
        assert cache_hit is False
