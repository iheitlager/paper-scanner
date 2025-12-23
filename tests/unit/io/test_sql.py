"""
Unit tests for paper_scanner.io.sql module.

Tests database abstraction layer including connection pooling,
paper/row conversion, and bulk operations.
"""

from unittest.mock import Mock, patch

import pytest

from paper_scanner.core.enum import DiscoveryMethod, PaperType
from paper_scanner.core.models import Author, Discovery, Paper, Screening
from paper_scanner.io.sql import DatabaseConnectionPool, DOIDuplicateHandler, PaperToRowConverter, PaperUploader


@pytest.fixture
def sample_paper():
    """Create a sample Paper model for testing."""
    return Paper(
        id="test-paper-1",
        cite_key="smith2023",
        source_key="source_1",
        title="Test Paper Title",
        abstract="This is a test abstract",
        authors=[
            Author(
                given_name="John",
                family_name="Smith",
                full_name="John Smith",
            ),
            Author(
                given_name="Jane",
                family_name="Doe",
                full_name="Jane Doe",
            ),
        ],
        keywords=["keyword1", "keyword2"],
        topics=["topic1"],
        year=2023,
        journal="Test Journal",
        journal_abbreviation="TJ",
        volume="10",
        number="5",
        pages="1-10",
        paper_type=PaperType.JOURNAL_ARTICLE,
        doi="10.1234/test.doi",
        url="https://example.com/paper",
        discovery=Discovery(
            method=DiscoveryMethod.MANUAL,
            source_database="test_source",
        ),
        screening=Screening(),
        manually_validated=True,
    )


@pytest.fixture
def mock_connection_pool():
    """Mock DatabaseConnectionPool."""
    pool = Mock(spec=DatabaseConnectionPool)
    pool.database_url = "postgresql://localhost/test"
    return pool


class TestDatabaseConnectionPool:
    """Tests for DatabaseConnectionPool class."""

    def test_init(self):
        """Test pool initialization parameters."""
        pool = DatabaseConnectionPool(
            "postgresql://user:pass@localhost:5432/testdb",
            min_connections=2,
            max_connections=10,
        )
        assert pool.database_url == "postgresql://user:pass@localhost:5432/testdb"
        assert pool.min_connections == 2
        assert pool.max_connections == 10

    def test_init_defaults(self):
        """Test pool initialization with default values."""
        pool = DatabaseConnectionPool("postgresql://localhost/testdb")
        assert pool.min_connections == 1
        assert pool.max_connections == 5

    @patch("paper_scanner.io.sql.SimpleConnectionPool")
    def test_initialize(self, mock_pool_class):
        """Test pool initialization."""
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        pool = DatabaseConnectionPool("postgresql://localhost/testdb")
        pool.initialize()

        mock_pool_class.assert_called_once()
        assert pool._pool == mock_pool

    @patch("paper_scanner.io.sql.SimpleConnectionPool")
    def test_close(self, mock_pool_class):
        """Test pool close."""
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        pool = DatabaseConnectionPool("postgresql://localhost/testdb")
        pool.initialize()
        pool.close()

        mock_pool.closeall.assert_called_once()
        assert pool._pool is None

    @patch("paper_scanner.io.sql.SimpleConnectionPool")
    def test_get_connection_not_initialized(self, mock_pool_class):
        """Test get_connection raises when pool not initialized."""
        pool = DatabaseConnectionPool("postgresql://localhost/testdb")

        with pytest.raises(RuntimeError, match="not initialized"):
            with pool.get_connection():
                pass

    @patch("paper_scanner.io.sql.SimpleConnectionPool")
    def test_get_connection_success(self, mock_pool_class):
        """Test successful connection retrieval."""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        pool = DatabaseConnectionPool("postgresql://localhost/testdb")
        pool.initialize()

        with pool.get_connection() as conn:
            assert conn == mock_conn

        mock_pool.getconn.assert_called_once()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    @patch("paper_scanner.io.sql.SimpleConnectionPool")
    def test_get_connection_rollback_on_error(self, mock_pool_class):
        """Test that connection rolls back on error."""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        pool = DatabaseConnectionPool("postgresql://localhost/testdb")
        pool.initialize()

        try:
            with pool.get_connection() as conn:
                raise Exception("Test error")
        except Exception:
            pass

        mock_conn.rollback.assert_called_once()


