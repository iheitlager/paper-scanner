"""
Unit tests for Crossref metadata fetcher.

Tests the CrossrefMetadataFetcher class for correct API calls,
caching, and field translation.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile

from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefMetadataFetcher,
)
from paper_scanner.core.models import Paper
from paper_scanner.core.enum import PaperType


class TestCrossrefMetadataFetcher:
    """Test suite for CrossrefMetadataFetcher."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def fetcher(self, cache_dir):
        """Create a fetcher instance."""
        return CrossrefMetadataFetcher(cache_dir=cache_dir)

    def test_fetcher_initialization(self, fetcher):
        """Test fetcher initializes with cache directory."""
        assert fetcher.cache_dir.exists()
        assert fetcher.name == "crossref"

    def test_cache_file_path_generation(self, fetcher):
        """Test cache file path is generated correctly."""
        doi = "10.1145/3025453.3025761"
        cache_file = fetcher._cache._get_cache_path(doi)

        # Should be MD5 hash of normalized DOI
        assert cache_file.parent == fetcher._cache.cache_dir
        assert cache_file.suffix == ".json"
        assert len(cache_file.stem) == 32  # MD5 hex string length

    def test_cache_file_normalization(self, fetcher):
        """Test cache file path is same for different DOI formats."""
        doi1 = "10.1145/3025453.3025761"
        doi2 = "DOI:10.1145/3025453.3025761"
        doi3 = "https://doi.org/10.1145/3025453.3025761"

        file1 = fetcher._cache._get_cache_path(doi1)
        file2 = fetcher._cache._get_cache_path(doi2)
        file3 = fetcher._cache._get_cache_path(doi3)

        # All should normalize to same file
        assert file1 == file2 == file3

    def test_abstract_extraction(self, fetcher):
        """Test abstract extraction from API response."""
        api_data = {
            "abstract": "This is a test abstract about software engineering."
        }
        abstract = fetcher._extract_abstract(api_data)
        assert abstract == "This is a test abstract about software engineering."

    def test_abstract_extraction_empty(self, fetcher):
        """Test abstract extraction returns None for missing abstract."""
        api_data = {"title": "Test"}
        abstract = fetcher._extract_abstract(api_data)
        assert abstract is None

    def test_authors_extraction(self, fetcher):
        """Test author extraction from API response."""
        api_data = {
            "author": [
                {"given": "John", "family": "Smith"},
                {"given": "Jane", "family": "Doe"},
            ]
        }
        authors = fetcher._extract_authors(api_data)
        assert len(authors) == 2
        assert authors[0].given_name == "John"
        assert authors[0].family_name == "Smith"
        assert authors[1].given_name == "Jane"
        assert authors[1].family_name == "Doe"

    def test_authors_extraction_missing_family(self, fetcher):
        """Test author extraction skips authors without family name."""
        api_data = {
            "author": [
                {"given": "John", "family": "Smith"},
                {"given": "Jane"},  # Missing family name
            ]
        }
        authors = fetcher._extract_authors(api_data)
        assert len(authors) == 1
        assert authors[0].family_name == "Smith"

    def test_keywords_extraction(self, fetcher):
        """Test keywords extraction from subjects."""
        api_data = {"subject": ["machine learning", "software engineering", "AI"]}
        keywords = fetcher._extract_keywords(api_data)
        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_topics_extraction(self, fetcher):
        """Test topics extraction (should be empty for Crossref)."""
        api_data = {"subject": ["topic1", "topic2"]}
        topics = fetcher._extract_topics(api_data)
        assert topics == []

    def test_paper_type_extraction(self, fetcher):
        """Test paper type extraction and mapping."""
        test_cases = [
            ("journal-article", PaperType.JOURNAL_ARTICLE.value),
            ("proceedings-article", PaperType.CONFERENCE_PAPER.value),
            ("book", PaperType.BOOK.value),
            ("book-chapter", PaperType.BOOK_CHAPTER.value),
            ("report", PaperType.TECHNICAL_REPORT.value),
            ("preprint", PaperType.PREPRINT.value),
        ]

        for crossref_type, expected_paper_type in test_cases:
            api_data = {"type": crossref_type}
            result = fetcher._extract_paper_type(api_data)
            assert result == expected_paper_type

    def test_paper_type_extraction_unknown(self, fetcher):
        """Test paper type extraction returns None for unknown types."""
        api_data = {"type": "unknown-type"}
        result = fetcher._extract_paper_type(api_data)
        assert result is None

    def test_oa_status_extraction(self, fetcher):
        """Test OA status extraction (should be None for Crossref)."""
        api_data = {"is-referenced-by-count": 10}
        oa_status = fetcher._extract_oa_status(api_data)
        assert oa_status is None

    def test_source_key_extraction(self, fetcher):
        """Test source key extraction returns DOI."""
        api_data = {"DOI": "10.1145/3025453.3025761"}
        source_key = fetcher._extract_source_key(api_data)
        assert source_key == "10.1145/3025453.3025761"

    def test_source_key_extraction_missing(self, fetcher):
        """Test source key extraction returns None if missing."""
        api_data = {"title": "Test"}
        source_key = fetcher._extract_source_key(api_data)
        assert source_key is None

    def test_cite_key_generation(self, fetcher):
        """Test cite key generation from authors and year."""
        from paper_scanner.core.models import Author

        authors = [
            Author(given_name="John", family_name="Smith", full_name="John Smith")
        ]
        year = 2020
        doi = "10.1145/3025453.3025761"

        cite_key = fetcher._generate_cite_key(authors, year, doi)
        assert cite_key == "smith_2020"

    def test_cite_key_generation_no_author(self, fetcher):
        """Test cite key generation without author."""
        doi = "10.1145/3025453.3025761"
        cite_key = fetcher._generate_cite_key([], None, doi)
        assert "doi_" in cite_key

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.requests.Session.get")
    def test_fetch_from_api_success(self, mock_get, fetcher):
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

        result = fetcher._fetch_from_api("10.1145/3025453.3025761")
        assert result is not None
        assert result["title"] == "Test Article"

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.requests.Session.get")
    def test_fetch_from_api_not_found(self, mock_get, fetcher):
        """Test API fetch for non-existent DOI."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetcher._fetch_from_api("10.1145/invalid")
        assert result is None

    def test_translate_to_paper(self, fetcher):
        """Test translation of API response to Paper model."""
        api_data = {
            "title": "Test Article",
            "DOI": "10.1145/3025453.3025761",
            "author": [{"given": "John", "family": "Smith"}],
            "abstract": "This is a test abstract.",
            "type": "journal-article",
            "year": 2020,
            "journal": "Test Journal",
            "volume": "10",
            "issue": "2",
            "page": "100-110",
        }

        paper = fetcher._translate_to_paper("10.1145/3025453.3025761", api_data)

        assert isinstance(paper, Paper)
        assert paper.title == "Test Article"
        assert paper.doi == "10.1145/3025453.3025761"
        assert len(paper.authors) == 1
        assert paper.authors[0].family_name == "Smith"
        assert paper.abstract == "This is a test abstract."
        assert paper.discovery.source_database == "crossref"

    def test_cache_save_and_load(self, fetcher):
        """Test caching of API response."""
        doi = "10.1145/3025453.3025761"

        api_data = {
            "title": "Test Article",
            "DOI": doi,
            "author": [{"given": "John", "family": "Smith"}],
        }

        # Save to cache
        success = fetcher._cache.set(doi, api_data)
        assert success

        # Load from cache
        loaded = fetcher._cache.get(doi)
        assert loaded == api_data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
