"""
Tests for CitationsStep validation and forward citations configuration

Tests the validate() method and forward citations extraction configuration.
"""

import tempfile
from pathlib import Path

import pytest

from paper_scanner.steps.citations import CitationsStep


class TestValidateForwardConfig:
    """Test CitationsStep.validate() static method for forward configuration"""

    def test_validate_invalid_config_defaults(self):
        """Test validation of invalid configuration"""
        config = {
            "forward": {
                "sources": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_forward_config_with_paper_types(self):
        """Test validation with explicit paper-types for forward"""
        config = {
            "paper-type": ["journal_article", "conference_paper"],
            "continue_on_not_found": True,
            "forward": {
                "citations": ["crossref"],
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_forward_not_dict(self):
        """Test validation fails when forward is not a dict"""
        config = {
            "forward": "crossref"
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'forward' must be a dictionary" in err for err in errors)

    def test_validate_forward_citations_not_string_or_list(self):
        """Test validation fails when forward.citations is not string or list"""
        config = {
            "forward": {
                "citations": 123
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'forward.citations' must be a string or list" in err for err in errors)

    def test_validate_forward_citations_as_string(self):
        """Test validation accepts forward citations as a string"""
        config = {
            "forward": {
                "citations": "crossref"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_forward_citations_as_list(self):
        """Test validation accepts forward citations as a list"""
        config = {
            "forward": {
                "citations": ["crossref", "openalex"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_forward_citations_list_with_invalid_item(self):
        """Test validation fails when citations list contains non-string items"""
        config = {
            "forward": {
                "citations": ["crossref", 123]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("items must be strings" in err for err in errors)

    def test_validate_forward_details_as_string(self):
        """Test validation accepts forward details as a string"""
        config = {
            "forward": {
                "details": "openalex"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_forward_details_as_list(self):
        """Test validation accepts forward details as a list"""
        config = {
            "forward": {
                "details": ["crossref", "openalex"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_forward_details_not_string_or_list(self):
        """Test validation fails when forward.details is not string or list"""
        config = {
            "forward": {
                "details": 456
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'forward.details' must be a string or list" in err for err in errors)


    def test_validate_forward_output_errors_nonexistent_path(self):
        """Test validation fails when output_errors path doesn't exist"""
        config = {
            "forward": {
                "sources": ["crossref"],
                "output_errors": "/nonexistent/path/errors.jsonl"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'forward.output_errors' must be a valid file path" in err for err in errors)



    def test_validate_forward_with_all_options(self):
        """Test validation with all forward configuration options"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            error_file = Path(tmp_dir) / "errors.jsonl"
            error_file.touch()
            
            config = {
                "paper-type": ["journal_article", "conference_paper"],
                "continue_on_not_found": True,
                "limit": 500,
                "forward": {
                    "citations": ["crossref", "openalex"],
                    "details": ["crossref", "openalex"],
                    "output_errors": str(error_file)
                }
            }
            
            is_valid, errors = CitationsStep.validate(config)
            
            assert is_valid is True
            assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
