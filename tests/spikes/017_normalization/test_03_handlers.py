"""
Phase 3 Spike Tests: Handler Integration with Normalizer

Tests that API fetcher handlers (Crossref, OpenAlex) properly integrate with
the Normalizer class for consistent field normalization.

Focus Areas:
- Handler metadata extraction with Normalizer integration
- Field normalization consistency across handlers
- Author parsing and normalization
- Title, abstract, journal normalization
- Keyword extraction and normalization
"""

from unittest.mock import MagicMock

import pytest

from paper_scanner.core.normalization import Normalizer
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import CrossrefHandler
from paper_scanner.tools.fetchers.fetcher_handlers.openalex_handler import OpenAlexHandler


class TestCrossrefHandlerWithNormalizer:
    """Test Crossref handler integration with Normalizer."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a Crossref handler with mocked cache."""
        handler = CrossrefHandler(cache_dir=tmp_path)
        handler._jsoncache = MagicMock()
        return handler

    def test_crossref_title_extraction_and_normalization(self, handler):
        """Test that Crossref title extraction returns raw value, later normalized."""
        api_data = {
            "title": ["ALL CAPS TITLE WITH excessive   spacing"],
            "DOI": "10.1234/test",
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test Journal"],
            "abstract": "Test abstract",
        }

        # Extract raw title (from list)
        title = handler._extract_title(api_data)
        assert title == "ALL CAPS TITLE WITH excessive   spacing"

        # Verify Normalizer would titlecase and collapse whitespace
        normalized_title = Normalizer.normalize_title(title)
        assert normalized_title == "All Caps Title with Excessive Spacing"

    def test_crossref_abstract_extraction_with_markup(self, handler):
        """Test that Crossref abstract handles markup and normalization."""
        api_data = {
            "abstract": "This is a test <i>abstract</i> with <b>HTML</b> tags.",
            "DOI": "10.1234/test",
            "title": ["Test"],
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test Journal"],
        }

        # Extract abstract (should clean markup)
        abstract = handler._extract_abstract(api_data)
        assert "<" not in abstract
        assert "abstract" in abstract.lower()

        # Verify Normalizer handles it
        normalized = Normalizer.normalize_abstract(abstract)
        assert isinstance(normalized, str)

    def test_crossref_authors_extraction_and_normalization(self, handler):
        """Test that Crossref author extraction preserves properly formatted author objects."""
        api_data = {
            "author": [
                {"given": "john", "family": "DOE"},
                {"given": "JANE", "family": "smith"},
            ],
            "DOI": "10.1234/test",
            "title": ["Test"],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test Journal"],
            "abstract": "Test",
        }

        # Extract authors (as Author objects)
        authors = handler._extract_authors(api_data)
        assert len(authors) == 2
        assert authors[0].full_name == "john DOE"
        assert authors[1].full_name == "JANE smith"

        # Handler creates properly formed Author objects for the Paper model
        # No string conversion needed for the handler pipeline

    def test_crossref_journal_extraction_and_normalization(self, handler):
        """Test that Crossref journal extraction is normalized."""
        api_data = {
            "container-title": ["nature JOURNAL   of Science"],
            "DOI": "10.1234/test",
            "title": ["Test"],
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "abstract": "Test",
        }

        # Extract raw journal
        journal = handler._extract_journal(api_data)
        assert journal == "nature JOURNAL   of Science"

        # Verify Normalizer would titlecase and collapse whitespace
        normalized_journal = Normalizer.normalize_journal(journal)
        assert "Nature" in normalized_journal
        assert "Journal" in normalized_journal

    def test_crossref_keywords_extraction(self, handler):
        """Test that Crossref keywords (subjects) are extracted and normalized."""
        api_data = {
            "subject": ["machine LEARNING", "DEEP   learning", "artificial INTELLIGENCE"],
            "DOI": "10.1234/test",
            "title": ["Test"],
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test Journal"],
            "abstract": "Test",
        }

        # Extract keywords
        keywords = handler._extract_keywords(api_data)
        assert len(keywords) == 3
        assert "machine LEARNING" in keywords

        # Verify Normalizer would titlecase
        normalized_keywords = Normalizer.normalize_keywords(keywords)
        assert len(normalized_keywords) == 3