class TestPaperToRowConverter:
    """Tests for PaperToRowConverter class."""

    def test_paper_to_row_basic(self, sample_paper):
        """Test basic Paper to row conversion."""
        converter = PaperToRowConverter()
        row = converter.paper_to_row(sample_paper)

        assert row["id"] == "test-paper-1"
        assert row["cite_key"] == "smith2023"
        assert row["title"] == "Test Paper Title"
        assert row["abstract"] == "This is a test abstract"
        assert row["year"] == 2023
        assert row["journal"] == "Test Journal"

    def test_paper_to_row_complex_fields(self, sample_paper):
        """Test conversion with complex fields."""
        converter = PaperToRowConverter()
        row = converter.paper_to_row(sample_paper)

        assert row["discovery"] is not None
        assert row["keywords"] == ["keyword1", "keyword2"]
        assert row["topics"] == ["topic1"]

    def test_paper_to_row_empty_arrays(self):
        """Test conversion with empty arrays."""
        paper = Paper(
            id="test-1",
            cite_key="test2023",
            title="Test",
            authors=[
                Author(
                    given_name="Test",
                    family_name="Author",
                    full_name="Test Author",
                )
            ],
            keywords=[],
            topics=[],
            discovery=Discovery(method=DiscoveryMethod.KEYWORD_SEARCH),
            screening=Screening(),
        )
        converter = PaperToRowConverter()
        row = converter.paper_to_row(paper)
        assert row["keywords"] == []
        assert row["topics"] == []

    def test_paper_to_row_all_fields(self, sample_paper):
        """Test conversion preserves all key fields."""
        converter = PaperToRowConverter()
        row = converter.paper_to_row(sample_paper)

        # Verify essential fields are present and correct
        assert row["id"] is not None
        assert row["cite_key"] is not None
        assert row["title"] is not None
        assert row["authors"] is not None
        assert row["discovery"] is not None
        assert row["screening"] is not None
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        assert row["paper_type"] == "journal_article"

    def test_paper_to_row_with_minimal_fields(self):
        """Test conversion with minimal required fields only."""
        minimal_paper = Paper(
            id="minimal-1",
            cite_key="min2023",
            title="Minimal Paper",
            authors=[
                Author(
                    given_name="Test",
                    family_name="Author",
                    full_name="Test Author",
                )
            ],
            discovery=Discovery(method=DiscoveryMethod.MANUAL),
            screening=Screening(),
        )
        converter = PaperToRowConverter()
        row = converter.paper_to_row(minimal_paper)

        assert row["title"] == "Minimal Paper"
        assert row["abstract"] is None
        assert row["journal"] is None
        assert row["year"] is None


