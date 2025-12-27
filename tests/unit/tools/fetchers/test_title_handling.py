"""
Unit tests for title handling across all fetcher handlers.

Tests verify that handlers properly extract titles and apply str.title() formatting
(with some handlers overriding for custom behavior).
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import CrossrefHandler
from paper_scanner.tools.fetchers.fetcher_handlers.openalex_handler import OpenAlexHandler
from paper_scanner.tools.fetchers.fetcher_handlers.semantic_scholar_handler import SemanticScholarHandler
from paper_scanner.tools.fetchers.fetcher_handlers.core_handler import COREHandler
from paper_scanner.tools.fetchers.fetcher_handlers.manual_handler import ManualHandler


class TestBaseFetcherHandlerTitleHandling:
    """Test title extraction in base handler (applies str.title())."""

    @pytest.fixture
    def handler(self):
        """Create Crossref handler to test base title handling."""
        with TemporaryDirectory() as tmpdir:
            # Use Crossref as it directly inherits base behavior
            yield CrossrefHandler(Path(tmpdir))

    def test_extract_title_basic_string(self, handler):
        """Test extracting title from basic string."""
        api_data = {"title": "machine learning for beginners"}
        result = handler._extract_title(api_data)
        # Base class applies title() method
        assert result == "Machine Learning For Beginners"

    def test_extract_title_with_special_characters(self, handler):
        """Test title extraction with special characters and title case."""
        api_data = {"title": "a novel approach to nlp: transformers and attention"}
        result = handler._extract_title(api_data)
        assert result == "A Novel Approach To Nlp: Transformers And Attention"

    def test_extract_title_already_uppercase(self, handler):
        """Test title that is already in uppercase."""
        api_data = {"title": "DEEP NEURAL NETWORKS"}
        result = handler._extract_title(api_data)
        assert result == "Deep Neural Networks"

    def test_extract_title_mixed_case(self, handler):
        """Test title with mixed case input."""
        api_data = {"title": "PyTorch for Computer Vision"}
        result = handler._extract_title(api_data)
        assert result == "Pytorch For Computer Vision"

    def test_extract_title_with_acronyms(self, handler):
        """Test title containing acronyms (note: title() doesn't preserve acronyms)."""
        api_data = {"title": "reinforcement learning with lstm networks"}
        result = handler._extract_title(api_data)
        # title() will lowercase LSTM to Lstm
        assert result == "Reinforcement Learning With Lstm Networks"

    def test_extract_title_empty_string(self, handler):
        """Test with empty title string."""
        api_data = {"title": ""}
        result = handler._extract_title(api_data)
        # Empty string is falsy, so should return empty or apply title() to empty
        assert result == "" or result is None

    def test_extract_title_missing_field(self, handler):
        """Test with missing title field."""
        api_data = {}
        result = handler._extract_title(api_data)
        assert result == "" or result is None

    def test_extract_title_none_value(self, handler):
        """Test with None as title value."""
        api_data = {"title": None}
        result = handler._extract_title(api_data)
        assert result is None

    def test_extract_title_with_newlines(self, handler):
        """Test title with embedded newlines."""
        api_data = {"title": "a long title\nwith multiple\nlines"}
        result = handler._extract_title(api_data)
        # Should apply title() to the raw string with newlines
        assert "A Long Title" in result or result == "A Long Title\nWith Multiple\nLines"

    def test_extract_title_with_html_tags(self, handler):
        """Test title containing HTML-like tags."""
        api_data = {"title": "machine <i>learning</i> algorithms"}
        result = handler._extract_title(api_data)
        # title() doesn't remove HTML, just applies case transformation
        assert result == "Machine <I>Learning</I> Algorithms"


class TestCrossrefHandlerTitleHandling:
    """Test title extraction in Crossref handler (inherits from base, applies str.title())."""

    @pytest.fixture
    def handler(self):
        """Create Crossref handler instance."""
        with TemporaryDirectory() as tmpdir:
            yield CrossrefHandler(Path(tmpdir))

    def test_crossref_title_extraction_basic(self, handler):
        """Test basic title extraction from Crossref-format data."""
        api_data = {
            "title": "the future of artificial intelligence",
            "author": [],
        }
        result = handler._extract_title(api_data)
        # Crossref inherits base behavior: applies title()
        assert result == "The Future Of Artificial Intelligence"

    def test_crossref_title_with_journal_reference(self, handler):
        """Test Crossref title with journal-style capitalization."""
        api_data = {
            "title": "quantum computing: present and future perspectives",
            "journal-title": "Nature",
        }
        result = handler._extract_title(api_data)
        assert result == "Quantum Computing: Present And Future Perspectives"

    def test_crossref_title_empty_list_fallback(self, handler):
        """Test Crossref with title as list (edge case)."""
        api_data = {
            "title": ["machine learning basics", "deep learning"],
            "author": [],
        }
        result = handler._extract_title(api_data)
        # Title is a list, so not a string; title() won't apply
        # Based on code: title.title() if isinstance(title, str) else title
        assert result == ["machine learning basics", "deep learning"] or isinstance(result, list)


class TestOpenAlexHandlerTitleHandling:
    """Test title extraction in OpenAlex handler (inherits from base, applies str.title())."""

    @pytest.fixture
    def handler(self):
        """Create OpenAlex handler instance."""
        with TemporaryDirectory() as tmpdir:
            yield OpenAlexHandler(Path(tmpdir))

    def test_openalex_title_extraction_basic(self, handler):
        """Test basic title extraction from OpenAlex-format data."""
        api_data = {
            "title": "protein folding and structure prediction",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # OpenAlex inherits base behavior: applies title()
        assert result == "Protein Folding And Structure Prediction"

    def test_openalex_title_with_complex_punctuation(self, handler):
        """Test OpenAlex title with complex punctuation."""
        api_data = {
            "title": "deep learning for covid-19 diagnosis: a comprehensive survey",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        assert result == "Deep Learning For Covid-19 Diagnosis: A Comprehensive Survey"

    def test_openalex_title_missing(self, handler):
        """Test OpenAlex with missing title."""
        api_data = {"authors": []}
        result = handler._extract_title(api_data)
        assert result == "" or result is None


class TestSemanticScholarHandlerTitleHandling:
    """Test title extraction in Semantic Scholar handler (custom implementation, uses _clean_title)."""

    @pytest.fixture
    def handler(self):
        """Create Semantic Scholar handler instance."""
        with TemporaryDirectory() as tmpdir:
            yield SemanticScholarHandler(Path(tmpdir))

    def test_semantic_scholar_title_extraction_basic(self, handler):
        """Test basic title extraction from Semantic Scholar data."""
        api_data = {
            "title": "transformer models: attention is all you need",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # Semantic Scholar overrides _extract_title to use _clean_title (preserves case)
        assert result == "transformer models: attention is all you need"

    def test_semantic_scholar_title_preserves_case(self, handler):
        """Test that Semantic Scholar preserves original case (doesn't apply title())."""
        api_data = {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # _clean_title only removes HTML and excess whitespace, preserves case
        assert result == "BERT: Pre-training of Deep Bidirectional Transformers"

    def test_semantic_scholar_title_with_html_tags(self, handler):
        """Test Semantic Scholar title with HTML tags (removed by _clean_title)."""
        api_data = {
            "title": "machine <i>learning</i> basics for <b>beginners</b>",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # _clean_title removes HTML tags
        assert result == "machine learning basics for beginners"

    def test_semantic_scholar_title_with_multiple_spaces(self, handler):
        """Test Semantic Scholar title with multiple spaces."""
        api_data = {
            "title": "deep   learning    with    multiple    spaces",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # _clean_title collapses multiple spaces to single space
        assert result == "deep learning with multiple spaces"

    def test_semantic_scholar_title_with_newlines(self, handler):
        """Test Semantic Scholar title with newlines."""
        api_data = {
            "title": "a title\nwith\nnewlines",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # _clean_title replaces newlines with spaces
        assert result == "a title with newlines"

    def test_semantic_scholar_title_empty(self, handler):
        """Test Semantic Scholar with empty title."""
        api_data = {"title": "", "authors": []}
        result = handler._extract_title(api_data)
        assert result is None

    def test_semantic_scholar_title_missing(self, handler):
        """Test Semantic Scholar with missing title field."""
        api_data = {"authors": []}
        result = handler._extract_title(api_data)
        assert result is None


class TestCOREHandlerTitleHandling:
    """Test title extraction in CORE handler (inherits from base, applies str.title())."""

    @pytest.fixture
    def handler(self):
        """Create CORE handler instance."""
        with TemporaryDirectory() as tmpdir:
            yield COREHandler(Path(tmpdir))

    def test_core_title_extraction_basic(self, handler):
        """Test basic title extraction from CORE data."""
        api_data = {
            "title": "open access research management systems",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # CORE inherits base behavior: applies title()
        assert result == "Open Access Research Management Systems"

    def test_core_title_with_pdf_reference(self, handler):
        """Test CORE title (typically comes with PDF info)."""
        api_data = {
            "title": "pdf content analysis and extraction",
            "downloadUrl": "http://example.com/paper.pdf",
        }
        result = handler._extract_title(api_data)
        assert result == "Pdf Content Analysis And Extraction"

    def test_core_title_missing(self, handler):
        """Test CORE with missing title."""
        api_data = {"downloadUrl": "http://example.com/paper.pdf"}
        result = handler._extract_title(api_data)
        assert result == "" or result is None


class TestManualHandlerTitleHandling:
    """Test title extraction in Manual handler (inherits from base, applies str.title())."""

    @pytest.fixture
    def handler(self):
        """Create Manual handler instance."""
        with TemporaryDirectory() as tmpdir:
            yield ManualHandler(Path(tmpdir))

    def test_manual_handler_title_extraction_basic(self, handler):
        """Test basic title extraction from manually cached data."""
        api_data = {
            "title": "a manually curated research paper",
            "authors": [],
        }
        result = handler._extract_title(api_data)
        # Manual handler inherits base behavior: applies title()
        assert result == "A Manually Curated Research Paper"

    def test_manual_handler_title_from_bibtex(self, handler):
        """Test title extracted from bibtex-sourced data."""
        api_data = {
            "title": "integrating deep learning with classical methods",
            "year": 2023,
        }
        result = handler._extract_title(api_data)
        assert result == "Integrating Deep Learning With Classical Methods"

    def test_manual_handler_title_missing(self, handler):
        """Test Manual handler with missing title."""
        api_data = {"year": 2023, "authors": []}
        result = handler._extract_title(api_data)
        assert result == "" or result is None


class TestTitleHandlingConsistency:
    """Test consistency of title handling across handlers."""

    def test_all_handlers_extract_title_method_exists(self):
        """Verify all handlers have _extract_title method."""
        handlers = [
            BaseFetcherHandler,
            CrossrefHandler,
            OpenAlexHandler,
            SemanticScholarHandler,
            COREHandler,
            ManualHandler,
        ]
        
        for handler_class in handlers:
            assert hasattr(handler_class, "_extract_title"), \
                f"{handler_class.__name__} missing _extract_title method"

    def test_title_extraction_returns_string_or_none(self):
        """Verify all handlers return string or None from _extract_title."""
        with TemporaryDirectory() as tmpdir:
            handlers = [
                CrossrefHandler(Path(tmpdir)),
                OpenAlexHandler(Path(tmpdir)),
                SemanticScholarHandler(Path(tmpdir)),
                COREHandler(Path(tmpdir)),
                ManualHandler(Path(tmpdir)),
            ]
            
            test_data = {"title": "test title"}
            
            for handler in handlers:
                result = handler._extract_title(test_data)
                assert isinstance(result, str) or result is None, \
                    f"{handler.name} returned invalid type: {type(result)}"

    def test_semantic_scholar_differs_from_others(self):
        """Verify Semantic Scholar uses different title handling than base."""
        with TemporaryDirectory() as tmpdir:
            base_handler = CrossrefHandler(Path(tmpdir))  # Use Crossref for base behavior
            s2_handler = SemanticScholarHandler(Path(tmpdir))
            
            # Test with title that should differ
            test_data = {"title": "UPPERCASE lowercase MiXeD"}
            
            base_result = base_handler._extract_title(test_data)
            s2_result = s2_handler._extract_title(test_data)
            
            # Base (Crossref) applies title(), S2 preserves case
            assert base_result == "Uppercase Lowercase Mixed"
            assert s2_result == "UPPERCASE lowercase MiXeD"
            assert base_result != s2_result
