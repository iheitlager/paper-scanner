"""
Unit tests for Manual Handler author serialization/deserialization.

Tests that authors are properly converted from strings (in cache) to Author
objects when constructing Paper models.
"""

import tempfile
from pathlib import Path

import pytest

from paper_scanner.core.models import Author, Paper
from paper_scanner.tools.fetchers.fetcher_handlers.manual_handler import ManualHandler


class TestManualHandlerAuthorSerialization:
    """Test author serialization and deserialization in manual handler."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def handler(self, temp_cache_dir):
        """Create manual handler with temp cache."""
        return ManualHandler(cache_dir=temp_cache_dir)

    def test_authors_as_strings_in_cache(self, handler, temp_cache_dir):
        """Test that cached data with string authors can be used to create Paper."""
        # Simulate cached data with string authors (as stored by BibtexParser)
        cached_data = {
            "doi": "10.1109/tem.2021.3075502",
            "title": "Test Paper",
            "abstract": "Test abstract",
            "authors": [
                "Smith, John",
                "Doe, Jane",
                "Johnson, Bob",
                "Williams, Alice",
            ],
            "year": 2021,
            "journal": "IEEE Transactions",
            "paper_type": "journal_article",
        }

        # Cache the data
        handler._jsoncache.set("10.1109/tem.2021.3075502", cached_data)

        # Retrieve via fetch_metadata
        api_data, _ = handler.fetch_metadata("10.1109/tem.2021.3075502")

        # Should be able to extract and use authors
        assert api_data is not None
        authors = handler._extract_authors(api_data)
        assert isinstance(authors, list)
        assert len(authors) == 4
        assert all(isinstance(a, Author) for a in authors)
        assert authors[0].full_name == "Smith, John"

    def test_extract_authors_returns_list(self, handler):
        """Test that _extract_authors returns a list of Author objects."""
        api_data = {
            "authors": ["Author One", "Author Two"],
        }
        authors = handler._extract_authors(api_data)
        assert isinstance(authors, list)
        assert len(authors) == 2
        assert all(isinstance(a, Author) for a in authors)
        assert authors[0].full_name == "Author One"

    def test_extract_authors_converts_strings_to_author_objects(self, handler):
        """Test that string authors are converted to Author objects for Paper model."""
        api_data = {
            "doi": "10.1234/test",
            "title": "Test",
            "authors": [
                "Smith, John",
                "Doe, Jane",
            ],
            "year": 2021,
        }

        # Handler extracts authors and converts to Author objects
        authors = handler._extract_authors(api_data)
        assert isinstance(authors, list)
        assert all(isinstance(a, Author) for a in authors)
        assert authors[0].full_name == "Smith, John"
        assert authors[0].family_name == "Smith"
        assert authors[0].given_name == "John"

    def test_paper_construction_with_string_authors_fails(self, handler):
        """Test that Paper construction fails if authors are strings."""
        # This demonstrates the bug
        with pytest.raises(Exception) as exc_info:
            Paper(
                cite_key="test2021",
                title="Test Paper",
                authors=["Smith, John", "Doe, Jane"],  # String authors
                year=2021,
            )
        assert "validation error" in str(exc_info.value).lower()

    def test_paper_construction_with_author_objects_succeeds(self):
        """Test that Paper construction succeeds with Author objects."""
        authors = [
            Author(full_name="Smith, John", family_name="Smith"),
            Author(full_name="Doe, Jane", family_name="Doe"),
        ]
        paper = Paper(
            cite_key="test2021",
            title="Test Paper",
            authors=authors,
            year=2021,
        )
        assert len(paper.authors) == 2
        assert paper.authors[0].full_name == "Smith, John"

    def test_manual_handler_should_convert_authors(self, handler, temp_cache_dir):
        """Test that manual handler converts string authors to Author objects."""
        cached_data = {
            "doi": "10.1109/tem.2021.3075502",
            "title": "Test Paper",
            "authors": [
                "Smith, John",
                "Doe, Jane",
                "Johnson, Bob",
                "Williams, Alice",
            ],
            "year": 2021,
            "journal": "IEEE Transactions",
            "paper_type": "journal_article",
        }

        handler._jsoncache.set("10.1109/tem.2021.3075502", cached_data)

        # This should work after the fix
        paper, from_api = handler.fetch_paper("10.1109/tem.2021.3075502")

        assert paper is not None
        assert len(paper.authors) == 4
        assert all(isinstance(a, Author) for a in paper.authors)
        assert paper.authors[0].full_name == "Smith, John"
        assert paper.authors[0].family_name == "Smith"


def _string_to_author(author_str: str) -> Author:
    """
    Convert author string to Author object.

    Handles formats like:
    - "Smith, John" -> family_name="Smith", given_name="John"
    - "John Smith" -> given_name="John", family_name="Smith"
    - "Smith" -> family_name="Smith"
    """
    if not author_str:
        raise ValueError("Author string cannot be empty")

    parts = author_str.strip().split()

    # Try "LastName, FirstName" format
    if "," in author_str:
        name_parts = author_str.split(",")
        family_name = name_parts[0].strip()
        given_name = name_parts[1].strip() if len(name_parts) > 1 else None
        return Author(
            family_name=family_name,
            given_name=given_name,
            full_name=author_str.strip(),
        )

    # Try "FirstName LastName" format
    if len(parts) >= 2:
        given_name = " ".join(parts[:-1])
        family_name = parts[-1]
        return Author(
            family_name=family_name,
            given_name=given_name,
            full_name=author_str.strip(),
        )

    # Single name fallback
    return Author(
        family_name=parts[0],
        full_name=author_str.strip(),
    )
