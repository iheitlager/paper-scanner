"""
Unit tests for the input step.

Tests reading JSON Lines from files and stdin with proper validation and error handling.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

import pytest

from paper_scanner.steps.input import validate, execute
from paper_scanner.core.models import Paper, Author
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import DiscoveryMethod


class TestInputValidation:
    """Test input step validation"""

    def test_validate_with_file_path(self):
        """Test validation succeeds with file path"""
        config = {"file": "data/papers.jsonl"}
        is_valid, errors = validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_stdin(self):
        """Test validation succeeds with stdin"""
        config = {"input": "stdin"}
        is_valid, errors = validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_both_file_and_stdin(self):
        """Test validation succeeds when both file and stdin specified"""
        config = {
            "file": "data/papers.jsonl",
            "input": "stdin"
        }
        is_valid, errors = validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_both_file_and_input(self):
        """Test validation fails when neither file nor input specified"""
        config = {}
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("Either 'file' or 'input' must be specified" in err for err in errors)

    def test_validate_invalid_file_type(self):
        """Test validation fails when file is not a string"""
        config = {"file": 123}
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("'file' must be a string" in err for err in errors)

    def test_validate_invalid_input_type(self):
        """Test validation fails when input is not a string"""
        config = {"input": 123}
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("'input' must be a string" in err for err in errors)

    def test_validate_invalid_input_source(self):
        """Test validation fails with invalid input source"""
        config = {"input": "file"}
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("'input' must be 'stdin'" in err for err in errors)

    def test_validate_valid_expected_count(self):
        """Test validation succeeds with valid expected_count"""
        config = {
            "file": "data/papers.jsonl",
            "expected_count": 10
        }
        is_valid, errors = validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_expected_count_type(self):
        """Test validation fails with non-integer expected_count"""
        config = {
            "file": "data/papers.jsonl",
            "expected_count": "10"
        }
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("'expected_count' must be a non-negative integer" in err for err in errors)

    def test_validate_negative_expected_count(self):
        """Test validation fails with negative expected_count"""
        config = {
            "file": "data/papers.jsonl",
            "expected_count": -5
        }
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("'expected_count' must be a non-negative integer" in err for err in errors)


class TestInputExecution:
    """Test input step execution"""

    @pytest.fixture
    def sample_papers_jsonl(self):
        """Create a temporary JSON Lines file with sample papers"""
        test_data = """{"cite_key": "Smith2024", "title": "Test Paper 1", "authors": [{"family_name": "Smith", "given_name": "John", "full_name": "John Smith"}], "year": 2024}
{"cite_key": "Doe2024", "title": "Test Paper 2", "authors": [{"family_name": "Doe", "given_name": "Jane", "full_name": "Jane Doe"}], "year": 2024}
{"cite_key": "Brown2023", "title": "Test Paper 3", "authors": [{"family_name": "Brown", "given_name": "Bob", "full_name": "Bob Brown"}], "year": 2023}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(test_data)
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        Path(temp_file).unlink()

    def test_execute_with_file_input(self, sample_papers_jsonl):
        """Test executing input step with file input"""
        papers_db = PapersDatabase()
        config = {
            "file": sample_papers_jsonl,
            "expected_count": 3
        }
        
        result = execute(config, papers_db, verbose=False)
        
        assert result["status"] == "ok"
        assert result["records_read"] == 3
        assert result["papers_converted"] == 3
        assert result["papers_failed"] == 0
        assert result["papers_added"] == 3
        assert result["papers_count"] == 3

    def test_execute_with_file_not_found(self):
        """Test executing input step with non-existent file"""
        papers_db = PapersDatabase()
        config = {
            "file": "/nonexistent/path/papers.jsonl"
        }
        
        result = execute(config, papers_db, verbose=False)
        
        assert result["status"] == "error"
        assert "File not found" in result["error"]

    def test_execute_with_expected_count_mismatch(self, sample_papers_jsonl):
        """Test execution with expected_count that doesn't match"""
        papers_db = PapersDatabase()
        config = {
            "file": sample_papers_jsonl,
            "expected_count": 5
        }
        
        result = execute(config, papers_db, verbose=False)
        
        # Should still process successfully, just with warning
        assert result["status"] == "ok"
        assert result["records_read"] == 3
        assert result["papers_added"] == 3

    def test_execute_with_invalid_json(self):
        """Test execution handles invalid JSON lines gracefully"""
        test_data = """{"cite_key": "Valid1", "title": "Valid Paper", "authors": [], "year": 2024}
{invalid json here}
{"cite_key": "Valid2", "title": "Another Valid Paper", "authors": [], "year": 2024}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(test_data)
            temp_file = f.name
        
        try:
            papers_db = PapersDatabase()
            config = {"file": temp_file}
            
            result = execute(config, papers_db, verbose=False)
            
            # Should skip the invalid line but still process valid ones
            assert result["status"] == "ok"
            assert result["records_read"] == 2  # Only 2 valid JSON lines
            assert result["papers_failed"] >= 0
        finally:
            Path(temp_file).unlink()

    def test_execute_with_empty_lines(self):
        """Test execution handles empty lines gracefully"""
        test_data = """{"cite_key": "Paper1", "title": "Paper 1", "authors": [], "year": 2024}

