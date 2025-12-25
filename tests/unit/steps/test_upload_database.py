"""
Tests for UploadDatabaseStep.

Tests configuration validation, database URL construction, environment variable
resolution, and upload execution with mocked database connections.
"""

import os
from unittest.mock import Mock, patch

import pytest

from paper_scanner.core.exceptions import StepFatalError
from paper_scanner.core.models import Paper
from paper_scanner.core.step_result import StepResult
from paper_scanner.steps.upload_database import UploadDatabaseStep


# Test fixtures
@pytest.fixture
def mock_db():
    """Create a mock database instance."""
    return Mock()


@pytest.fixture
def cache_dir(tmp_path):
    """Create a temporary cache directory."""
    return tmp_path


@pytest.fixture
def general_config():
    """Create a general configuration dictionary."""
    return {"project_name": "test_project"}


def create_step(mock_db, cache_dir, general_config):
    """Helper to create a step instance with required arguments."""
    return UploadDatabaseStep(
        general_config=general_config,
        db=mock_db,
        cache_dir=cache_dir
    )


class TestUploadDatabaseValidation:
    """Tests for configuration validation."""

    def test_validate_with_database_url(self):
        """Test validation passes with database_url parameter."""
        config = {"database_url": "postgresql://user:pass@localhost:5432/testdb"}
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_with_env_var_database_url(self):
        """Test validation passes with environment variable reference."""
        config = {"database_url": "$DATABASE_URL"}
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_with_components(self):
        """Test validation passes with individual components."""
        config = {
            "db_username": "user",
            "db_password": "pass",
            "db_host": "localhost",
            "db_port": "5432",
            "db_name": "testdb",
        }
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_database_url_and_components(self):
        """Test validation fails when neither database_url nor components provided."""
        config = {}
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid
        assert any("database_url" in e or "db_username" in e for e in errors)

    def test_validate_incomplete_components(self):
        """Test validation fails with incomplete components."""
        config = {
            "db_username": "user",
            "db_password": "pass",
            # Missing db_host, db_port, db_name
        }
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid

    def test_validate_invalid_database_url(self):
        """Test validation fails with invalid URL format."""
        config = {"database_url": "mysql://user:pass@localhost/db"}
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid
        assert any("Invalid database_url format" in e for e in errors)

    def test_validate_invalid_batch_size(self):
        """Test validation fails with invalid batch_size."""
        config = {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "batch_size": "not_a_number"
        }
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid
        assert any("batch_size must be integer" in e for e in errors)

    def test_validate_negative_batch_size(self):
        """Test validation fails with negative batch_size."""
        config = {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "batch_size": -1
        }
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid
        assert any("batch_size must be positive" in e for e in errors)

    def test_validate_invalid_conflict_strategy(self):
        """Test validation fails with invalid conflict_strategy."""
        config = {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "conflict_strategy": "invalid_strategy"
        }
        is_valid, errors = UploadDatabaseStep.validate(config)
        assert not is_valid
        assert any("conflict_strategy" in e for e in errors)

    def test_validate_valid_conflict_strategies(self):
        """Test validation passes with valid conflict strategies."""
        for strategy in ["skip", "update", "raise"]:
            config = {
                "database_url": "postgresql://user:pass@localhost:5432/db",
                "conflict_strategy": strategy
            }
            is_valid, errors = UploadDatabaseStep.validate(config)
            assert is_valid, f"Strategy '{strategy}' should be valid"


