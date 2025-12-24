"""
Unit tests for ManualHandler and BibtexParser.
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from paper_scanner.core.cache import JSONFileCache
from paper_scanner.core.enum import CitationDirection
from paper_scanner.core.doi import DOI
from paper_scanner.tools.fetchers.fetcher_handlers.bibtex_parser import (
    BibtexParser,
    BibtexParseError,
)
from paper_scanner.tools.fetchers.fetcher_handlers.manual_handler import ManualHandler


class TestBibtexParser:
    """Test bibtex parsing functionality."""

    @pytest.fixture
    def temp_bibtex(self):
        """Create temporary bibtex file."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parse_valid_entry(self, temp_bibtex):
        """Test parsing valid bibtex entry."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Smith2023,
  author = {Smith, John and Doe, Jane},
  title = {A Great Paper},
  year = {2023},
  journal = {Nature},
  doi = {10.1234/example},
  abstract = {This is an abstract},
  keywords = {keyword1, keyword2, keyword3},
  cites = {10.1111/ref1, 10.2222/ref2},
  citedby = {10.3333/citing1},
  lastchecked = {2024-12-24}
}
        """
        )

        entries, skipped = BibtexParser.parse_file(bibtex_file)

        assert len(entries) == 1
        assert len(skipped) == 0

        entry = entries[0]
        assert entry["doi"] == "10.1234/example"
        assert entry["title"] == "A Great Paper"
        assert entry["year"] == 2023
        assert entry["journal"] == "Nature"
        assert entry["abstract"] == "This is an abstract"
        assert len(entry["keywords"]) == 3
        assert entry["lastchecked"] == "2024-12-24"
        assert len(entry["authors"]) == 2

    def test_parse_missing_required_field(self, temp_bibtex):
        """Test that entries missing required fields are skipped."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Smith2023,
  title = {Paper Without Abstract},
  year = {2023},
  doi = {10.1234/example},
  keywords = {a, b}
}

@article{Jones2023,
  title = {Complete Paper},
  year = {2023},
  doi = {10.5555/valid},
  abstract = {Valid abstract},
  keywords = {x, y}
}
        """
        )

        entries, skipped = BibtexParser.parse_file(bibtex_file)

        assert len(entries) == 1
        assert len(skipped) == 1
        assert "Smith2023" in skipped[0]

    def test_parse_citation_fields(self, temp_bibtex):
        """Test parsing cites and citedby fields."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Main2023,
  author = {Smith, John},
  title = {Main Paper},
  year = {2023},
  doi = {10.1234/main},
  abstract = {Abstract},
  keywords = {test},
  cites = {10.1111/ref1, 10.2222/ref2, 10.3333/ref3},
  citedby = {10.4444/citing1, 10.5555/citing2}
}
        """
        )

        entries, _ = BibtexParser.parse_file(bibtex_file)

        assert len(entries) == 1
        entry = entries[0]

        # Check citations (stored as dicts)
        backward = [c for c in entry["citations"] if c.get("direction") == "backward"]
        forward = [c for c in entry["citations"] if c.get("direction") == "forward"]

        assert len(backward) == 3
        assert len(forward) == 2
        assert backward[0].get("extraction_method") == "manual"
        assert backward[0].get("confidence") == 1.0

    def test_parse_citedbycount(self, temp_bibtex):
        """Test citedbycount calculation."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Test1,
  author = {A},
  title = {Paper 1},
  year = {2023},
  doi = {10.1/test1},
  abstract = {Abstract},
  keywords = {test},
  citedby = {10.1/c1, 10.2/c2, 10.3/c3}
}

@article{Test2,
  author = {B},
  title = {Paper 2},
  year = {2023},
  doi = {10.2/test2},
  abstract = {Abstract},
  keywords = {test},
  citedby = {10.1/c1},
  citedbycount = {10}
}
        """
        )

        entries, _ = BibtexParser.parse_file(bibtex_file)

        # Paper 1: should calculate from citedby
        assert entries[0]["citedbycount"] == 3

        # Paper 2: should use provided value
        assert entries[1]["citedbycount"] == 10

    def test_parse_empty_citations(self, temp_bibtex):
        """Test handling of empty citation fields."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Test,
  author = {A},
  title = {Paper},
  year = {2023},
  doi = {10.1/test},
  abstract = {Abstract},
  keywords = {test}
}
        """
        )

        entries, _ = BibtexParser.parse_file(bibtex_file)

        assert len(entries) == 1
        assert len(entries[0]["citations"]) == 0

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file."""
        with pytest.raises(BibtexParseError):
            BibtexParser.parse_file(Path("/nonexistent/file.bib"))

    def test_parse_doi_field_formats(self, temp_bibtex):
        """Test different DOI field formats (CSV and braces)."""
        bibtex_file = temp_bibtex / "test.bib"
        bibtex_file.write_text(
            """
@article{Test1,
  author = {A},
  title = {Paper 1},
  year = {2023},
  doi = {10.1/test1},
  abstract = {Abstract},
  keywords = {test},
  cites = {10.1/a, 10.2/b}
}

