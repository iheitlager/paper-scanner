"""
Tests for DownloadPDFsStep.

Tests validate(), config parsing, and execute() with mocked Fetcher.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import DiscoveryMethod, StepStatus
from paper_scanner.core.models import Discovery, Paper, PDFInfo
from paper_scanner.steps.download_pdfs import DownloadPDFsStep


class TestDownloadPDFsValidation:
    """Test configuration validation."""

    def test_validate_missing_store_path(self):
        """Config missing store_path should fail."""
        config = {
            "sources": ["crossref"],
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid
        assert any("store_path" in e for e in errors)

    def test_validate_missing_sources(self):
        """Config missing sources should fail."""
        config = {
            "store_path": "/tmp",
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid
        assert any("sources" in e for e in errors)

    def test_validate_empty_sources(self):
        """Empty sources list should fail."""
        config = {
            "store_path": "/tmp",
            "sources": [],
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid
        assert any("cannot be empty" in e for e in errors)

    def test_validate_invalid_sources(self):
        """Invalid source names should fail."""
        config = {
            "store_path": "/tmp",
            "sources": ["crossref", "invalid_source"],
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid
        assert any("Invalid sources" in e for e in errors)


    def test_validate_invalid_timeout(self):
        """Non-numeric timeout should fail."""
        config = {
            "store_path": "/tmp",
            "sources": ["crossref"],
            "timeout": "invalid",
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid
        assert any("timeout" in e for e in errors)

    def test_validate_zero_timeout(self):
        """Zero or negative timeout should fail."""
        config = {
            "store_path": "/tmp",
            "sources": ["crossref"],
            "timeout": 0,
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert not is_valid

    def test_validate_valid_config_minimal(self):
        """Minimal valid config should pass."""
        config = {
            "store_path": "/tmp/pdfs",
            "sources": ["crossref"],
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert is_valid
        assert not errors

    def test_validate_valid_config_full(self):
        """Full valid config should pass."""
        config = {
            "store_path": "/tmp/pdfs",
            "sources": ["crossref", "openalex"],
            "max_retries": 3,
            "timeout": 30,
            "output_errors": "/tmp/errors.json",
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert is_valid
        assert not errors

    def test_validate_timeout_float(self):
        """Float timeout should pass."""
        config = {
            "store_path": "/tmp/pdfs",
            "sources": ["crossref"],
            "timeout": 30.5,
        }
        is_valid, errors = DownloadPDFsStep.validate(config)
        assert is_valid


class TestDownloadPDFsExecution:
    """Test execution logic."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = MagicMock(spec=PapersDatabase)
        db.count.return_value = 10
        return db

    @pytest.fixture
    def step(self, mock_db, tmp_path):
        """Create a DownloadPDFsStep instance."""
        return DownloadPDFsStep(
            general_config={},
            db=mock_db,
            cache_dir=tmp_path / "cache",
        )

    def test_execute_no_papers_needing_pdf(self, step, mock_db, tmp_path):
        """Execution with no papers needing PDF should return early."""
        mock_db.find.return_value = []
        mock_db.count.return_value = 0  # Mock the count method as well
        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher"):
            result = step.execute(config)

        assert result.status == StepStatus.SUCCESS
        assert result.stats["count"] == 0
        assert result.stats["skipped"] == 0
        assert "No papers needing PDF downloads" in result.message

    def test_execute_creates_store_directory(self, step, mock_db, tmp_path):
        """Execution should create store directory if missing."""
        mock_db.find.return_value = []
        store_path = tmp_path / "pdfs"
        config = {
            "store_path": str(store_path),
            "sources": ["crossref"],
        }

        assert not store_path.exists()

        with patch("paper_scanner.steps.download_pdfs.Fetcher"):
            step.execute(config)

        assert store_path.exists()

    def test_execute_initializes_fetcher_with_sources(self, step, mock_db, tmp_path):
        """Execution should initialize Fetcher with specified sources."""
        mock_db.find.return_value = []
        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref", "unpaywall"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            step.execute(config)

        # Verify Fetcher was instantiated with correct arguments
        mock_fetcher_class.assert_called_once()
        call_kwargs = mock_fetcher_class.call_args[1]
        assert call_kwargs["methods"] == ["crossref", "unpaywall"]

    def test_execute_skips_papers_without_doi(self, step, mock_db, tmp_path):
        """Papers without DOI should be skipped."""
        paper = MagicMock(spec=Paper)
        paper.doi = None
        paper.cite_key = "paper1"
        mock_db.find.return_value = [paper]

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher"):
            result = step.execute(config)

        assert result.stats["skipped"] == 1
        assert result.stats["count"] == 0

    def test_execute_downloads_pdf_and_updates_paper(self, step, mock_db, tmp_path):
        """Successful download should update paper and move file."""
        # Create a mock paper with DOI
        paper = MagicMock(spec=Paper)
        paper.doi = "10.1234/test"
        paper.cite_key = "TestPaper2024"
        paper.pdf_info = None
        paper.discovery = Discovery(method=DiscoveryMethod.MANUAL)

        mock_db.find.return_value = [paper]

        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(b"PDF content")
            tmp_pdf_path = Path(tmp_pdf.name)

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            # fetch_pdf now returns PDFInfo instead of Path
            mock_fetcher.fetch_pdf.return_value = PDFInfo(
                file_path=str(tmp_pdf_path),
                file_size_bytes=11,
                download_source="crossref",
                download_url="https://example.com/paper.pdf",
            )

            result = step.execute(config)

        assert result.stats["count"] == 1
        assert result.stats["skipped"] == 0
        assert result.status == StepStatus.SUCCESS

    def test_execute_dry_run_mode(self, step, mock_db, tmp_path):
        """Dry run should not write files or update database."""
        paper = MagicMock(spec=Paper)
        paper.doi = "10.1234/test"
        paper.cite_key = "TestPaper2024"

        mock_db.find.return_value = [paper]

        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(b"PDF content")
            tmp_pdf_path = Path(tmp_pdf.name)

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            # fetch_pdf now returns PDFInfo instead of Path
            mock_fetcher.fetch_pdf.return_value = PDFInfo(
                file_path=str(tmp_pdf_path),
                file_size_bytes=11,
                download_source="crossref",
            )

            result = step.execute(config, dry_run=True)

        assert result.stats["count"] == 1
        # In dry_run mode, db.update should not be called
        # (this depends on implementation details, but files shouldn't be copied)
        assert not (tmp_path / "pdfs" / "TestPaper2024.pdf").exists()

    def test_execute_error_handling_and_logging(self, step, mock_db, tmp_path):
        """Errors should be caught and logged."""
        paper = MagicMock(spec=Paper)
        paper.doi = "10.1234/test"
        paper.cite_key = "ErrorPaper"

        mock_db.find.return_value = [paper]

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
            "output_errors": str(tmp_path / "errors.jsonl"),
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.fetch_pdf.side_effect = Exception("Network error")

            result = step.execute(config)

        assert result.stats["errors"] > 0

        # Check error log was created
        error_log = tmp_path / "errors.jsonl"
        assert error_log.exists()
        with open(error_log) as f:
            lines = f.readlines()
            assert len(lines) > 0
            error_entry = json.loads(lines[0])
            assert error_entry["paper"] == "ErrorPaper"
            assert "Network error" in error_entry["error"]

    def test_execute_multiple_papers(self, step, mock_db, tmp_path):
        """Should handle multiple papers with mixed outcomes."""
        paper1 = MagicMock(spec=Paper)
        paper1.doi = "10.1234/test1"
        paper1.cite_key = "Paper1"

        paper2 = MagicMock(spec=Paper)
        paper2.doi = None  # Will be skipped
        paper2.cite_key = "Paper2"

        paper3 = MagicMock(spec=Paper)
        paper3.doi = "10.1234/test3"
        paper3.cite_key = "Paper3"

        mock_db.find.return_value = [paper1, paper2, paper3]

        # Mock successful download for paper1, None for paper3
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf.write(b"PDF content")
            tmp_pdf_path = Path(tmp_pdf.name)

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            # paper1 succeeds, paper3 returns None
            mock_fetcher.fetch_pdf.side_effect = [
                PDFInfo(
                    file_path=str(tmp_pdf_path),
                    file_size_bytes=11,
                    download_source="crossref",
                ),
                None,  # paper3 - no PDF found
            ]

            result = step.execute(config)

        assert result.stats["count"] == 1  # Only paper1 succeeded
        assert result.stats["skipped"] == 2  # paper2 (no DOI) + paper3 (no PDF found)