class TestResolveEnvVar:
    """Tests for environment variable resolution."""

    def test_resolve_literal_value(self, mock_db, cache_dir, general_config):
        """Test that literal values are returned as-is."""
        step = create_step(mock_db, cache_dir, general_config)
        result = step._resolve_env_var("localhost")
        assert result == "localhost"

    def test_resolve_env_var_reference(self, mock_db, cache_dir, general_config):
        """Test that $VAR_NAME is resolved from environment."""
        with patch.dict(os.environ, {"DB_HOST": "prod-db.example.com"}):
            step = create_step(mock_db, cache_dir, general_config)
            result = step._resolve_env_var("$DB_HOST")
            assert result == "prod-db.example.com"

    def test_resolve_missing_env_var(self, mock_db, cache_dir, general_config):
        """Test that missing environment variable returns None."""
        with patch.dict(os.environ, {}, clear=False):
            step = create_step(mock_db, cache_dir, general_config)
            result = step._resolve_env_var("$NONEXISTENT_VAR")
            assert result is None

    def test_resolve_none_value(self, mock_db, cache_dir, general_config):
        """Test that None input returns None."""
        step = create_step(mock_db, cache_dir, general_config)
        result = step._resolve_env_var(None)
        assert result is None

    def test_resolve_empty_string(self, mock_db, cache_dir, general_config):
        """Test that empty string returns None."""
        step = create_step(mock_db, cache_dir, general_config)
        result = step._resolve_env_var("")
        assert result is None