class TestPaperUploader:
    """Tests for PaperUploader class."""

    def test_init(self, mock_connection_pool):
        """Test uploader initialization."""
        uploader = PaperUploader(mock_connection_pool)
        assert uploader.pool == mock_connection_pool

    def test_insert_papers_empty_list(self, mock_connection_pool):
        """Test insert with empty paper list."""
        uploader = PaperUploader(mock_connection_pool)
        result = uploader.insert_papers([])

        assert result["inserted"] == 0
        assert result["skipped"] == 0

    @patch("paper_scanner.io.sql.PaperToRowConverter")
    def test_insert_papers_dry_run(self, mock_converter, mock_connection_pool, sample_paper):
        """Test dry-run mode doesn't insert."""
        mock_converter.paper_to_row.return_value = {"id": "test-1", "cite_key": "test"}

        uploader = PaperUploader(mock_connection_pool)
        result = uploader.insert_papers([sample_paper], dry_run=True)

        # In dry-run, connection should not be called
        assert result["inserted"] == 1
        mock_connection_pool.get_connection.assert_not_called()

    @patch("paper_scanner.io.sql.PaperToRowConverter")
    def test_insert_papers_success(self, mock_converter, mock_connection_pool, sample_paper):
        """Test successful paper insertion."""
        # Setup mocks
        mock_converter.paper_to_row.return_value = {"id": "test-1", "cite_key": "test"}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection_pool.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connection_pool.get_connection.return_value.__exit__ = Mock(return_value=False)

        uploader = PaperUploader(mock_connection_pool)
        result = uploader.insert_papers([sample_paper])

        assert result["inserted"] == 1
        mock_cursor.execute.assert_called()

    @patch("paper_scanner.io.sql.PaperToRowConverter")
    def test_insert_papers_conflict_skip(self, mock_converter, mock_connection_pool, sample_paper):
        """Test conflict strategy: skip."""
        mock_converter.paper_to_row.return_value = {"cite_key": "test"}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection_pool.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connection_pool.get_connection.return_value.__exit__ = Mock(return_value=False)

        uploader = PaperUploader(mock_connection_pool)
        result = uploader.insert_papers([sample_paper], conflict_strategy="skip")

        assert result["inserted"] == 1

    @patch("paper_scanner.io.sql.PaperToRowConverter")
    def test_insert_papers_conflict_update(self, mock_converter, mock_connection_pool, sample_paper):
        """Test conflict strategy: update."""
        mock_converter.paper_to_row.return_value = {"cite_key": "test", "title": "Updated"}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connection_pool.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connection_pool.get_connection.return_value.__exit__ = Mock(return_value=False)

        uploader = PaperUploader(mock_connection_pool)
        result = uploader.insert_papers([sample_paper], conflict_strategy="update")

        assert result["inserted"] == 1

    def test_transaction_context_manager(self, mock_connection_pool):
        """Test transaction context manager."""
        mock_conn = Mock()

        uploader = PaperUploader(mock_connection_pool)
        # Transaction is a context manager, verify it works
        with uploader.transaction(mock_conn):
            mock_conn.commit.assert_not_called()

        # After context exits, should commit
        mock_conn.commit.assert_called_once()


class TestDOIDuplicateHandler:
    """Tests for DOIDuplicateHandler class."""

    def test_normalize_doi_basic(self):
        """Test basic DOI normalization."""
        doi = "10.1234/test.doi"
        result = DOIDuplicateHandler.normalize_doi(doi)
        assert result == "10.1234/test.doi"

    def test_normalize_doi_uppercase(self):
        """Test DOI normalization with uppercase."""
        doi = "10.1234/TEST.DOI"
        result = DOIDuplicateHandler.normalize_doi(doi)
        assert result == "10.1234/test.doi"

    def test_normalize_doi_whitespace(self):
        """Test DOI normalization with whitespace."""
        doi = "  10.1234/test.doi  "
        result = DOIDuplicateHandler.normalize_doi(doi)
        assert result == "10.1234/test.doi"

    def test_normalize_doi_none(self):
        """Test DOI normalization with None."""
        result = DOIDuplicateHandler.normalize_doi(None)
        assert result is None

    def test_normalize_doi_empty_string(self):
        """Test DOI normalization with empty string."""
        result = DOIDuplicateHandler.normalize_doi("")
        assert result is None

    def test_mark_duplicate(self):
        """Test marking a paper as duplicate."""
        mock_cursor = Mock()

        DOIDuplicateHandler.mark_duplicate(
            mock_cursor,
            duplicate_paper_id="dup-1",
            primary_paper_id="primary-1",
        )

        mock_cursor.execute.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_connection_pool_lifecycle(self):
        """Test complete connection pool lifecycle."""
        with patch("paper_scanner.io.sql.SimpleConnectionPool"):
            pool = DatabaseConnectionPool("postgresql://localhost/test")
            pool.initialize()
            assert pool._pool is not None
            pool.close()
            assert pool._pool is None

    def test_multiple_papers_conversion(self, sample_paper):
        """Test converting multiple papers."""
        converter = PaperToRowConverter()
        papers = [sample_paper, sample_paper]
        rows = [converter.paper_to_row(p) for p in papers]

        assert len(rows) == 2
        assert rows[0]["cite_key"] == rows[1]["cite_key"]

    def test_doi_normalization_consistency(self):
        """Test that DOI normalization is consistent."""
        doi1 = DOIDuplicateHandler.normalize_doi("10.1234/TEST")
        doi2 = DOIDuplicateHandler.normalize_doi("10.1234/test")
        doi3 = DOIDuplicateHandler.normalize_doi("  10.1234/Test  ")

        assert doi1 == doi2 == doi3
