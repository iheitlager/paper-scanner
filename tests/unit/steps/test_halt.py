"""
Unit tests for the halt step.

Tests the HaltStep class including validation and execution.
"""

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper
from paper_scanner.steps.halt import HaltException, HaltStep

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
        Paper(
            cite_key="Brown2022",
            title="Natural Language Processing Advances",
            abstract="Recent advances",
            keywords=[],
            authors=[],
            doi=None,
            year=2022,
            paper_type=None
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
    """Tests for halt step validation"""
    
    def test_validate_empty_config(self):
        """Should validate with empty config"""
        is_valid, errors = HaltStep.validate({})
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_string_message(self):
        """Should validate when message is a string"""
        config = {"message": "Custom halt message"}
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_empty_message(self):
        """Should validate with empty string message"""
        config = {"message": ""}
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is True
        assert errors == []
    
    def test_validate_with_non_string_message(self):
        """Should fail validation when message is not a string"""
        config = {"message": 12345}
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
        assert "'message' must be a string" in errors[0]
    
    def test_validate_with_list_message(self):
        """Should fail validation when message is a list"""
        config = {"message": ["stop", "now"]}
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
    
    def test_validate_with_dict_message(self):
        """Should fail validation when message is a dict"""
        config = {"message": {"text": "halt"}}
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
    
    def test_validate_with_extra_fields(self):
        """Should validate with extra unexpected fields (ignored)"""
        config = {
            "message": "Stop processing",
            "extra_field": "ignored",
            "another_field": 123
        }
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is True
        assert errors == []


# ============================================================================
# EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Tests for halt step execution"""
    
    def test_execute_raises_halt_exception(self, empty_db, temp_cache_dir):
        """Should raise HaltException on execution"""
        step = HaltStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {"message": "Test halt"}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == "Test halt"
    
    def test_execute_default_message(self, empty_db, temp_cache_dir):
        """Should use default message when none provided"""
        step = HaltStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == "Pipeline halted"
    
    def test_execute_custom_message(self, empty_db, temp_cache_dir):
        """Should use custom message from config"""
        step = HaltStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {"message": "Processing complete, stopping here"}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == "Processing complete, stopping here"
    
    def test_execute_with_sample_data(self, sample_db, temp_cache_dir):
        """Should include paper count before halting"""
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Halt after processing"}
        
        with pytest.raises(HaltException):
            step.execute(config)
        
        # Verify the step was created correctly and has access to db
        assert step.db.count(primary_only=False) == 3
    
    def test_execute_verbose_mode(self, sample_db, temp_cache_dir):
        """Should raise exception even in verbose mode"""
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Verbose halt"}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config, verbose=True)
        
        assert str(exc_info.value) == "Verbose halt"
    
    def test_execute_dry_run_mode(self, sample_db, temp_cache_dir):
        """Should still halt in dry_run mode"""
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Dry run halt"}
        
        with pytest.raises(HaltException):
            step.execute(config, dry_run=True)
    
    def test_execute_debug_mode(self, sample_db, temp_cache_dir):
        """Should raise exception in debug mode"""
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Debug halt"}
        
        with pytest.raises(HaltException):
            step.execute(config, debug=True)
    
    def test_execute_with_multiline_message(self, empty_db, temp_cache_dir):
        """Should handle multiline messages"""
        step = HaltStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        message = "Line 1\nLine 2\nLine 3"
        config = {"message": message}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == message
    
    def test_execute_with_special_characters(self, empty_db, temp_cache_dir):
        """Should handle special characters in message"""
        step = HaltStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        message = "Special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"
        config = {"message": message}
        
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == message


# ============================================================================
# HALT EXCEPTION TESTS
# ============================================================================

class TestHaltException:
    """Tests for HaltException class"""
    
    def test_halt_exception_creation(self):
        """Should create HaltException with message"""
        exc = HaltException("Test message")
        assert str(exc) == "Test message"
    
    def test_halt_exception_is_exception(self):
        """HaltException should be an Exception subclass"""
        exc = HaltException("Test")
        assert isinstance(exc, Exception)
    
    def test_halt_exception_can_be_caught(self):
        """HaltException should be catchable as Exception"""
        with pytest.raises(Exception):
            raise HaltException("Test")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestHaltIntegration:
    """Integration tests for halt step"""
    
    def test_validate_then_execute(self, sample_db, temp_cache_dir):
        """Should validate config then execute and halt"""
        config = {"message": "Integration test halt"}
        
        # Validate first
        is_valid, errors = HaltStep.validate(config)
        assert is_valid is True
        assert errors == []
        
        # Then execute
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        with pytest.raises(HaltException) as exc_info:
            step.execute(config)
        
        assert str(exc_info.value) == "Integration test halt"
    
    def test_halt_stops_pipeline(self, sample_db, temp_cache_dir):
        """Should effectively stop pipeline execution when raised"""
        step = HaltStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"message": "Pipeline stopped"}
        
        # Simulate pipeline execution that should not reach code after raise
        execution_reached_after_halt = False
        
        try:
            step.execute(config)
            execution_reached_after_halt = True
        except HaltException:
            pass
        
        # Should not reach this point if HaltException is properly raised
        assert execution_reached_after_halt is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
