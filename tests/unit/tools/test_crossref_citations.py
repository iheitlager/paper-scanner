"""
Unit tests for Crossref citation extraction and parsing.

Tests citation extraction, reference parsing, and confidence scoring.
Focus: References -> Citation models, NOT metadata extraction.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import (
    CrossrefHandler,
)
from paper_scanner.core.models import Citation


class TestCrossrefCitationExtraction:
    """Test citation extraction from Crossref API responses."""

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
    def test_fetch_citations_from_api_success(self, mock_fetch, handler):
        """Test fetching and parsing citations using unified cache."""
        doi = "10.1145/3025453.3025761"
        
        # Mock API response with references
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Test Paper",
            "reference": [
                {
                    "DOI": "10.1234/test1",
                    "article-title": "Reference 1",
                    "author": "Smith, J.",
                    "year": "2020",
                    "journal-title": "Test Journal",
                    "volume": "10",
                    "issue": "2",
                    "first-page": "100",
                    "last-page": "110",
                },
                {
                    "DOI": "10.1234/test2",
                    "article-title": "Reference 2",
                    "author": "Doe, J.",
                    "year": "2021",
                    "journal-title": "Another Journal",
                    "volume": "20",
                }
            ]
        }
        
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert citations is not None
        assert len(citations) == 2
        assert citations[0].doi == "10.1234/test1"
        assert citations[1].doi == "10.1234/test2"
        assert not cache_hit  # First fetch should not be from cache

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_citations_from_api_no_references(self, mock_fetch, handler):
        """Test fetching when paper has no references."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Test Paper",
            "reference": []
        }
        
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert citations is not None
        assert len(citations) == 0
        assert not cache_hit

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_citations_from_api_not_found(self, mock_fetch, handler):
        """Test fetching when DOI not found."""
        doi = "10.1234/nonexistent"
        
        mock_fetch.return_value = None
        
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert citations == []
        assert not cache_hit

    def test_extract_citations(self, handler):
        """Test extracting Citation objects from API data."""
        api_data = {
            "reference": [
                {
                    "DOI": "10.1234/test1",
                    "article-title": "Reference 1: Complete Metadata",
                    "author": "Smith, J.",
                    "year": "2020",
                    "journal-title": "Test Journal",
                    "volume": "10",
                    "issue": "2",
                    "first-page": "100",
                    "last-page": "110",
                    "publisher": "Test Publisher",
                },
                {
                    "unstructured": "Reference without structure but with author and year",
                    "author": "Doe, J.",
                    "year": "2021",
                },
                {
                    "article-title": "Reference 3: Minimal Metadata",
                    "year": "2019",
                    "journal-title": "Another Journal",
                }
            ]
        }
        
        citations = handler._extract_citations(api_data)
        
        assert len(citations) == 3
        assert isinstance(citations[0], Citation)
        assert isinstance(citations[1], Citation)
        assert isinstance(citations[2], Citation)
        assert citations[0].doi == "10.1234/test1"
        assert citations[0].title == "Reference 1: Complete Metadata"
        assert citations[0].extraction_method == "crossref"
        assert citations[1].raw_text == "Reference without structure but with author and year"
        assert citations[2].journal == "Another Journal"
        assert citations[2].doi is None

    def test_parse_reference_complete(self, handler):
        """Test parsing reference with all fields."""
        ref = {
            "DOI": "10.1234/TEST",
            "article-title": "Complete Reference",
            "author": "Smith, J.",
            "year": "2020",
            "journal-title": "Test Journal",
            "volume": "10",
            "issue": "2",
            "first-page": "100",
            "last-page": "110",
            "publisher": "Test Publisher",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation is not None
        assert citation.doi == "10.1234/test"  # Normalized to lowercase
        assert citation.title == "Complete Reference"
        assert citation.authors == ["Smith, J."]
        assert citation.year == 2020
        assert citation.journal == "Test Journal"
        assert citation.volume == "10"
        assert citation.issue == "2"
        assert citation.pages == "100-110"
        assert citation.publisher == "Test Publisher"
        assert citation.raw_text is None  # No unstructured field
        # Confidence should be high with all fields
        assert citation.confidence > 0.9

    def test_parse_reference_minimal(self, handler):
        """Test parsing reference with minimal fields."""
        ref = {
            "unstructured": "Minimal reference without structure",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation is not None
        assert citation.doi is None
        assert citation.title == "Minimal reference without structure"
        assert citation.authors == []
        assert citation.year is None

    def test_parse_reference_only_first_page(self, handler):
        """Test parsing reference with only first page."""
        ref = {
            "article-title": "Some Paper",
            "first-page": "50",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.pages == "50"

    def test_parse_reference_container_title_fallback(self, handler):
        """Test journal extraction falls back to container-title."""
        ref = {
            "article-title": "Paper Title",
            "container-title": "Container Journal",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.journal == "Container Journal"

    def test_parse_reference_doi_normalization(self, handler):
        """Test DOI is normalized to lowercase."""
        ref = {
            "DOI": "10.1234/UPPERCASE",
            "article-title": "Paper",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.doi == "10.1234/uppercase"

    def test_parse_reference_year_extraction(self, handler):
        """Test year extraction from various formats."""
        # Valid year
        ref1 = {"article-title": "Paper", "year": "2020"}
        citation1 = handler._parse_reference(ref1, idx=0)
        assert citation1.year == 2020
        
        # Invalid year
        ref2 = {"article-title": "Paper", "year": "not_a_year"}
        citation2 = handler._parse_reference(ref2, idx=0)
        assert citation2.year is None
        
        # Missing year
        ref3 = {"article-title": "Paper"}
        citation3 = handler._parse_reference(ref3, idx=0)
        assert citation3.year is None

    def test_calculate_confidence_perfect_score(self, handler):
        """Test confidence calculation with all fields."""
        confidence = handler._calculate_confidence(
            doi="10.1234/test",
            title="A complete and meaningful title",
            year=2020,
            authors=["Author, A."]
        )
        
        # Base 0.5 + DOI 0.35 + Title 0.1 + Year 0.05 = 1.0
        assert confidence == 1.0

    def test_calculate_confidence_no_doi(self, handler):
        """Test confidence without DOI."""
        confidence = handler._calculate_confidence(
            doi=None,
            title="A meaningful title",
            year=2020,
            authors=["Author, A."]
        )
        
        # Base 0.5 + Title 0.1 + Year 0.05 = 0.65
        assert confidence == 0.65

    def test_calculate_confidence_short_title(self, handler):
        """Test confidence with short title."""
        confidence = handler._calculate_confidence(
            doi="10.1234/test",
            title="Short",
            year=2020,
            authors=[]
        )
        
        # Base 0.5 + DOI 0.35 + Year 0.05 = 0.9 (title too short)
        assert confidence == 0.9

    def test_calculate_confidence_only_base(self, handler):
        """Test minimum confidence with no extra fields."""
        confidence = handler._calculate_confidence(
            doi=None,
            title=None,
            year=None,
            authors=[]
        )
        
        # Only base 0.5
        assert confidence == 0.5

    def test_calculate_confidence_capped_at_1(self, handler):
        """Test confidence is capped at 1.0."""
        # Try to add more than possible
        confidence = handler._calculate_confidence(
            doi="10.1234/test",
            title="A very meaningful and long title here",
            year=2020,
            authors=["Author, A.", "Author, B."]
        )
        
        # Should not exceed 1.0
        assert confidence <= 1.0
        assert confidence == 1.0

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_and_parse_citations_success(self, mock_fetch, handler):
        """Test complete fetch and parse flow."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "reference": [
                {
                    "DOI": "10.1234/test1",
                    "article-title": "Reference 1",
                    "year": "2020",
                },
                {
                    "unstructured": "Reference without DOI",
                    "year": "2021",
                }
            ]
        }
        
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert len(citations) == 2
        assert cache_hit is False  # First call, not cached
        assert all(isinstance(c, Citation) for c in citations)

    def test_extract_citations_missing_references_key(self, handler):
        """Test parsing handles invalid data gracefully."""
        ref = {
            "year": "invalid_year",
            "volume": None,
            "issue": None,
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation is not None
        assert citation.year is None
        assert citation.volume is None
        assert citation.issue is None
        # Should still calculate confidence based on empty title (10+ chars = no bonus)
        assert citation.confidence >= 0.5

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_fetch_citations_handles_malformed_reference(self, mock_fetch, handler):
        """Test fetch_and_parse_citations handles malformed references gracefully."""
        doi = "10.1145/3025453.3025761"
        
        mock_fetch.return_value = {
            "DOI": doi,
            "reference": [
                {"article-title": "Valid reference"},
                {"year": "not_a_number_for_year_parsing"},  # Malformed
                {"article-title": "Another valid reference"},
            ]
        }
        
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert citations is not None
        assert len(citations) == 3
        assert not cache_hit

    def test_extract_citations_empty_reference_list(self, handler):
        """Test extracting from empty reference list."""
        api_data = {"reference": []}
        
        citations = handler._extract_citations(api_data)
        
        assert citations == []

    def test_extract_citations_missing_references_key(self, handler):
        """Test extracting when reference key is missing."""
        api_data = {"other_key": "value"}
        
        citations = handler._extract_citations(api_data)
        
        assert citations == []

    def test_parse_reference_pages_both_set(self, handler):
        """Test pages formatting with both first and last page."""
        ref = {
            "article-title": "Paper",
            "first-page": "123",
            "last-page": "456",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.pages == "123-456"

    def test_parse_reference_pages_only_last_ignored(self, handler):
        """Test that last page without first page is not included."""
        ref = {
            "article-title": "Paper",
            "last-page": "456",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.pages is None

    def test_parse_reference_whitespace_stripped(self, handler):
        """Test that whitespace is properly stripped from fields."""
        ref = {
            "article-title": "  Title with spaces  ",
            "journal-title": "  Journal  ",
            "author": "  Smith, J.  ",
        }
        
        citation = handler._parse_reference(ref, idx=0)
        
        assert citation.title == "Title with spaces"
        assert citation.journal == "Journal"
        assert citation.authors == ["Smith, J."]

    def test_calculate_confidence_with_empty_authors(self, handler):
        """Test confidence calculation with empty authors list."""
        confidence = handler._calculate_confidence(
            doi="10.1234/test",
            title="Title",
            year=2020,
            authors=[]
        )
        
        assert confidence > 0.5

    def test_calculate_confidence_with_short_author_name(self, handler):
        """Test confidence with very short author name."""
        confidence = handler._calculate_confidence(
            doi=None,
            title="Meaningful title here",
            year=None,
            authors=["A"]  # Single character
        )
        
        assert confidence == 0.6  # Base 0.5 + Title 0.1


class TestCrossrefCitationIntegration:
    """Integration tests for citation extraction workflows."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, cache_dir):
        """Create a handler instance."""
        return CrossrefHandler(cache_dir=cache_dir)

    @patch("paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler.CrossrefHandler._fetch_from_api")
    def test_complete_citation_extraction_workflow(self, mock_fetch, handler):
        """Test complete workflow from API response to Citation objects."""
        doi = "10.1145/3025453.3025761"
        
        # Realistic Crossref API response
        mock_fetch.return_value = {
            "DOI": doi,
            "title": "Original Paper",
            "reference": [
                {
                    "DOI": "10.1016/j.jss.2015.11.016",
                    "article-title": "Software testing: a research travelogue",
                    "author": "Bertolino, A.",
                    "year": "2007",
                    "journal-title": "Future Generation Computer Systems",
                    "volume": "29",
                    "issue": "3",
                    "first-page": "876",
                    "last-page": "885",
                    "publisher": "Elsevier",
                },
                {
                    "unstructured": "Kent Beck et al. (2001). Extreme Programming Explained: Embrace Change.",
                },
            ]
        }
        
        # Test fetch with unified cache
        citations, cache_hit = handler.fetch_citations(doi)
        
        assert len(citations) == 2
        assert not cache_hit  # First fetch should not be from cache
        
        # First citation should have full metadata
        first = citations[0]
        assert first.doi == "10.1016/j.jss.2015.11.016"
        assert first.title == "Software testing: a research travelogue"
        assert first.year == 2007
        assert first.confidence > 0.9  # High confidence with DOI, title, year
        
        # Second citation minimal
        second = citations[1]
        assert second.doi is None
        assert "Extreme Programming Explained" in second.title
        # Has title that's > 10 chars, so gets base 0.5 + title 0.1 = 0.6
        assert second.confidence >= 0.5
