"""
Unit tests for database management CLI tasks.

Tests the database statistics command and clear command.
"""

from unittest.mock import Mock, patch

import psycopg2
import pytest
from rich.console import Console

from paper_scanner.cli.tasks.db import _get_database_url, _resolve_env_var, execute_db_clear, execute_db_stats


@pytest.fixture
def mock_console():
    """Create a mock console for testing."""
    return Mock(spec=Console)


@pytest.fixture
def mock_database_connection():
    """Create a mock database connection."""
    return Mock()


class TestDatabaseStats:
    """Tests for execute_db_stats function."""

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_success(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test successful stats retrieval."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (42,),          # papers count
            (10,),          # citations count
            (5, 2020, 2025, 35),  # stats tuple
            (38,),          # screened count
        ]

        # Execute
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console
        )

        # Verify
        assert result == 0
        assert mock_psycopg2_connect.called
        assert mock_cursor.execute.called
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_with_custom_database_url(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test stats with custom database URL."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (10,),          # papers count
            (5,),           # citations count
            (3, 2021, 2024, 8),   # stats tuple
            (9,),           # screened count
        ]

        # Execute with custom URL
        custom_url = "postgresql://user:pass@host:5432/customdb"
        result = execute_db_stats(
            database_url=custom_url,
            cache_dir=None,
            console=mock_console
        )

        # Verify
        assert result == 0
        mock_psycopg2_connect.assert_called_with(custom_url)

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_connection_error(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test error handling when connection fails."""
        # Simulate connection error
        mock_psycopg2_connect.side_effect = psycopg2.Error("Connection refused")

        # Execute
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console
        )

        # Verify error handling
        assert result == 1
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_default_console(self, mock_psycopg2_connect, mock_load_dotenv):
        """Test that default console is created if none provided."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (100,),         # papers count
            (50,),          # citations count
            (10, 2015, 2025, 80),  # stats tuple
            (95,),          # screened count
        ]

        # Execute without providing console
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=None
        )

        # Verify
        assert result == 0
        assert mock_cursor.execute.called

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_query_error(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test error handling during query execution."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate query error
        mock_cursor.execute.side_effect = Exception("Query error")

        # Execute
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console
        )

        # Verify error handling
        assert result == 1
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_empty_results(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test stats when database is empty."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results with empty database
        mock_cursor.fetchone.side_effect = [
            (0,),           # papers count
            (0,),           # citations count
            (0, None, None, 0),  # stats tuple with None values
            (0,),           # screened count
        ]

        # Execute
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console
        )

        # Verify
        assert result == 0
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_stats_cursor_cleanup(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test that cursor and connection are properly cleaned up."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (50,),          # papers count
            (25,),          # citations count
            (7, 2018, 2025, 40),   # stats tuple
            (48,),          # screened count
        ]

        # Execute
        result = execute_db_stats(
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console
        )

        # Verify cleanup
        assert result == 0
        mock_cursor.close.assert_called_once()
        assert mock_cursor.close.called


class TestDatabaseUrlResolution:
    """Tests for _get_database_url and _resolve_env_var functions."""

    def test_resolve_env_var_literal_value(self):
        """Test _resolve_env_var with literal value."""
        result = _resolve_env_var("postgresql://localhost/db")
        assert result == "postgresql://localhost/db"

    def test_resolve_env_var_env_reference(self):
        """Test _resolve_env_var with environment variable reference."""
        import os
        os.environ["TEST_DB_URL"] = "postgresql://user:pass@host/db"

        result = _resolve_env_var("$TEST_DB_URL")
        assert result == "postgresql://user:pass@host/db"

    def test_resolve_env_var_missing_env(self):
        """Test _resolve_env_var with missing environment variable."""
        result = _resolve_env_var("$NONEXISTENT_VAR_XYZ")
        assert result is None

    def test_resolve_env_var_none_value(self):
        """Test _resolve_env_var with None value."""
        result = _resolve_env_var(None)
        assert result is None

    def test_resolve_env_var_empty_string(self):
        """Test _resolve_env_var with empty string."""
        result = _resolve_env_var("")
        assert result is None

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://explicit/url"})
    def test_get_database_url_explicit(self):
        """Test _get_database_url with explicit parameter."""
        result = _get_database_url("postgresql://custom:pass@host/customdb")
        assert result == "postgresql://custom:pass@host/customdb"

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://envvar/url"})
    def test_get_database_url_env_var(self):
        """Test _get_database_url with DATABASE_URL env var."""
        result = _get_database_url(None)
        assert result == "postgresql://envvar/url"

    @patch.dict(
        "os.environ",
        {
            "DB_USER": "testuser",
            "DB_PASSWORD": "testpass",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "testdb"
        },
        clear=True
    )
    def test_get_database_url_components(self):
        """Test _get_database_url with individual components."""
        result = _get_database_url(None)
        assert result == "postgresql://testuser:testpass@localhost:5432/testdb"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_database_url_no_config(self):
        """Test _get_database_url with no configuration."""
        result = _get_database_url(None)
        assert result is None

    @patch.dict(
        "os.environ",
        {
            "DB_USER": "$USER_ENV",
            "DB_PASSWORD": "staticpass",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "testdb",
            "USER_ENV": "myuser"
        }
    )
    def test_get_database_url_with_env_references(self):
        """Test _get_database_url with environment variable references in components."""
        result = _get_database_url(None)
        assert result == "postgresql://myuser:staticpass@localhost:5432/testdb"