{"cite_key": "Paper2", "title": "Paper 2", "authors": [], "year": 2024}

"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(test_data)
            temp_file = f.name
        
        try:
            papers_db = PapersDatabase()
            config = {"file": temp_file}
            
            result = execute(config, papers_db, verbose=False)
            
            # Should skip empty lines and process only valid papers
            assert result["status"] == "ok"
            assert result["records_read"] == 2
        finally:
            Path(temp_file).unlink()

    def test_execute_dry_run(self, sample_papers_jsonl):
        """Test execution with dry_run=True doesn't add papers"""
        papers_db = PapersDatabase()
        config = {
            "file": sample_papers_jsonl,
            "expected_count": 3
        }
        
        result = execute(config, papers_db, verbose=False, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["records_read"] == 3
        assert result["papers_converted"] == 3
        assert result["papers_added"] == 0  # Dry run doesn't add
        assert result["papers_count"] == 0  # No papers added to DB

    def test_execute_with_stdin(self):
        """Test executing input step with stdin"""
        test_data = """{"cite_key": "Paper1", "title": "From stdin", "authors": [], "year": 2024}
{"cite_key": "Paper2", "title": "Also stdin", "authors": [], "year": 2024}
"""
        papers_db = PapersDatabase()
        config = {"input": "stdin"}
        
        # Mock stdin
        with patch('sys.stdin', StringIO(test_data)):
            result = execute(config, papers_db, verbose=False)
        
        assert result["status"] == "ok"
        assert result["records_read"] == 2
        assert result["papers_added"] == 2

    def test_execute_verbose_output(self, sample_papers_jsonl):
        """Test verbose output is produced"""
        papers_db = PapersDatabase()
        config = {
            "file": sample_papers_jsonl,
            "expected_count": 3
        }
        
        result = execute(config, papers_db, verbose=True)
        
        # Just verify that execution succeeds and returns verbose result
        assert result["status"] == "ok"
        assert result["records_read"] == 3

    def test_execute_papers_have_discovery_method(self, sample_papers_jsonl):
        """Test that imported papers have MANUAL discovery method"""
        papers_db = PapersDatabase()
        config = {"file": sample_papers_jsonl}
        
        result = execute(config, papers_db, verbose=False)
        
        assert result["status"] == "ok"
        assert result["papers_added"] == 3
        
        # Get papers from database and check discovery method
        for paper in papers_db.papers:
            assert paper.discovery is not None
            assert paper.discovery.method == DiscoveryMethod.MANUAL

    def test_execute_path_expansion(self):
        """Test that ~ in file paths is expanded"""
        test_data = '{"cite_key": "Test", "title": "Test", "authors": [], "year": 2024}\n'
        
        # Create temp file in home directory
        home = Path.home()
        temp_dir = home / ".test_paper_scanner"
        temp_dir.mkdir(exist_ok=True)
        
        temp_file = temp_dir / "test.jsonl"
        temp_file.write_text(test_data)
        
        try:
            papers_db = PapersDatabase()
            # Use ~ to reference home directory
            config = {
                "file": str(temp_file).replace(str(home), "~")
            }
            
            result = execute(config, papers_db, verbose=False)
            
            assert result["status"] == "ok"
            assert result["records_read"] == 1
        finally:
            temp_file.unlink()
            temp_dir.rmdir()

    def test_execute_file_precedence_over_stdin(self, sample_papers_jsonl):
        """Test that file takes precedence when both file and input are specified"""
        papers_db = PapersDatabase()
        stdin_data = '{"cite_key": "StdinPaper", "title": "From stdin", "authors": [], "year": 2024}\n'
        
        config = {
            "file": sample_papers_jsonl,
            "input": "stdin"
        }
        
        with patch('sys.stdin', StringIO(stdin_data)):
            result = execute(config, papers_db, verbose=False)
        
        # Should read from file, not stdin
        assert result["status"] == "ok"
        assert result["records_read"] == 3  # From file, not stdin

    def test_execute_with_incomplete_paper_data(self):
        """Test execution with papers missing some fields"""
        test_data = '{"cite_key": "Paper1", "title": "Minimal Paper"}\n'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(test_data)
            temp_file = f.name
        
        try:
            papers_db = PapersDatabase()
            config = {"file": temp_file}
            
            result = execute(config, papers_db, verbose=False)
            
            # Should still work with minimal data
            assert result["status"] == "ok"
            assert result["records_read"] == 1
        finally:
            Path(temp_file).unlink()

    def test_execute_result_structure(self, sample_papers_jsonl):
        """Test that execute result has all expected fields"""
        papers_db = PapersDatabase()
        config = {"file": sample_papers_jsonl}
        
        result = execute(config, papers_db, verbose=False)
        
        # Check all expected fields
        assert "status" in result
        assert "source" in result
        assert "records_read" in result
        assert "papers_converted" in result
        assert "papers_failed" in result
        assert "papers_added" in result
        assert "papers_count" in result
        
        assert isinstance(result["status"], str)
        assert isinstance(result["records_read"], int)
        assert isinstance(result["papers_count"], int)
