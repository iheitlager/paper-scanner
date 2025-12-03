"""
Tests for database reference insertion methods.

Tests cover:
- Inserting references into database
- Citation edge creation
- Citation metadata tracking
- Retrieval of references for papers
- Error handling
"""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from paper_scanner.web.database import DatabaseManager
from paper_scanner.web.exceptions import DatabaseException


@pytest.fixture
def db_manager():
    """Create a DatabaseManager instance for testing."""
    return DatabaseManager("postgresql://localhost/test")


@pytest.fixture
def sample_references_data():
    """Sample references data extracted from Claude."""
    return {
        "total_references": 2,
        "extraction_date": "2025-12-02T10:00:00Z",
        "source_paper": {
            "citekey": "AuthorA2025",
            "title": "Sample Paper",
            "authors": ["Author, A"],
            "year": "2025"
        },
        "references": [
            {
                "id": 1,
                "citekey": "SmithJ2023",
                "reference_type": "journal_article",
                "authors": [
                    {"last_name": "Smith", "first_name": "John", "initials": "J", "order": 1}
                ],
                "year": "2023",
                "title": "A study on innovation",
                "source": {
                    "type": "journal",
                    "name": "Journal of Technology",
                    "volume": "45",
                    "issue": "3",
                    "pages": {"start": "123", "end": "145", "range": "123-145"},
                    "publisher": "Tech Press",
                    "location": "New York",
                    "isbn": None,
                    "editors": None,
                    "edition": None
                },
                "identifiers": {
                    "doi": "10.1234/jtech.2023.45.3",
                    "url": None,
                    "arxiv": None,
                    "ssrn": None
                },
                "raw_citation": "Smith, J. (2023). A study on innovation. Journal of Technology, 45(3), 123-145.",
                "notes": None
            },
            {
                "id": 2,
                "citekey": "DoeA2022",
                "reference_type": "journal_article",
                "authors": [
                    {"last_name": "Doe", "first_name": "Alice", "initials": "A", "order": 1},
                    {"last_name": "Jones", "first_name": "Bob", "initials": "B", "order": 2}
                ],
                "year": "2022",
                "title": "Digital transformation",
                "source": {
                    "type": "journal",
                    "name": "IT Management Review",
                    "volume": "12",
                    "issue": "1",
                    "pages": {"start": "34", "end": "56", "range": "34-56"},
                    "publisher": None,
                    "location": None,
                    "isbn": None,
                    "editors": None,
                    "edition": None
                },
                "identifiers": {
                    "doi": None,
                    "url": "https://example.com/article",
                    "arxiv": None,
                    "ssrn": None
                },
                "raw_citation": "Doe, A., & Jones, B. (2022). Digital transformation. IT Management Review, 12(1), 34-56.",
                "notes": None
            }
        ],
        "parsing_metadata": {
            "successfully_parsed": 2,
            "parsing_issues": [],
            "citation_style": "APA"
        }
    }


class TestInsertReferences:
    """Test insert_references method."""

    def test_insert_references_success(self, db_manager, sample_references_data):
        """Test successful reference insertion."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock sequential ID returns for references
        mock_cursor.fetchone.side_effect = [(1,), (2,)]

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.insert_references(source_paper_id=100, references_data=sample_references_data)

            assert len(result) == 2
            assert result == [1, 2]
            mock_conn.commit.assert_called_once()

    def test_insert_references_empty_data(self, db_manager):
        """Test insertion with empty references data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.insert_references(source_paper_id=100, references_data={"references": []})

            assert result == []
            mock_conn.commit.assert_called_once()

    def test_insert_references_invalid_data_structure(self, db_manager):
        """Test insertion with invalid data structure."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.insert_references(source_paper_id=100, references_data={"invalid": "data"})

            assert result == []

    def test_insert_references_database_error(self, db_manager, sample_references_data):
        """Test database error handling during insertion."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                db_manager.insert_references(source_paper_id=100, references_data=sample_references_data)

            mock_conn.rollback.assert_called_once()

    def test_insert_references_creates_citation_edges(self, db_manager, sample_references_data):
        """Test that citation edges are created linking papers to references."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock sequential ID returns
        mock_cursor.fetchone.side_effect = [(1,), (2,)]

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            db_manager.insert_references(source_paper_id=100, references_data=sample_references_data)

            # Verify citation_edges INSERT was called
            call_count = mock_cursor.execute.call_count
            # Should have: 2 reference inserts + 2 citation_edge inserts + 2 metadata inserts
            assert call_count >= 4  # At least references and citation edges

    def test_insert_references_with_parsing_issues(self, db_manager):
        """Test reference insertion with parsing issues metadata."""
        data_with_issues = {
            "references": [
                {
                    "id": 1,
                    "citekey": "Test2023",
                    "reference_type": "article",
                    "authors": [{"last_name": "Test"}],
                    "year": "2023",
                    "title": "Test",
                    "source": {"type": "journal", "name": "Test Journal"},
                    "identifiers": {},
                    "raw_citation": "Test citation",
                    "notes": None
                }
            ],
            "parsing_metadata": {
                "successfully_parsed": 1,
                "parsing_issues": [
                    {"reference_id": 1, "issue_description": "Missing publisher"}
                ]
            }
        }

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(1,)]

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.insert_references(source_paper_id=100, references_data=data_with_issues)

            assert len(result) == 1
            mock_conn.commit.assert_called_once()


class TestGetReferencesForPaper:
    """Test get_references_for_paper method."""

    def test_get_references_success(self, db_manager):
        """Test successful reference retrieval."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock RealDictCursor behavior
        mock_refs = [
            {
                "id": 1,
                "source_paper_id": 100,
                "citekey": "SmithJ2023",
                "title": "A study on innovation",
                "year": "2023",
                "doi": "10.1234/test",
                "parsing_status": "success",
                "notes": None
            },
            {
                "id": 2,
                "source_paper_id": 100,
                "citekey": "DoeA2022",
                "title": "Digital transformation",
                "year": "2022",
                "doi": None,
                "parsing_status": "success",
                "notes": None
            }
        ]
        mock_cursor.fetchall.return_value = mock_refs

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.get_references_for_paper(paper_id=100)

            assert len(result) == 2
            assert result[0]["citekey"] == "SmithJ2023"
            assert result[1]["citekey"] == "DoeA2022"

    def test_get_references_empty(self, db_manager):
        """Test retrieval when no references exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.get_references_for_paper(paper_id=100)

            assert result == []

    def test_get_references_database_error(self, db_manager):
        """Test error handling during reference retrieval."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                db_manager.get_references_for_paper(paper_id=100)

    def test_get_references_includes_metadata(self, db_manager):
        """Test that retrieved references include parsing metadata."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_refs = [
            {
                "id": 1,
                "citekey": "SmithJ2023",
                "parsing_status": "warning",
                "parsing_issues": "Missing publisher info",
                "notes": "See original source"
            }
        ]
        mock_cursor.fetchall.return_value = mock_refs

        with patch.object(db_manager, "get_connection", return_value=mock_conn):
            result = db_manager.get_references_for_paper(paper_id=100)

            assert len(result) == 1
            assert result[0]["parsing_status"] == "warning"
            assert result[0]["parsing_issues"] == "Missing publisher info"
            assert result[0]["notes"] == "See original source"