class TestGetDatabaseUrl:
    """Tests for database URL construction."""

    def test_get_database_url_direct(self, mock_db, cache_dir, general_config):
        """Test retrieving direct database URL."""
        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/testdb"}
        url = step._get_database_url(config)
        assert url == "postgresql://user:pass@localhost:5432/testdb"

    def test_get_database_url_from_env_var(self, mock_db, cache_dir, general_config):
        """Test retrieving database URL from environment variable."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://prod:secret@prod-host:5432/prod_db"}):
            step = create_step(mock_db, cache_dir, general_config)
            config = {"database_url": "$DATABASE_URL"}
            url = step._get_database_url(config)
            assert url == "postgresql://prod:secret@prod-host:5432/prod_db"

    def test_get_database_url_missing_env_var(self, mock_db, cache_dir, general_config):
        """Test that missing environment variable returns None."""
        with patch.dict(os.environ, {}, clear=False):
            step = create_step(mock_db, cache_dir, general_config)
            config = {"database_url": "$MISSING_VAR"}
            url = step._get_database_url(config)
            assert url is None

    def test_get_database_url_from_components(self, mock_db, cache_dir, general_config):
        """Test building database URL from individual components."""
        step = create_step(mock_db, cache_dir, general_config)
        config = {
            "db_username": "user",
            "db_password": "pass",
            "db_host": "localhost",
            "db_port": "5432",
            "db_name": "testdb",
        }
        url = step._get_database_url(config)
        assert url == "postgresql://user:pass@localhost:5432/testdb"

    def test_get_database_url_from_components_with_env_vars(self, mock_db, cache_dir, general_config):
        """Test building database URL from components with environment variables."""
        with patch.dict(os.environ, {
            "DB_USER": "prod_user",
            "DB_PASS": "prod_secret",
            "DB_HOST": "prod.example.com",
            "DB_PORT": "5433",
            "DB_NAME": "prod_db"
        }):
            step = create_step(mock_db, cache_dir, general_config)
            config = {
                "db_username": "$DB_USER",
                "db_password": "$DB_PASS",
                "db_host": "$DB_HOST",
                "db_port": "$DB_PORT",
                "db_name": "$DB_NAME",
            }
            url = step._get_database_url(config)
            assert url == "postgresql://prod_user:prod_secret@prod.example.com:5433/prod_db"

    def test_get_database_url_missing_component(self, mock_db, cache_dir, general_config):
        """Test that missing component returns None."""
        step = create_step(mock_db, cache_dir, general_config)
        config = {
            "db_username": "user",
            "db_password": "pass",
            "db_host": "localhost",
            # Missing db_port and db_name
        }
        url = step._get_database_url(config)
        assert url is None


class TestExecuteDryRun:
    """Tests for dry-run execution."""

    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_dry_run_no_papers(self, mock_load_dotenv, mock_db, cache_dir, general_config):
        """Test dry-run with no papers in database."""
        from paper_scanner.core.enum import StepStatus

        mock_db.all.return_value = []

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=True)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.WARNING
        assert "No papers" in result.message
        assert result.stats["total_papers"] == 0

    @patch("paper_scanner.steps.upload_database.load_dotenv")
    @patch("paper_scanner.steps.upload_database.PaperToRowConverter")
    def test_execute_dry_run_valid_papers(self, mock_converter, mock_load_dotenv, mock_db, cache_dir, general_config):
        """Test dry-run validation with valid papers."""
        from paper_scanner.core.enum import StepStatus

        # Create mock papers
        mock_papers = [Mock(spec=Paper, cite_key="paper1")]
        mock_db.all.return_value = mock_papers

        # Mock converter to not raise errors
        mock_converter.paper_to_row.return_value = {"id": 1}

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=True)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.SUCCESS
        assert "validated" in result.message.lower()
        assert result.stats["total_papers"] == 1

    @patch("paper_scanner.steps.upload_database.load_dotenv")
    @patch("paper_scanner.steps.upload_database.PaperToRowConverter")
    def test_execute_dry_run_invalid_papers(self, mock_converter, mock_load_dotenv, mock_db, cache_dir, general_config):
        """Test dry-run validation with invalid papers."""
        from paper_scanner.core.enum import StepStatus

        # Create mock papers
        mock_papers = [Mock(spec=Paper, cite_key="paper1")]
        mock_db.all.return_value = mock_papers

        # Mock converter to raise error
        mock_converter.paper_to_row.side_effect = ValueError("Invalid paper")

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=True)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.WARNING
        assert "Validation errors" in result.message
        assert result.stats["total_papers"] == 1
        assert result.stats["validation_errors"] > 0


class TestExecuteRealUpload:
    """Tests for actual database upload execution."""

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_upload_success(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test successful upload execution."""
        from paper_scanner.core.enum import StepStatus

        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        # Mock insert_papers to return successful stats
        mock_uploader.insert_papers.return_value = {
            "inserted": 5,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "error_count": 0,
            "citation_edges": {
                "edges_inserted": 0,
                "edges_skipped": 0,
            },
        }

        # Create mock papers
        mock_papers = [Mock(spec=Paper) for _ in range(5)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=False)

        assert isinstance(result, StepResult)
        from paper_scanner.core.enum import StepStatus
        assert result.status == StepStatus.SUCCESS
        assert "inserted" in result.message.lower()
        assert result.stats["inserted"] == 5
        assert result.stats["errors"] == 0
        mock_pool.close.assert_called_once()

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_upload_with_errors(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test upload with some errors."""
        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        # Mock insert_papers to return stats with errors
        mock_uploader.insert_papers.return_value = {
            "inserted": 3,
            "updated": 0,
            "skipped": 1,
            "errors": ["Error with paper 1", "Error with paper 2"],
            "error_count": 2,
            "citation_edges": {
                "edges_inserted": 0,
                "edges_skipped": 0,
            },
        }

        # Create mock papers
        mock_papers = [Mock(spec=Paper) for _ in range(5)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=False)

        assert isinstance(result, StepResult)
        from paper_scanner.core.enum import StepStatus
        assert result.status == StepStatus.WARNING  # Warning due to errors
        assert result.stats["errors"] == 2
        assert result.stats["inserted"] == 3
        mock_pool.close.assert_called_once()

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_connection_error(self, mock_load_dotenv, mock_pool_class, mock_db, cache_dir, general_config):
        """Test that connection failure raises StepFatalError."""
        # Setup mock to raise error
        mock_pool = Mock()
        mock_pool.initialize.side_effect = ConnectionError("Cannot connect to database")
        mock_pool_class.return_value = mock_pool

        mock_db.all.return_value = [Mock(spec=Paper)]

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://invalid:host"}

        with pytest.raises(StepFatalError) as exc_info:
            step.execute(config, dry_run=False)

        assert "Failed to initialize database connection" in str(exc_info.value)

    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_invalid_database_url(self, mock_load_dotenv, mock_db, cache_dir, general_config):
        """Test that invalid database URL raises StepFatalError."""
        mock_db.all.return_value = [Mock(spec=Paper)]

        step = create_step(mock_db, cache_dir, general_config)
        config = {}  # No database_url

        with pytest.raises(StepFatalError) as exc_info:
            step.execute(config, dry_run=False)

        assert "Could not construct database URL" in str(exc_info.value)


class TestBatchProcessing:
    """Tests for batch processing in upload."""

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_batches_papers(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test that papers are uploaded in batches."""
        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        # Mock insert_papers to track batch calls
        call_count = [0]

        def mock_insert(papers, **kwargs):
            call_count[0] += 1
            return {
                "inserted": len(papers),
                "updated": 0,
                "skipped": 0,
                "errors": [],
                "error_count": 0,
                "citation_edges": {
                    "edges_inserted": 0,
                    "edges_skipped": 0,
                },
            }

        mock_uploader.insert_papers.side_effect = mock_insert

        # Create 250 mock papers (should be 3 batches with batch_size=100)
        mock_papers = [Mock(spec=Paper) for _ in range(250)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {
            "database_url": "postgresql://user:pass@localhost:5432/db",
            "batch_size": 100
        }

        result = step.execute(config, dry_run=False)

        # Should be called 3 times (batches of 100, 100, 50)
        assert mock_uploader.insert_papers.call_count == 3
        assert result.stats["inserted"] == 250

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_default_batch_size(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test that default batch size is 100."""
        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader
        mock_uploader.insert_papers.return_value = {
            "inserted": 100,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "error_count": 0,
            "citation_edges": {
                "edges_inserted": 0,
                "edges_skipped": 0,
            },
        }

        # Create 100 mock papers
        mock_papers = [Mock(spec=Paper) for _ in range(100)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=False)

        # Should be called once (all papers in one batch)
        assert mock_uploader.insert_papers.call_count == 1

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_with_citation_edges(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test that citation edges are properly aggregated when present."""
        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        # Mock insert_papers with citation edges
        mock_uploader.insert_papers.return_value = {
            "inserted": 10,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "error_count": 0,
            "citation_edges": {
                "edges_inserted": 25,
                "edges_skipped": 3,
            },
        }

        # Create mock papers
        mock_papers = [Mock(spec=Paper) for _ in range(10)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=False)

        assert isinstance(result, StepResult)
        from paper_scanner.core.enum import StepStatus
        assert result.status == StepStatus.SUCCESS
        assert result.stats["inserted"] == 10
        assert result.stats["citation_edges_inserted"] == 25
        assert result.stats["citation_edges_skipped"] == 3
        mock_pool.close.assert_called_once()

    @patch("paper_scanner.steps.upload_database.DatabaseConnectionPool")
    @patch("paper_scanner.steps.upload_database.PaperUploader")
    @patch("paper_scanner.steps.upload_database.load_dotenv")
    def test_execute_without_citation_edges(self, mock_load_dotenv, mock_uploader_class, mock_pool_class, mock_db, cache_dir, general_config):
        """Test that zero citation edges are handled correctly."""
        # Setup mocks
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool

        mock_uploader = Mock()
        mock_uploader_class.return_value = mock_uploader

        # Mock insert_papers without citation edges
        mock_uploader.insert_papers.return_value = {
            "inserted": 5,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "error_count": 0,
            "citation_edges": {
                "edges_inserted": 0,
                "edges_skipped": 0,
            },
        }

        # Create mock papers
        mock_papers = [Mock(spec=Paper) for _ in range(5)]
        mock_db.all.return_value = mock_papers

        step = create_step(mock_db, cache_dir, general_config)
        config = {"database_url": "postgresql://user:pass@localhost:5432/db"}

        result = step.execute(config, dry_run=False)

        assert isinstance(result, StepResult)
        from paper_scanner.core.enum import StepStatus
        assert result.status == StepStatus.SUCCESS
        assert result.stats["inserted"] == 5
        assert result.stats["citation_edges_inserted"] == 0
        assert result.stats["citation_edges_skipped"] == 0
        mock_pool.close.assert_called_once()
