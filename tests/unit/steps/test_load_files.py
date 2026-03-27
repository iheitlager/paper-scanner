"""
Tests for the load_files step

Tests file loading, DOI extraction, and PDF processing
"""

from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError
from paper_scanner.core.step_result import StepResult
from paper_scanner.steps.load_files import LoadFilesStep


class TestValidate:
    """Test LoadFilesStep.validate() static method"""

    def test_validate_valid_config(self):
        """Test validation of valid configuration"""
        config = {
            "file_path": "/path/to/pdfs",
            "store_path": "/path/to/store"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_expected_count(self):
        """Test validation with optional expected_count parameter"""
        config = {
            "file_path": "/path/to/pdfs",
            "store_path": "/path/to/store",
            "expected_count": 10
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_file_path(self):
        """Test validation fails when file_path is missing"""
        config = {
            "store_path": "/path/to/store"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'file_path' is required" in errors

    def test_validate_missing_store_path(self):
        """Test validation fails when store_path is missing"""
        config = {
            "file_path": "/path/to/pdfs"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'store_path' is required" in errors

    def test_validate_file_path_not_string(self):
        """Test validation fails when file_path is not a string"""
        config = {
            "file_path": 123,
            "store_path": "/path/to/store"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'file_path' must be a string" in errors

    def test_validate_store_path_not_string(self):
        """Test validation fails when store_path is not a string"""
        config = {
            "file_path": "/path/to/pdfs",
            "store_path": 456
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'store_path' must be a string" in errors

    def test_validate_expected_count_negative(self):
        """Test validation fails when expected_count is negative"""
        config = {
            "file_path": "/path/to/pdfs",
            "store_path": "/path/to/store",
            "expected_count": -1
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'expected_count' must be a non-negative integer" in errors

    def test_validate_expected_count_not_integer(self):
        """Test validation fails when expected_count is not an integer"""
        config = {
            "file_path": "/path/to/pdfs",
            "store_path": "/path/to/store",
            "expected_count": "ten"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert "'expected_count' must be a non-negative integer" in errors

    def test_validate_multiple_errors(self):
        """Test validation returns multiple errors"""
        config = {
            "file_path": 123,
            "store_path": 456,
            "expected_count": "invalid"
        }

        is_valid, errors = LoadFilesStep.validate(config)

        assert is_valid is False
        assert len(errors) >= 3


class TestExecute:
    """Test LoadFilesStep.execute() method"""

    def test_execute_nonexistent_path(self, tmp_path):
        """Test execute with non-existent file path"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": "/nonexistent/path",
            "store_path": str(tmp_path / "store")
        }

        with pytest.raises(ConfigurationError) as exc_info:
            step.execute(config, verbose=False, dry_run=False)

        assert "File path does not exist" in str(exc_info.value)

    def test_execute_empty_directory(self, tmp_path):
        """Test execute with empty PDF directory"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.WARNING
        assert result.stats["papers_loaded"] == 0
        assert result.stats["papers_failed"] == 0
        assert "No PDF files found" in result.message

    def test_execute_creates_store_path(self, tmp_path):
        """Test execute creates store_path if it doesn't exist"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "nonexistent" / "store"

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        step.execute(config, verbose=False, dry_run=False)

        # Store path should be created
        assert store_path.exists()

    def test_execute_dry_run(self, tmp_path):
        """Test execute with dry_run flag doesn't store anything"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create a mock PDF file
        pdf_file = file_path / "test.pdf"
        pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to avoid actual PDF processing
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.exists.return_value = True
            mock_reader.get_file_info.return_value = {
                "file_name": "test.pdf",
                "file_size_bytes": 1024
            }
            mock_reader.extract_doi.return_value = "10.1234/test"
            mock_reader.get_page_count.return_value = 5
            mock_reader_class.return_value = mock_reader

            step.execute(config, verbose=False, dry_run=True)

        # In dry_run mode, nothing should be stored or copied
        assert db.count(primary_only=False) == 0

    def test_execute_with_verbose(self, tmp_path, capsys):
        """Test execute with verbose output"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        result = step.execute(config, verbose=True, dry_run=False)

        # Should execute without error
        assert isinstance(result, StepResult)
        assert result.status == StepStatus.WARNING

    def test_execute_file_not_found_during_read(self, tmp_path):
        """Test handling when PDF file is not found during processing"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create a mock PDF file
        pdf_file = file_path / "test.pdf"
        pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to return exists=False
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.exists.return_value = False
            mock_reader_class.return_value = mock_reader

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.stats["papers_failed"] == 1
        assert result.stats["papers_loaded"] == 0

    def test_execute_no_doi_extracted(self, tmp_path):
        """Test handling when no DOI can be extracted from PDF"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create a mock PDF file
        pdf_file = file_path / "test.pdf"
        pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to return no DOI
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.exists.return_value = True
            mock_reader.get_file_info.return_value = {
                "file_name": "test.pdf",
                "file_size_bytes": 1024
            }
            mock_reader.extract_doi.return_value = None
            mock_reader_class.return_value = mock_reader

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.stats["papers_failed"] == 1
        assert result.stats["papers_loaded"] == 0

    def test_execute_successful_processing(self, tmp_path):
        """Test successful PDF processing and storage"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create a mock PDF file
        pdf_file = file_path / "test.pdf"
        pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to return valid data
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class, \
             patch('paper_scanner.steps.load_files.shutil.copy2'):
            mock_reader = MagicMock()
            mock_reader.exists.return_value = True
            mock_reader.get_file_info.return_value = {
                "file_name": "test.pdf",
                "file_path": str(pdf_file),
                "file_created_time": "2024-01-01T00:00:00",
                "file_hash": "mockhash",
                "file_size_bytes": 1024
            }
            mock_reader.extract_doi.return_value = "10.1234/test"
            mock_reader.get_page_count.return_value = 5
            mock_reader_class.return_value = mock_reader

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_loaded"] == 1
        assert result.stats["papers_failed"] == 0
        assert result.stats["files_copied"] == 1
        assert db.count(primary_only=False) == 1

    def test_execute_multiple_files(self, tmp_path):
        """Test processing multiple PDF files"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create multiple mock PDF files
        for i in range(3):
            pdf_file = file_path / f"test{i}.pdf"
            pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to return valid data for all PDFs
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class, \
             patch('paper_scanner.steps.load_files.shutil.copy2'):
            def reader_factory(path):
                mock_reader = MagicMock()
                mock_reader.exists.return_value = True
                mock_reader.get_file_info.return_value = {
                    "file_name": path.name,
                    "file_path": str(path),
                    "file_created_time": "2024-01-01T00:00:00",
                    "file_hash": "mockhash",
                    "file_size_bytes": 1024
                }
                mock_reader.extract_doi.return_value = f"10.1234/test{path.stem}"
                mock_reader.get_page_count.return_value = 5
                return mock_reader

            mock_reader_class.side_effect = reader_factory

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_loaded"] == 3
        assert result.stats["papers_failed"] == 0
        assert result.stats["files_copied"] == 3
        assert db.count(primary_only=False) == 3

    def test_execute_mixed_success_and_failure(self, tmp_path):
        """Test processing mix of successful and failed PDFs"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create multiple mock PDF files
        for i in range(3):
            pdf_file = file_path / f"test{i}.pdf"
            pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path)
        }

        # Mock FileReader to fail on second file
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class, \
             patch('paper_scanner.steps.load_files.shutil.copy2'):
            def reader_factory(path):
                mock_reader = MagicMock()
                mock_reader.exists.return_value = True
                mock_reader.get_file_info.return_value = {
                    "file_name": path.name,
                    "file_path": str(path),
                    "file_size_bytes": 1024,
                    "file_created_time": "2024-01-01T00:00:00",
                    "file_hash": "mockhash"
                }

                # Fail on test1.pdf (no DOI)
                if "test1" in str(path):
                    mock_reader.extract_doi.return_value = None
                else:
                    mock_reader.extract_doi.return_value = f"10.1234/{path.stem}"
                    mock_reader.get_page_count.return_value = 5

                return mock_reader

            mock_reader_class.side_effect = reader_factory

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.WARNING
        assert result.stats["papers_loaded"] == 2
        assert result.stats["papers_failed"] == 1
        assert result.stats["files_copied"] == 2

    def test_execute_with_expected_count(self, tmp_path):
        """Test execute with expected_count in config"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        file_path = tmp_path / "pdfs"
        file_path.mkdir()

        store_path = tmp_path / "store"

        # Create one PDF file
        pdf_file = file_path / "test.pdf"
        pdf_file.write_bytes(b"mock pdf content")

        db = PapersDatabase()
        step = LoadFilesStep(
            general_config={},
            db=db,
            cache_dir=cache_dir
        )

        config = {
            "file_path": str(file_path),
            "store_path": str(store_path),
            "expected_count": 1
        }

        # Mock FileReader
        with patch('paper_scanner.steps.load_files.FileReader') as mock_reader_class, \
             patch('paper_scanner.steps.load_files.shutil.copy2'):
            mock_reader = MagicMock()
            mock_reader.exists.return_value = True
            mock_reader.get_file_info.return_value = {
                "file_name": "test.pdf",
                "file_path": str(pdf_file),
                "file_created_time": "2024-01-01T00:00:00",
                "file_hash": "mockhash",
                "file_size_bytes": 1024
            }
            mock_reader.extract_doi.return_value = "10.1234/test"
            mock_reader.get_page_count.return_value = 5
            mock_reader_class.return_value = mock_reader

            result = step.execute(config, verbose=False, dry_run=False)

        assert isinstance(result, StepResult)
        assert result.stats["papers_loaded"] == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
