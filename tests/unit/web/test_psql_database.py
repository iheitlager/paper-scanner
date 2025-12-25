"""
Comprehensive tests for DatabaseManager class.

Tests cover:
- Connection management with retry logic
- Database initialization and schema verification
- PDF record CRUD operations
- Tag management and synchronization
- Error handling and exception cases
"""

import json
from unittest.mock import Mock, patch

import pytest
from psycopg2 import OperationalError

from paper_scanner.web.database import DatabaseManager
from paper_scanner.web.exceptions import DatabaseException, InvalidDataException


class TestDatabaseManagerInit:
    """Test DatabaseManager initialization."""

    def test_init_stores_db_url(self):
        """Test that __init__ stores the database URL."""
        db_url = "postgresql://user:pass@localhost/dbname"
        manager = DatabaseManager(db_url)
        assert manager.db_url == db_url

    def test_init_with_different_urls(self):
        """Test initialization with various URL formats."""
        urls = [
            "postgresql://localhost/test",
            "postgresql://user:password@host:5432/database",
            "postgres://localhost/mydb",
        ]
        for url in urls:
            manager = DatabaseManager(url)
            assert manager.db_url == url


class TestGetConnection:
    """Test get_connection method with retry logic."""

    def test_get_connection_success_first_attempt(self):
        """Test successful connection on first attempt."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()

        with patch("paper_scanner.web.database.connect") as mock_connect:
            mock_connect.return_value = mock_conn
            result = manager.get_connection()

            assert result == mock_conn
            mock_connect.assert_called_once_with("postgresql://localhost/test")

    def test_get_connection_success_after_retries(self):
        """Test successful connection after initial failures."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()

        with patch("paper_scanner.web.database.connect") as mock_connect:
            with patch("paper_scanner.web.database.time.sleep"):
                # Fail twice, succeed on third attempt
                mock_connect.side_effect = [
                    OperationalError("Connection refused"),
                    OperationalError("Connection refused"),
                    mock_conn,
                ]
                result = manager.get_connection(retries=3, delay=1)

                assert result == mock_conn
                assert mock_connect.call_count == 3

    def test_get_connection_fails_after_max_retries(self):
        """Test DatabaseException raised after max retries exhausted."""
        manager = DatabaseManager("postgresql://localhost/test")

        with patch("paper_scanner.web.database.connect") as mock_connect:
            with patch("paper_scanner.web.database.time.sleep"):
                mock_connect.side_effect = OperationalError("Connection refused")

                with pytest.raises(DatabaseException) as exc_info:
                    manager.get_connection(retries=3, delay=1)

                assert "Database connection failed after 3 attempts" in str(exc_info.value)
                assert mock_connect.call_count == 3

    def test_get_connection_respects_delay_between_retries(self):
        """Test that delay is respected between retry attempts."""
        manager = DatabaseManager("postgresql://localhost/test")

        with patch("paper_scanner.web.database.connect") as mock_connect:
            with patch("paper_scanner.web.database.time.sleep") as mock_sleep:
                mock_connect.side_effect = [
                    OperationalError("Failed"),
                    OperationalError("Failed"),
                    Mock(),
                ]
                manager.get_connection(retries=3, delay=2)

                # Should sleep twice (after first and second failures)
                assert mock_sleep.call_count == 2
                mock_sleep.assert_called_with(2)

    def test_get_connection_with_custom_retry_params(self):
        """Test custom retry and delay parameters."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()

        with patch("paper_scanner.web.database.connect") as mock_connect:
            mock_connect.return_value = mock_conn
            result = manager.get_connection(retries=5, delay=3)

            assert result == mock_conn
            mock_connect.assert_called_once()

    def test_get_connection_handles_generic_exception(self):
        """Test that generic exceptions are caught and retried."""
        manager = DatabaseManager("postgresql://localhost/test")

        with patch("paper_scanner.web.database.connect") as mock_connect:
            with patch("paper_scanner.web.database.time.sleep"):
                mock_connect.side_effect = [
                    Exception("Generic error"),
                    Exception("Generic error"),
                    Exception("Generic error"),
                ]

                with pytest.raises(DatabaseException):
                    manager.get_connection(retries=3, delay=1)


class TestInitDatabase:
    """Test init_database method."""

    def test_init_database_schema_exists(self):
        """Test successful initialization when schema exists."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.init_database()

            mock_cursor.execute.assert_called_once()
            assert "SELECT 1 FROM information_schema.tables" in mock_cursor.execute.call_args[0][0]
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_init_database_schema_not_found(self):
        """Test initialization warning when schema not found."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with patch("paper_scanner.web.database.logger") as mock_logger:
                manager.init_database()

                mock_logger.warning.assert_called_once()
                assert "not found" in mock_logger.warning.call_args[0][0]

    def test_init_database_connection_failure(self):
        """Test DatabaseException on connection failure."""
        manager = DatabaseManager("postgresql://localhost/test")

        with patch.object(manager, "get_connection", side_effect=DatabaseException("Connection failed")):
            with pytest.raises(DatabaseException) as exc_info:
                manager.init_database()

            assert "Database initialization failed" in str(exc_info.value)

    def test_init_database_cursor_failure(self):
        """Test DatabaseException on cursor operation failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.init_database()

            assert "Database initialization failed" in str(exc_info.value)


