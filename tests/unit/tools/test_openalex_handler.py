"""
Integration tests for OpenAlexHandler.

Tests handler-level behavior including unified cache and workflow integration.
Focus: API fetch, cache behavior, and method workflows (metadata + citations).
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from paper_scanner.tools.fetchers.fetcher_handlers.openalex_handler import (
    OpenAlexHandler,
)
from paper_scanner.core.models import Paper


class TestOpenAlexHandlerInitialization:
    """Test handler initialization and basic setup."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create an OpenAlexHandler instance."""
        return OpenAlexHandler(cache_dir=cache_dir)

    def test_handler_initialization(self, handler):
        """Test handler initializes with cache directory."""
        assert handler.cache_dir.exists()
        assert handler.name == "openalex"

    def test_cache_file_path_generation(self, handler):
        """Test cache file path is generated correctly."""
        doi = "10.1145/3025453.3025761"
        cache_file = handler._jsoncache._get_cache_path(doi)

        # Should be MD5 hash of normalized DOI
        assert cache_file.parent == handler._jsoncache.cache_dir
        assert cache_file.suffix == ".json"
        assert len(cache_file.stem) == 32  # MD5 hex string length

    def test_cache_file_normalization(self, handler):
        """Test cache file path is same for different DOI formats."""
        doi1 = "10.1145/3025453.3025761"
        doi2 = "https://doi.org/10.1145/3025453.3025761"
        doi3 = "http://doi.org/10.1145/3025453.3025761"

        path1 = handler._jsoncache._get_cache_path(doi1)
        path2 = handler._jsoncache._get_cache_path(doi2)
        path3 = handler._jsoncache._get_cache_path(doi3)

        # All should normalize to same path
        assert path1 == path2 == path3

    def test_handler_has_session(self, handler):
        """Test handler has requests session configured."""
        assert handler.session is not None
        assert "User-Agent" in handler.session.headers


class TestOpenAlexHandlerAPIFetch:
    """Test API fetch functionality."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create an OpenAlexHandler instance."""
        return OpenAlexHandler(cache_dir=cache_dir)

    def test_fetch_from_api_success(self, handler):
        """Test successful API fetch."""
        doi = "10.1145/3025453.3025761"
        mock_response = {
            "id": "https://openalex.org/W1234567890",
            "title": "Test Paper",
            "doi": doi,
            "publication_year": 2024,
            "abstract": "Test abstract",
            "authorships": [],
            "is_oa": True,
        }

        with patch.object(
            handler.session,
            "get",
            return_value=MagicMock(json=lambda: mock_response, status_code=200),
        ):
            result = handler._fetch_from_api(doi)
            assert result is not None
            assert result["title"] == "Test Paper"
            assert result["doi"] == doi

    def test_fetch_from_api_not_found(self, handler):
        """Test API returns None for not found."""
        doi = "10.9999/nonexistent"

        with patch.object(
            handler.session,
            "get",
            return_value=MagicMock(json=lambda: None, status_code=404),
        ):
            result = handler._fetch_from_api(doi)
            assert result is None


class TestOpenAlexHandlerUnifiedCache:
    """Test unified cache behavior across metadata and citations."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create an OpenAlexHandler instance."""
        return OpenAlexHandler(cache_dir=cache_dir)

    def test_fetch_paper_then_citations_uses_cache(self, handler):
        """Test that fetching citations after metadata uses same cache."""
        doi = "10.1145/3025453.3025761"
        mock_data = {
            "id": "https://openalex.org/W1234567890",
            "title": "Test Paper",
            "doi": doi,
            "publication_year": 2024,
            "authorships": [],
        }

        with patch.object(
            handler.session, "get", return_value=MagicMock(json=lambda: mock_data)
        ):
            # First call to fetch_paper
            paper, hit1 = handler.fetch_paper(doi)
            assert paper is not None
            assert hit1 is False  # Cache miss

            # Second call should hit cache
            paper, hit2 = handler.fetch_paper(doi)
            assert paper is not None
            assert hit2 is True  # Cache hit

    def test_cache_persists_across_instances(self, cache_dir):
        """Test that cache persists across handler instances."""
        doi = "10.1145/3025453.3025761"
        mock_data = {
            "id": "https://openalex.org/W1234567890",
            "title": "Test Paper",
            "doi": doi,
            "publication_year": 2024,
            "authorships": [],
        }

        # First handler instance
        handler1 = OpenAlexHandler(cache_dir=cache_dir)
        with patch.object(
            handler1.session, "get", return_value=MagicMock(json=lambda: mock_data)
        ):
            paper1, hit1 = handler1.fetch_paper(doi)
            assert hit1 is False

        # Second handler instance with same cache dir
        handler2 = OpenAlexHandler(cache_dir=cache_dir)
        with patch.object(
            handler2.session, "get", return_value=MagicMock(json=lambda: mock_data)
        ):
            paper2, hit2 = handler2.fetch_paper(doi)
            # Should be cache hit because cache persists
            assert hit2 is True
            assert paper1.title == paper2.title


class TestOpenAlexHandlerIntegration:
    """Integration tests for OpenAlex handler."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create an OpenAlexHandler instance."""
        return OpenAlexHandler(cache_dir=cache_dir)

    def test_handler_name_property(self, handler):
        """Test handler returns correct name."""
        assert handler.name == "openalex"
        assert isinstance(handler.name, str)

    def test_handler_cache_directories_exist(self, handler):
        """Test that cache directories are created."""
        assert handler.cache_dir.exists()
        assert handler.cache_dir_json.exists()
