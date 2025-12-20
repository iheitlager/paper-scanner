"""
Unit tests for Crossref metadata extraction.

Tests the CrossrefHandler class for correct metadata field extraction,
Paper model translation, and cite key generation.
Focus: Metadata -> Paper model transformation, NOT citations.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefHandler,
)
from paper_scanner.core.models import Paper
from paper_scanner.core.enum import PaperType


class TestCrossrefMetadataExtraction:
    """Test metadata extraction from Crossref API responses."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a CrossrefHandler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    def test_abstract_extraction(self, handler):
        """Test abstract extraction from API response."""
        api_data = {
            "abstract": "This is a test abstract about software engineering."
        }
        abstract = handler._extract_abstract(api_data)
        assert abstract == "This is a test abstract about software engineering."

    def test_abstract_extraction_empty(self, handler):
        """Test abstract extraction returns None for missing abstract."""
        api_data = {"title": "Test"}
        abstract = handler._extract_abstract(api_data)
        assert abstract is None

    def test_authors_extraction(self, handler):
        """Test author extraction from API response."""
        api_data = {
            "author": [
                {"given": "John", "family": "Smith"},
                {"given": "Jane", "family": "Doe"},
            ]
        }
        authors = handler._extract_authors(api_data)
        assert len(authors) == 2
        assert authors[0].given_name == "John"
        assert authors[0].family_name == "Smith"
        assert authors[1].given_name == "Jane"
        assert authors[1].family_name == "Doe"

    def test_authors_extraction_missing_family(self, handler):
        """Test author extraction skips authors without family name."""
        api_data = {
            "author": [
                {"given": "John", "family": "Smith"},
                {"given": "Jane"},  # Missing family name
            ]
        }
        authors = handler._extract_authors(api_data)
        assert len(authors) == 1
        assert authors[0].family_name == "Smith"

    def test_keywords_extraction(self, handler):
        """Test keywords extraction from subjects."""
        api_data = {"subject": ["machine learning", "software engineering", "AI"]}
        keywords = handler._extract_keywords(api_data)
        assert len(keywords) == 3
        assert "machine learning" in keywords

    def test_topics_extraction(self, handler):
        """Test topics extraction (should be empty for Crossref)."""
        api_data = {"subject": ["topic1", "topic2"]}
        topics = handler._extract_topics(api_data)
        assert topics == []

    def test_paper_type_extraction(self, handler):
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
            result = handler._extract_paper_type(api_data)
            assert result == expected_paper_type

    def test_paper_type_extraction_unknown(self, handler):
        """Test paper type extraction returns None for unknown types."""
        api_data = {"type": "unknown-type"}
        result = handler._extract_paper_type(api_data)
        assert result is None

    def test_oa_status_extraction(self, handler):
        """Test OA status extraction (should be None for Crossref)."""
        api_data = {"is-referenced-by-count": 10}
        oa_status = handler._extract_oa_status(api_data)
        assert oa_status is None

    def test_source_key_extraction(self, handler):
        """Test source key extraction returns DOI."""
        api_data = {"DOI": "10.1145/3025453.3025761"}
        source_key = handler._extract_source_key(api_data)
        assert source_key == "10.1145/3025453.3025761"

    def test_source_key_extraction_missing(self, handler):
        """Test source key extraction returns None if missing."""
        api_data = {"title": "Test"}
        source_key = handler._extract_source_key(api_data)
        assert source_key is None

    def test_year_extraction_from_published_print(self, handler):
        """Test year extraction from published-print field (Crossref format)."""
        api_data = {
            "published-print": {"date-parts": [[2026, 3]]}
        }
        year = handler._extract_year(api_data)
        assert year == 2026

    def test_year_extraction_from_published_online(self, handler):
        """Test year extraction from published-online field."""
        api_data = {
            "published-online": {"date-parts": [[2025, 12, 7]]}
        }
        year = handler._extract_year(api_data)
        assert year == 2025

    def test_year_extraction_from_issued(self, handler):
        """Test year extraction from issued field."""
        api_data = {
            "issued": {"date-parts": [[2024, 6, 15]]}
        }
        year = handler._extract_year(api_data)
        assert year == 2024

    def test_year_extraction_priority(self, handler):
        """Test that published-print takes priority over other fields."""
        api_data = {
            "published-print": {"date-parts": [[2026, 3]]},
            "published-online": {"date-parts": [[2025, 12, 7]]},
            "issued": {"date-parts": [[2024, 6, 15]]}
        }
        year = handler._extract_year(api_data)
        assert year == 2026  # published-print should win

    def test_year_extraction_missing(self, handler):
        """Test year extraction returns None when no date found."""
        api_data = {"title": "Test"}
        year = handler._extract_year(api_data)
        assert year is None

    def test_journal_extraction_from_container_title(self, handler):
        """Test journal extraction from container-title field (Crossref format)."""
        api_data = {
            "container-title": ["Technovation"]
        }
        journal = handler._extract_journal(api_data)
        assert journal == "Technovation"

    def test_journal_extraction_from_container_title_string(self, handler):
        """Test journal extraction when container-title is a string."""
        api_data = {
            "container-title": "Journal of Software Engineering"
        }
        journal = handler._extract_journal(api_data)
        assert journal == "Journal of Software Engineering"

    def test_journal_extraction_from_short_container_title(self, handler):
        """Test journal extraction from short-container-title as fallback."""
        api_data = {
            "short-container-title": ["Technovation"]
        }
        journal = handler._extract_journal(api_data)
        assert journal == "Technovation"

    def test_journal_extraction_priority(self, handler):
        """Test that container-title takes priority over short-container-title."""
        api_data = {
            "container-title": ["Full Journal Name"],
            "short-container-title": ["Short Name"]
        }
        journal = handler._extract_journal(api_data)
        assert journal == "Full Journal Name"

    def test_journal_extraction_missing(self, handler):
        """Test journal extraction returns None when not found."""
        api_data = {"title": "Test"}
        journal = handler._extract_journal(api_data)
        assert journal is None

    def test_url_extraction_from_resource_primary(self, handler):
        """Test URL extraction from resource.primary.URL (Crossref format)."""
        api_data = {
            "resource": {
                "primary": {
                    "URL": "https://linkinghub.elsevier.com/retrieve/pii/S0166497225002287"
                }
            }
        }
        url = handler._extract_url(api_data)
        assert url == "https://linkinghub.elsevier.com/retrieve/pii/S0166497225002287"

    def test_url_extraction_from_top_level_url(self, handler):
        """Test URL extraction from top-level URL field."""
        api_data = {
            "URL": "https://example.com/paper"
        }
        url = handler._extract_url(api_data)
        assert url == "https://example.com/paper"

    def test_url_extraction_priority(self, handler):
        """Test that resource.primary.URL takes priority over top-level URL."""
        api_data = {
            "resource": {
                "primary": {
                    "URL": "https://preferred.url/paper"
                }
            },
            "URL": "https://fallback.url/paper"
        }
        url = handler._extract_url(api_data)
        assert url == "https://preferred.url/paper"

    def test_url_extraction_missing(self, handler):
        """Test URL extraction returns None when not found."""
        api_data = {"title": "Test"}
        url = handler._extract_url(api_data)
        assert url is None

    def test_translate_to_paper_with_url(self, handler):
        """Test translation includes URL extraction."""
        api_data = {
            "title": "Test Article",
            "DOI": "10.1016/j.example.2025.123456",
            "author": [{"given": "Jane", "family": "Doe"}],
            "type": "journal-article",
            "resource": {
                "primary": {
                    "URL": "https://example.com/paper"
                }
            }
        }
        paper = handler._translate_to_paper("10.1016/j.example.2025.123456", api_data)
        assert paper.url == "https://example.com/paper"

    def test_translate_to_paper_with_crossref_formats(self, handler):
        """Test translation with actual Crossref date and journal formats."""
        api_data = {
            "title": "Digital innovation and transformation",
            "DOI": "10.1016/j.technovation.2025.103396",
            "author": [
                {"given": "Yunfei", "family": "Xing"},
                {"given": "Justin Zuopeng", "family": "Zhang"},
                {"given": "Xiwei", "family": "Wang"}
            ],
            "type": "journal-article",
            "published-print": {"date-parts": [[2026, 3]]},
            "container-title": ["Technovation"],
            "volume": "151",
            "publisher": "Elsevier BV"
        }

        paper = handler._translate_to_paper("10.1016/j.technovation.2025.103396", api_data)

        assert paper.year == 2026
        assert paper.journal == "Technovation"
        assert paper.volume == "151"
        assert paper.publisher == "Elsevier BV"
        assert paper.paper_type == PaperType.JOURNAL_ARTICLE.value

    def test_cite_key_generation(self, handler):
        """Test cite key generation from authors and year."""
        from paper_scanner.core.models import Author

        authors = [
            Author(given_name="John", family_name="Smith", full_name="John Smith")
        ]
        year = 2020
        doi = "10.1145/3025453.3025761"

        cite_key = handler._generate_cite_key(authors, year, doi)
        assert cite_key == "doi_2d61f4f8"  # MD5 of "10.1145/3025453.3025761"

    def test_cite_key_generation_no_author(self, handler):
        """Test cite key generation without author."""
        doi = "10.1145/3025453.3025761"
        cite_key = handler._generate_cite_key([], None, doi)
        assert "doi_" in cite_key

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

    def test_translate_to_paper(self, handler):
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

        paper = handler._translate_to_paper("10.1145/3025453.3025761", api_data)

        assert isinstance(paper, Paper)
        assert paper.title == "Test Article"
        assert paper.doi == "10.1145/3025453.3025761"
        assert len(paper.authors) == 1
        assert paper.authors[0].family_name == "Smith"
        assert paper.abstract == "This is a test abstract."
        assert paper.discovery.source_database == "crossref"

    def test_cache_save_and_load(self, handler):
        """Test caching of API response."""
        doi = "10.1145/3025453.3025761"

        api_data = {
            "title": "Test Article",
            "DOI": doi,
            "author": [{"given": "John", "family": "Smith"}],
        }

        # Save to cache
        success = handler._jsoncache.set(doi, api_data)
        assert success

        # Load from cache
        loaded = handler._jsoncache.get(doi)
        assert loaded == api_data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