class TestOpenAlexHandlerWithNormalizer:
    """Test OpenAlex handler integration with Normalizer."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create an OpenAlex handler with mocked cache."""
        handler = OpenAlexHandler(cache_dir=tmp_path)
        handler._jsoncache = MagicMock()
        return handler

    def test_openalex_title_extraction(self, handler):
        """Test that OpenAlex title extraction returns raw value."""
        api_data = {
            "title": "MACHINE LEARNING for NATURAL LANGUAGE processing",
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract raw title
        title = handler._extract_title(api_data)
        assert title == "MACHINE LEARNING for NATURAL LANGUAGE processing"

        # Verify Normalizer would titlecase
        normalized_title = Normalizer.normalize_title(title)
        assert "Machine" in normalized_title
        assert "Learning" in normalized_title

    def test_openalex_abstract_reconstruction(self, handler):
        """Test that OpenAlex inverted abstract is reconstructed and normalized."""
        api_data = {
            "abstract_inverted_index": {
                "This": [0],
                "is": [1],
                "a": [2],
                "test": [3],
            },
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "title": "Test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract abstract from inverted index
        abstract = handler._extract_abstract(api_data)
        assert abstract is not None
        assert "test" in abstract.lower()

        # Verify Normalizer works with reconstructed abstract
        normalized_abstract = Normalizer.normalize_abstract(abstract)
        assert isinstance(normalized_abstract, str)

    def test_openalex_authors_extraction_and_normalization(self, handler):
        """Test that OpenAlex author extraction works correctly with handler."""
        api_data = {
            "authorships": [
                {
                    "author": {"display_name": "john smith"},
                    "institutions": [{"display_name": "MIT"}],
                },
                {
                    "author": {"display_name": "JANE doe"},
                    "institutions": [{"display_name": "Stanford University"}],
                },
            ],
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "title": "Test",
            "type": "article",
            "publication_year": 2024,
        }

        # Extract authors (as Author objects)
        authors = handler._extract_authors(api_data)
        assert len(authors) == 2
        assert authors[0].full_name == "john smith"
        assert authors[1].full_name == "JANE doe"

        # Handler creates properly formed Author objects for the Paper model

    def test_openalex_keywords_from_concepts(self, handler):
        """Test that OpenAlex concepts are extracted as keywords and normalized."""
        api_data = {
            "concepts": [
                {"display_name": "MACHINE learning", "score": 0.8},
                {"display_name": "NEURAL networks", "score": 0.7},
                {"display_name": "low relevance topic", "score": 0.1},
            ],
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "title": "Test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract keywords (score > 0.3)
        keywords = handler._extract_keywords(api_data)
        assert len(keywords) == 2
        assert "MACHINE learning" in keywords
        assert "NEURAL networks" in keywords

        # Verify Normalizer normalizes them
        normalized_keywords = Normalizer.normalize_keywords(keywords)
        assert len(normalized_keywords) == 2

    def test_openalex_journal_extraction(self, handler):
        """Test that OpenAlex journal is extracted and normalized."""
        api_data = {
            "primary_location": {
                "source": {
                    "display_name": "nature MACHINE intelligence   journal",
                }
            },
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "title": "Test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract journal
        journal = handler._extract_journal(api_data)
        assert journal == "nature MACHINE intelligence   journal"

        # Verify Normalizer would titlecase and collapse whitespace
        normalized_journal = Normalizer.normalize_journal(journal)
        assert "Nature" in normalized_journal


class TestHandlerConsistencyWithNormalizer:
    """Test that handlers produce consistent results after Normalizer application."""

    @pytest.fixture
    def crossref_handler(self, tmp_path):
        """Create a Crossref handler."""
        handler = CrossrefHandler(cache_dir=tmp_path)
        handler._jsoncache = MagicMock()
        return handler

    @pytest.fixture
    def openalex_handler(self, tmp_path):
        """Create an OpenAlex handler."""
        handler = OpenAlexHandler(cache_dir=tmp_path)
        handler._jsoncache = MagicMock()
        return handler

    def test_both_handlers_normalize_titles_consistently(
        self, crossref_handler, openalex_handler
    ):
        """Test that both handlers normalize titles to same format."""
        # Same title, different formats from different APIs
        crossref_data = {
            "title": ["MACHINE LEARNING Systems"],
            "DOI": "10.1234/test",
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test"],
            "abstract": "Test",
        }

        openalex_data = {
            "title": "MACHINE LEARNING Systems",
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract and normalize from both
        crossref_title = crossref_handler._extract_title(crossref_data)
        openalex_title = openalex_handler._extract_title(openalex_data)

        # After normalization, should be identical
        norm_crossref = Normalizer.normalize_title(crossref_title)
        norm_openalex = Normalizer.normalize_title(openalex_title)

        assert norm_crossref == norm_openalex
        assert norm_crossref == "Machine Learning Systems"

    def test_both_handlers_normalize_journals_consistently(
        self, crossref_handler, openalex_handler
    ):
        """Test that both handlers normalize journals consistently."""
        crossref_data = {
            "container-title": ["NATURE machine intelligence"],
            "DOI": "10.1234/test",
            "title": ["Test"],
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "abstract": "Test",
        }

        openalex_data = {
            "primary_location": {
                "source": {"display_name": "NATURE machine intelligence"}
            },
            "id": "https://openalex.org/W1234567890",
            "doi": "10.1234/test",
            "title": "Test",
            "type": "article",
            "publication_year": 2024,
            "authorships": [],
        }

        # Extract and normalize from both
        crossref_journal = crossref_handler._extract_journal(crossref_data)
        openalex_journal = openalex_handler._extract_journal(openalex_data)

        # After normalization, should be identical
        norm_crossref = Normalizer.normalize_journal(crossref_journal)
        norm_openalex = Normalizer.normalize_journal(openalex_journal)

        assert norm_crossref == norm_openalex
        assert "Nature" in norm_crossref
        assert "Machine" in norm_crossref

    def test_handler_paper_translation_applies_normalizer(self, crossref_handler):
        """Test that handler's _translate_to_paper applies Normalizer."""
        api_data = {
            "title": ["DEEP learning FOR computer VISION"],
            "DOI": "10.1234/test",
            "author": [
                {"given": "john", "family": "DOE"},
                {"given": "JANE", "family": "smith"},
            ],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["IEEE   TRANSACTIONS   on   NEURAL networks"],
            "abstract": "This   is   a   test   abstract   with   EXCESSIVE   spacing",
            "subject": ["DEEP learning", "COMPUTER vision"],
        }

        # Translate to Paper model (should apply Normalizer internally)
        paper = crossref_handler._translate_to_paper("10.1234/test", api_data)

        # Verify normalization was applied
        assert paper.title == "Deep Learning for Computer Vision"
        assert len(paper.authors) == 2
        # Authors are Author objects, verify the names are properly formatted
        assert paper.authors[0].full_name == "John Doe"
        assert paper.authors[1].full_name == "Jane Smith"
        assert paper.journal == "IEEE Transactions on Neural Networks"
        assert len(paper.keywords) == 2


class TestHandlerEdgeCasesWithNormalizer:
    """Test edge cases in handler extraction and Normalizer integration."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a Crossref handler."""
        handler = CrossrefHandler(cache_dir=tmp_path)
        handler._jsoncache = MagicMock()
        return handler

    def test_empty_title_handling(self, handler):
        """Test that empty titles are handled correctly."""
        api_data = {
            "title": "",
            "DOI": "10.1234/test",
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test"],
            "abstract": "Test",
        }

        title = handler._extract_title(api_data)
        normalized = Normalizer.normalize_title(title) if title else title
        assert normalized == "" or normalized is None

    def test_none_values_in_extraction(self, handler):
        """Test that None values are preserved through extraction."""
        api_data = {
            "title": ["Test"],
            "DOI": "10.1234/test",
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test"],
            "abstract": None,  # Missing abstract
            "subject": None,  # Missing keywords
        }

        abstract = handler._extract_abstract(api_data)
        keywords = handler._extract_keywords(api_data)

        assert abstract is None
        assert keywords == []

    def test_special_characters_in_titles(self, handler):
        """Test that special characters in titles are preserved."""
        api_data = {
            "title": ["Machine Learning & Deep Learning: A Survey"],
            "DOI": "10.1234/test",
            "author": [],
            "type": "journal-article",
            "issued": {"date-parts": [[2024]]},
            "container-title": ["Test"],
            "abstract": "Test",
        }

        title = handler._extract_title(api_data)
        normalized = Normalizer.normalize_title(title)

        assert "&" in normalized or "and" in normalized.lower()
        assert ":" in normalized