class TestDatabaseClear:
    """Tests for execute_db_clear function."""

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_all_dry_run(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test clear all with dry run mode."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results for all tables
        mock_cursor.fetchone.side_effect = [
            (0,),   # paper_cluster_assignments
            (0,),   # paper_clusters
            (0,),   # paper_tags
            (0,),   # tags
            (0,),   # processing_logs
            (0,),   # chunk_embeddings
            (0,),   # paper_embeddings
            (0,),   # paper_chunks
            (0,),   # paper_analysis
            (0,),   # citation_edges
            (0,),   # paper_screening
            (100,), # papers
        ]

        # Execute with dry run
        result = execute_db_clear(
            target="all",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=True,
            verbose=False,
        )

        # Verify dry run returned 0 (success)
        assert result == 0
        # Verify mock_cursor.execute was called for count queries
        assert mock_cursor.execute.called
        # Verify DELETE was NOT called (dry run)
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if call[0][0].startswith("DELETE")]
        assert len(delete_calls) == 0

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_all_execute(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test clear all with actual execution."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results - counts for each table
        fetch_results = [
            (0,),   # COUNT for paper_cluster_assignments
            (0,),   # COUNT for paper_clusters
            (0,),   # COUNT for paper_tags
            (0,),   # COUNT for tags
            (0,),   # COUNT for processing_logs
            (0,),   # COUNT for chunk_embeddings
            (0,),   # COUNT for paper_embeddings
            (0,),   # COUNT for paper_chunks
            (0,),   # COUNT for paper_analysis
            (0,),   # COUNT for citation_edges
            (0,),   # COUNT for paper_screening
            (50,),  # COUNT for papers
        ]
        mock_cursor.fetchone.side_effect = fetch_results

        # Execute actual clear
        result = execute_db_clear(
            target="all",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=True,
        )

        # Verify success
        assert result == 0
        # Verify DELETE was called for papers table
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if call[0][0].startswith("DELETE")]
        assert len(delete_calls) > 0
        # Verify conn.commit was called
        mock_conn.commit.assert_called_once()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_specific_table(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test clearing a specific table."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock count query result
        mock_cursor.fetchone.return_value = (30,)

        # Execute clear for specific table
        result = execute_db_clear(
            target="papers",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=False,
        )

        # Verify success
        assert result == 0
        # Verify DELETE was called
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if "DELETE FROM papers" in call[0][0]]
        assert len(delete_calls) > 0

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_invalid_table(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test clearing with invalid table name."""
        # Execute with invalid table
        result = execute_db_clear(
            target="nonexistent_table",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=False,
        )

        # Verify error
        assert result == 1
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_connection_error(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test error handling when connection fails."""
        # Simulate connection error
        mock_psycopg2_connect.side_effect = psycopg2.Error("Connection refused")

        # Execute
        result = execute_db_clear(
            target="all",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=False,
        )

        # Verify error handling
        assert result == 1
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_query_error(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test error handling during clear operation."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate psycopg2 error during execution
        mock_cursor.execute.side_effect = psycopg2.Error("Query error")

        # Execute
        result = execute_db_clear(
            target="all",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=False,
        )

        # Verify error handling
        assert result == 1
        mock_console.print.assert_called()

    @patch("dotenv.load_dotenv")
    @patch("paper_scanner.cli.tasks.db.psycopg2.connect")
    def test_clear_empty_tables(self, mock_psycopg2_connect, mock_load_dotenv, mock_console):
        """Test clear when all tables are empty."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_psycopg2_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # All tables have 0 records
        mock_cursor.fetchone.return_value = (0,)

        # Execute
        result = execute_db_clear(
            target="all",
            database_url="postgresql://user:pass@localhost/testdb",
            cache_dir=None,
            console=mock_console,
            dry_run=False,
            verbose=False,
        )

        # Verify success (nothing to clear)
        assert result == 0
        # Verify conn.commit was called
        mock_conn.commit.assert_called_once()
