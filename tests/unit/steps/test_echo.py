"""
Unit tests for the echo step.

Tests the EchoStep class including validation and execution.
"""

import pytest

from paper_scanner.steps.echo import EchoStep
from paper_scanner.core.models import Paper, Author
from paper_scanner.core.database import PapersDatabase


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def empty_db():
    """Create an empty database"""
    return PapersDatabase()


@pytest.fixture
def sample_db():
    """Create a database with sample papers"""
    db = PapersDatabase()
    
    papers = [
        Paper(
            cite_key="Smith2020",
            title="Machine Learning in Healthcare",
            abstract="A comprehensive review",
            keywords=["ML", "healthcare"],
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/ml.2020",
            year=2020,
            paper_type="journal_article"
        ),
        Paper(
            cite_key="Doe2021",
            title="Deep Learning Applications",
            abstract="Survey of applications",
            keywords=["DL"],
            authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
            doi="10.1234/dl.2021",
            year=2021,
            paper_type="conference_paper"
        ),
    ]
    
    for paper in papers:
        db.add(paper)
    
    return db


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    return tmp_path / "cache"


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidate:
    """Tests for echo step validation"""
    
    def test_validate_empty_config(self):
        """Should validate with empty config"""
        is_valid, errors = EchoStep.validate({})
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_string_message(self):
        """Should validate when message is a string"""
        config = {"message": "Hello, World!"}
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_empty_message(self):
        """Should validate with empty string message"""
        config = {"message": ""}
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_non_string_message(self):
        """Should fail validation when message is not a string"""
        config = {"message": 12345}
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
        assert "'message' must be a string" in errors[0]
    
    def test_validate_with_list_message(self):
        """Should fail validation when message is a list"""
        config = {"message": ["hello", "world"]}
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
    
    def test_validate_with_dict_message(self):
        """Should fail validation when message is a dict"""
        config = {"message": {"text": "hello"}}
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
    
    def test_validate_with_extra_fields(self):
        """Should validate with extra unexpected fields (ignored)"""
        config = {
            "message": "Test message",
            "extra_field": "ignored",
            "another_field": 123
        }
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is True
        assert errors == []


# ============================================================================
# EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Tests for echo step execution"""
    
    def test_execute_with_message(self, empty_db, temp_cache_dir):
        """Should execute and return message in output"""
        step = EchoStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {"message": "Test echo message"}
        
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == "Test echo message"
        assert "papers_count" in result
        assert result["papers_count"] == 0
    
    def test_execute_without_message(self, empty_db, temp_cache_dir):
        """Should execute with empty message when not provided"""
        step = EchoStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {}
        
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == ""
        assert result["papers_count"] == 0
    
    def test_execute_with_sample_data(self, sample_db, temp_cache_dir):
        """Should return correct paper count"""
        step = EchoStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Processing papers"}
        
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == "Processing papers"
        assert result["papers_count"] == 2
    
    def test_execute_verbose_mode(self, sample_db, temp_cache_dir):
        """Should execute in verbose mode without error"""
        step = EchoStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Verbose test"}
        
        result = step.execute(config, verbose=True)
        
        assert result["status"] == "ok"
        assert result["output"] == "Verbose test"
        assert result["papers_count"] == 2
    
    def test_execute_dry_run_mode(self, sample_db, temp_cache_dir):
        """Should execute in dry_run mode (no side effects for echo)"""
        step = EchoStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Dry run test"}
        
        result = step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["output"] == "Dry run test"
    
    def test_execute_debug_mode(self, sample_db, temp_cache_dir):
        """Should execute in debug mode without error"""
        step = EchoStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Debug test"}
        
        result = step.execute(config, debug=True)
        
        assert result["status"] == "ok"
        assert result["output"] == "Debug test"
    
    def test_execute_with_multiline_message(self, empty_db, temp_cache_dir):
        """Should handle multiline messages"""
        step = EchoStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        message = "Line 1\nLine 2\nLine 3"
        config = {"message": message}
        
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == message
    
    def test_execute_with_special_characters(self, empty_db, temp_cache_dir):
        """Should handle special characters in message"""
        step = EchoStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        message = "Special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"
        config = {"message": message}
        
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == message


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestEchoIntegration:
    """Integration tests for echo step"""
    
    def test_validate_then_execute(self, sample_db, temp_cache_dir):
        """Should validate config then successfully execute"""
        config = {"message": "Integration test"}
        
        # Validate first
        is_valid, errors = EchoStep.validate(config)
        assert is_valid is True
        assert errors == []
        
        # Then execute
        step = EchoStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result = step.execute(config)
        
        assert result["status"] == "ok"
        assert result["output"] == "Integration test"
        assert result["papers_count"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