@article{Test2,
  author = {B},
  title = {Paper 2},
  year = {2023},
  doi = {10.2/test2},
  abstract = {Abstract},
  keywords = {test},
  citedby = {10.3/c, 10.4/d}
}
        """
        )

        entries, _ = BibtexParser.parse_file(bibtex_file)

        assert len(entries[0]["citations"]) == 2
        assert len(entries[1]["citations"]) == 2


class TestManualHandler:
    """Test ManualHandler functionality."""

    @pytest.fixture
    def handler_with_cache(self):
        """Create handler with temporary cache."""
        with TemporaryDirectory() as tmpdir:
            handler = ManualHandler(cache_dir=Path(tmpdir))
            yield handler

    def test_handler_name(self, handler_with_cache):
        """Test handler returns correct name."""
        assert handler_with_cache.name == "manual"

    def test_fetch_from_cache_hit(self, handler_with_cache):
        """Test fetching with cache hit via fetch_metadata."""
        doi = "10.1234/test"
        test_data = {
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": ["Smith"],
        }

        handler_with_cache._jsoncache.set(doi, test_data)

        # fetch_metadata retrieves cached data
        result, _ = handler_with_cache.fetch_metadata(doi)

        assert result is not None
        assert result["title"] == "Test Paper"

    def test_fetch_from_cache_miss(self, handler_with_cache):
        """Test fetching with cache miss."""
        result = handler_with_cache._fetch_from_api("10.9999/nonexistent")
        assert result is None

    def test_extract_methods(self, handler_with_cache):
        """Test extraction methods return cached values."""
        api_data = {
            "title": "Title",
            "abstract": "Abstract",
            "authors": ["Author1", "Author2"],
            "keywords": ["kw1", "kw2"],
            "topics": ["topic1"],
            "paper_type": "journal_article",
            "year": 2023,
            "journal": "Nature",
            "url": "https://example.com",
            "isbn": "123456",
            "issn": "789012",
            "oa_status": "open",
            "source_key": "key123",
            "citations": [],
            "download_url": "https://pdf.example.com",
        }

        assert handler_with_cache._extract_title(api_data) == "Title"
        assert handler_with_cache._extract_abstract(api_data) == "Abstract"
        assert len(handler_with_cache._extract_authors(api_data)) == 2
        assert len(handler_with_cache._extract_keywords(api_data)) == 2
        assert len(handler_with_cache._extract_topics(api_data)) == 1
        assert handler_with_cache._extract_paper_type(api_data) == "journal_article"
        assert handler_with_cache._extract_year(api_data) == 2023
        assert handler_with_cache._extract_journal(api_data) == "Nature"
        assert handler_with_cache._extract_url(api_data) == "https://example.com"
        assert handler_with_cache._extract_isbn(api_data) == "123456"
        assert handler_with_cache._extract_issn(api_data) == "789012"
        assert handler_with_cache._extract_oa_status(api_data) == "open"
        assert handler_with_cache._extract_source_key(api_data) == "key123"
        assert handler_with_cache._extract_citations(api_data) == []
        assert handler_with_cache._find_download_url(api_data) == "https://pdf.example.com"

    def test_extract_missing_fields(self, handler_with_cache):
        """Test extraction methods handle missing fields gracefully."""
        api_data = {}

        assert handler_with_cache._extract_title(api_data) is None
        assert handler_with_cache._extract_abstract(api_data) is None
        assert handler_with_cache._extract_authors(api_data) == []
        assert handler_with_cache._extract_keywords(api_data) == []


class TestBibtexParserIntegration:
    """Integration tests for parser with manual handler cache."""

    def test_parse_and_cache_workflow(self):
        """Test full workflow: parse bibtex, create handler, cache data."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create bibtex file
            bibtex_file = tmpdir_path / "papers.bib"
            bibtex_file.write_text(
                """
@article{Smith2023,
  author = {Smith, John},
  title = {Machine Learning Applications},
  year = {2023},
  doi = {10.1234/ml.2023},
  journal = {AI Review},
  abstract = {A comprehensive review of ML applications},
  keywords = {machine learning, AI, applications},
  cites = {10.1111/ml1, 10.2222/ml2},
  citedby = {10.3333/citing1},
  citedbycount = {5},
  lastchecked = {2024-12-24}
}
            """
            )

            # Parse bibtex
            entries, skipped = BibtexParser.parse_file(bibtex_file)
            assert len(entries) == 1
            assert len(skipped) == 0

            # Create handler and cache entry
            handler = ManualHandler(cache_dir=tmpdir_path)
            entry = entries[0]
            handler._jsoncache.set(entry["doi"], entry)

            # Fetch via fetch_metadata which retrieves cached data
            fetched_dict, _ = handler.fetch_metadata(entry["doi"])
            assert fetched_dict is not None
            assert fetched_dict["title"] == "Machine Learning Applications"
            assert fetched_dict["year"] == 2023
            assert len(fetched_dict["citations"]) == 3  # 2 backward + 1 forward