class TestInsertPdfRecord:
    """Test insert_pdf_record method."""

    def test_insert_pdf_record_minimal(self):
        """Test inserting a PDF record with minimal required fields."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.insert_pdf_record(record)

            assert result is True
            mock_cursor.execute.assert_called()
            assert mock_conn.commit.called
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_insert_pdf_record_with_all_fields(self):
        """Test inserting a PDF record with all available fields."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "size_bytes": 1024000,
            "created_time": "2025-12-01 10:00:00",
            "modified_time": "2025-12-02 11:00:00",
            "accessed_time": "2025-12-02 12:00:00",
            "tags": "tag1:tag2:tag3",
            "title-details": {
                "title": "Sample Paper",
                "citekey": "Smith2025",
                "year": 2025,
                "authors": "Smith et al.",
            },
            "analysis": {
                "key_concepts": ["concept1", "concept2"],
                "summary": "Paper summary",
            },
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.insert_pdf_record(record)

            assert result is True
            # Should insert into tags table first
            insert_calls = [call for call in mock_cursor.execute.call_args_list]
            assert len(insert_calls) >= 2  # At least tag inserts + main insert
            mock_conn.commit.assert_called()

    def test_insert_pdf_record_missing_required_field(self):
        """Test InvalidDataException when required field is missing."""
        manager = DatabaseManager("postgresql://localhost/test")

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            # Missing directory
        }

        with pytest.raises(InvalidDataException) as exc_info:
            manager.insert_pdf_record(record)

        assert "Missing required fields" in str(exc_info.value)

    def test_insert_pdf_record_with_tags(self):
        """Test that tags are synced to tags table."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "tags": "python:machine learning:ai",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.insert_pdf_record(record)

            # First three calls should be for tags
            calls = mock_cursor.execute.call_args_list
            assert calls[0][0][0] == "INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING"
            assert calls[0][0][1] == ("python",)
            assert calls[1][0][1] == ("machine learning",)
            assert calls[2][0][1] == ("ai",)

    def test_insert_pdf_record_with_empty_tags(self):
        """Test that empty tags string doesn't cause errors."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "tags": "",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.insert_pdf_record(record)

            assert result is True
            # Should only have one insert call (for papers)
            assert len(mock_cursor.execute.call_args_list) == 1

    def test_insert_pdf_record_database_error(self):
        """Test DatabaseException on insert failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Insert failed")

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.insert_pdf_record(record)

            assert "Failed to insert PDF record" in str(exc_info.value)
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_insert_pdf_record_cleanup_on_error(self):
        """Test that cursor and connection are closed even on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.insert_pdf_record(record)

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_insert_pdf_record_serializes_title_details_to_json(self):
        """Test that title_details is serialized to JSON in database."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        title_details = {
            "title": "Test Paper",
            "citekey": "Test2025",
            "authors": "Author et al.",
        }
        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "title-details": title_details,
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.insert_pdf_record(record)

            # Find the INSERT INTO papers call
            calls = mock_cursor.execute.call_args_list
            pdf_insert_call = [c for c in calls if "INSERT INTO papers" in c[0][0]][0]
            # The title_details should be serialized to JSON
            assert json.dumps(title_details) in str(pdf_insert_call)

    def test_insert_pdf_record_extracts_year_from_title_details(self):
        """Test that year is extracted from title_details."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "title-details": {
                "title": "Test Paper",
                "citekey": "Test2025",
                "year": 2025,
            },
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.insert_pdf_record(record)

            # Get the INSERT call and verify year is included
            calls = mock_cursor.execute.call_args_list
            pdf_insert_call = [c for c in calls if "INSERT INTO papers" in c[0][0]][0]
            # Year (2025) should be in the parameters
            assert 2025 in pdf_insert_call[0][1]

    def test_insert_pdf_record_converts_year_string_to_int(self):
        """Test that year string is converted to integer."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/to/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path/to",
            "title-details": {
                "title": "Test Paper",
                "year": "2025",  # String instead of int
            },
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.insert_pdf_record(record)

            # Get the INSERT call and verify year is int
            calls = mock_cursor.execute.call_args_list
            pdf_insert_call = [c for c in calls if "INSERT INTO papers" in c[0][0]][0]
            # Year should be converted to int
            assert 2025 in pdf_insert_call[0][1]


class TestGetAllPdfs:
    """Test get_all_pdfs method."""

    def test_get_all_pdfs_no_filter(self):
        """Test retrieving all PDF records."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_records = [
            {"file_name": "file1.pdf", "file_path": "/path/file1.pdf"},
            {"file_name": "file2.pdf", "file_path": "/path/file2.pdf"},
        ]
        mock_cursor.fetchall.return_value = mock_records

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_all_pdfs()

            assert result == mock_records
            mock_cursor.execute.assert_called_once()
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_all_pdfs_empty_result(self):
        """Test retrieving PDFs when database is empty."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_all_pdfs()

            assert result == []

    def test_get_all_pdfs_database_error(self):
        """Test DatabaseException on query failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.get_all_pdfs()

            assert "Failed to fetch PDF records" in str(exc_info.value)
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_all_pdfs_cleanup_on_error(self):
        """Test that resources are cleaned up on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.get_all_pdfs()

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()


class TestGetPdfByFileName:
    """Test get_pdf_by_file_name method."""

    def test_get_pdf_by_file_name_found(self):
        """Test retrieving a PDF record that exists."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_record = {
            "file_name": "paper.pdf",
            "file_path": "/path/paper.pdf",
            "title": "Sample Paper",
        }
        mock_cursor.fetchone.return_value = mock_record

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_pdf_by_file_name("paper.pdf")

            assert result == mock_record
            mock_cursor.execute.assert_called_once_with(
                "SELECT * FROM papers WHERE file_name = %s",
                ("paper.pdf",),
            )
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_pdf_by_file_name_not_found(self):
        """Test retrieving a PDF record that doesn't exist."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_pdf_by_file_name("nonexistent.pdf")

            assert result is None

    def test_get_pdf_by_file_name_database_error(self):
        """Test DatabaseException on query failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.get_pdf_by_file_name("paper.pdf")

            assert "Failed to fetch PDF record" in str(exc_info.value)

    def test_get_pdf_by_file_name_cleanup_on_error(self):
        """Test that resources are cleaned up on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.get_pdf_by_file_name("paper.pdf")

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()


class TestGetAllTags:
    """Test get_all_tags method."""

    def test_get_all_tags_returns_list(self):
        """Test retrieving all tags from database."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("machine learning",),
            ("python",),
            ("ai",),
        ]

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_all_tags()

            assert result == ["machine learning", "python", "ai"]
            mock_cursor.execute.assert_called_once_with("SELECT tag_name FROM tags ORDER BY tag_name")
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_all_tags_empty_result(self):
        """Test retrieving tags when no tags exist."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_all_tags()

            assert result == []

    def test_get_all_tags_database_error(self):
        """Test DatabaseException on query failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.get_all_tags()

            assert "Failed to fetch tags" in str(exc_info.value)

    def test_get_all_tags_cleanup_on_error(self):
        """Test that resources are cleaned up on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.get_all_tags()

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()


class TestUpdatePdfTags:
    """Test update_pdf_tags method."""

    def test_update_pdf_tags_success(self):
        """Test successfully updating tags for a PDF."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.update_pdf_tags("paper.pdf", "python:ai:machine learning")

            assert result is True
            # Should have calls for tag inserts + update
            calls = mock_cursor.execute.call_args_list
            assert len(calls) >= 4  # 3 tag inserts + 1 update
            mock_conn.commit.assert_called()
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_update_pdf_tags_syncs_to_tags_table(self):
        """Test that tags are synced to tags table."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.update_pdf_tags("paper.pdf", "tag1:tag2:tag3")

            calls = mock_cursor.execute.call_args_list
            # First three calls should be for tags
            assert calls[0][0][0] == "INSERT INTO tags (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING"
            assert calls[0][0][1] == ("tag1",)
            assert calls[1][0][1] == ("tag2",)
            assert calls[2][0][1] == ("tag3",)

    def test_update_pdf_tags_with_empty_tags(self):
        """Test updating tags with empty string."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.update_pdf_tags("paper.pdf", "")

            assert result is True
            # Should only have update call (no tag inserts)
            calls = mock_cursor.execute.call_args_list
            assert len(calls) == 1
            assert "UPDATE papers SET tags" in calls[0][0][0]

    def test_update_pdf_tags_database_error(self):
        """Test DatabaseException on update failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Update failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.update_pdf_tags("paper.pdf", "tag1:tag2")

            assert "Failed to update tags" in str(exc_info.value)

    def test_update_pdf_tags_cleanup_on_error(self):
        """Test that resources are cleaned up on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.update_pdf_tags("paper.pdf", "tag1")

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_update_pdf_tags_with_whitespace(self):
        """Test that tags with whitespace are properly cleaned."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(manager, "get_connection", return_value=mock_conn):
            manager.update_pdf_tags("paper.pdf", "  tag1  :  tag2  :  tag3  ")

            calls = mock_cursor.execute.call_args_list
            # Tags should be stripped of whitespace
            assert calls[0][0][1] == ("tag1",)
            assert calls[1][0][1] == ("tag2",)
            assert calls[2][0][1] == ("tag3",)


class TestGetYearOverview:
    """Test get_year_overview method."""

    def test_get_year_overview_returns_list(self):
        """Test retrieving year overview data."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_year_data = [
            {
                "year": 2025,
                "count": 3,
                "papers": [
                    {"file_name": "paper1.pdf", "title": "Paper 1", "citekey": "P1"},
                    {"file_name": "paper2.pdf", "title": "Paper 2", "citekey": "P2"},
                    {"file_name": "paper3.pdf", "title": "Paper 3", "citekey": "P3"},
                ],
            },
            {
                "year": 2024,
                "count": 2,
                "papers": [
                    {"file_name": "paper4.pdf", "title": "Paper 4", "citekey": "P4"},
                    {"file_name": "paper5.pdf", "title": "Paper 5", "citekey": "P5"},
                ],
            },
        ]
        mock_cursor.fetchall.return_value = mock_year_data

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_year_overview()

            assert len(result) == 2
            assert result[0]["year"] == 2025
            assert result[0]["count"] == 3
            assert len(result[0]["papers"]) == 3
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_year_overview_empty(self):
        """Test retrieving year overview when no years present."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(manager, "get_connection", return_value=mock_conn):
            result = manager.get_year_overview()

            assert result == []

    def test_get_year_overview_database_error(self):
        """Test DatabaseException on query failure."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Query failed")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException) as exc_info:
                manager.get_year_overview()

            assert "Failed to fetch year overview" in str(exc_info.value)
            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()

    def test_get_year_overview_cleanup_on_error(self):
        """Test that resources are cleaned up on error."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Error")

        with patch.object(manager, "get_connection", return_value=mock_conn):
            with pytest.raises(DatabaseException):
                manager.get_year_overview()

            mock_cursor.close.assert_called()
            mock_conn.close.assert_called()


class TestDatabaseManagerIntegration:
    """Integration tests combining multiple operations."""

    def test_insert_then_retrieve_pdf(self):
        """Test inserting a PDF and then retrieving it."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        record = {
            "file_path": "/path/file.pdf",
            "file_name": "file.pdf",
            "directory": "/path",
        }

        with patch.object(manager, "get_connection", return_value=mock_conn):
            # Insert
            manager.insert_pdf_record(record)
            mock_cursor.reset_mock()

            # Retrieve
            mock_cursor.fetchone.return_value = record
            result = manager.get_pdf_by_file_name("file.pdf")

            assert result == record

    def test_connection_reused_for_operations(self):
        """Test that get_connection is called for each operation."""
        manager = DatabaseManager("postgresql://localhost/test")
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        with patch.object(manager, "get_connection", return_value=mock_conn) as mock_get_conn:
            # Two operations
            manager.get_all_tags()
            manager.get_all_pdfs()

            # Should call get_connection twice
            assert mock_get_conn.call_count == 2