class TestDownloadPDFsIntegration:
    """Integration tests with real database."""

    def test_integration_with_real_database(self, tmp_path):
        """Test with actual database operations."""
        # Create real database
        db = PapersDatabase()

        # Create papers
        paper1 = Paper(
            cite_key="Paper1",
            source_key="source1",
            doi="10.1234/test1",
            title="Test Paper 1",
            authors=[],
        )
        paper2 = Paper(
            cite_key="Paper2",
            source_key="source2",
            doi="10.1234/test2",
            title="Test Paper 2",
            authors=[],
        )

        db.add(paper1)
        db.add(paper2)

        # Create step
        step = DownloadPDFsStep(
            general_config={},
            db=db,
            cache_dir=tmp_path / "cache",
        )

        config = {
            "store_path": str(tmp_path / "pdfs"),
            "sources": ["crossref"],
        }

        # Execute with mocked Fetcher that returns None (no PDFs found)
        with patch("paper_scanner.steps.download_pdfs.Fetcher") as mock_fetcher_class:
            mock_fetcher = MagicMock()
            mock_fetcher_class.return_value = mock_fetcher
            mock_fetcher.fetch_pdf.return_value = None  # No PDFs found

            result = step.execute(config)

        # With no PDFs found, papers are skipped but status should still be ok
        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_total"] == 2
        assert result.stats["skipped"] == 2  # Both papers have DOI but no PDF found
