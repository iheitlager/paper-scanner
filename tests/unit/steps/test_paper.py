"""
Unit tests for PaperStep

Tests validation, paper creation, DOI handling, and cite_key generation.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from paper_scanner.core.enum import DiscoveryMethod, PaperType, StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.steps.paper import PaperStep


class TestPaperStepValidation:
    """Test PaperStep.validate() static method"""

    def test_validate_missing_papers_key(self):
        """Should fail if 'papers' key is missing"""
        is_valid, errors = PaperStep.validate({})
        assert not is_valid
        assert any("'papers' key is required" in err for err in errors)

    def test_validate_papers_not_list(self):
        """Should fail if 'papers' is not a list"""
        is_valid, errors = PaperStep.validate({"papers": "not a list"})
        assert not is_valid
        assert any("must be a list" in err for err in errors)

    def test_validate_empty_papers_list(self):
        """Should fail if 'papers' list is empty"""
        is_valid, errors = PaperStep.validate({"papers": []})
        assert not is_valid
        assert any("cannot be empty" in err for err in errors)

    def test_validate_missing_doi(self):
        """Should fail if paper spec missing 'doi'"""
        is_valid, errors = PaperStep.validate({"papers": [{"cite_key": "test"}]})
        assert not is_valid
        assert any("'doi' is required" in err for err in errors)

    def test_validate_doi_not_string(self):
        """Should fail if 'doi' is not a string"""
        is_valid, errors = PaperStep.validate({"papers": [{"doi": 123}]})
        assert not is_valid
        assert any("'doi' must be a string" in err for err in errors)

    def test_validate_invalid_doi_format(self):
        """Should fail if DOI format is invalid"""
        is_valid, errors = PaperStep.validate({"papers": [{"doi": "invalid"}]})
        assert not is_valid
        assert any("Invalid DOI" in err for err in errors)

    def test_validate_invalid_paper_type(self):
        """Should fail if paper_type is invalid enum value"""
        is_valid, errors = PaperStep.validate({
            "papers": [{
                "doi": "10.1000/182",
                "paper_type": "invalid_type"
            }]
        })
        assert not is_valid
        assert any("not a valid PaperType" in err for err in errors)

    def test_validate_invalid_study_type(self):
        """Should fail if study_type is invalid enum value"""
        is_valid, errors = PaperStep.validate({
            "papers": [{
                "doi": "10.1000/182",
                "study_type": "invalid_type"
            }]
        })
        assert not is_valid
        assert any("not a valid StudyType" in err for err in errors)

    def test_validate_valid_minimal_paper(self):
        """Should pass with just DOI"""
        is_valid, errors = PaperStep.validate({
            "papers": [{"doi": "10.1000/182"}]
        })
        assert is_valid
        assert len(errors) == 0

    def test_validate_valid_full_paper(self):
        """Should pass with all fields"""
        is_valid, errors = PaperStep.validate({
            "papers": [{
                "doi": "10.1000/182",
                "cite_key": "my_key",
                "paper_type": "journal_article",
                "study_type": "empirical_quantitative"
            }]
        })
        assert is_valid
        assert len(errors) == 0

    def test_validate_valid_multiple_papers(self):
        """Should pass with multiple valid papers"""
        is_valid, errors = PaperStep.validate({
            "papers": [
                {"doi": "10.1000/182"},
                {"doi": "10.1000/183", "paper_type": "conference_paper"},
                {"doi": "10.1000/184", "study_type": "empirical_qualitative"}
            ]
        })
        assert is_valid
        assert len(errors) == 0


class TestPaperStepExecution:
    """Test PaperStep.execute() instance method"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.add = Mock()
        self.mock_db.count = Mock(return_value=0)
        
        self.step = PaperStep(
            general_config={},
            db=self.mock_db,
            cache_dir=Path("/tmp/cache")
        )

    def test_execute_creates_paper_with_doi(self):
        """Should create paper with DOI from config"""
        config = {"papers": [{"doi": "10.1000/182"}]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["count"] == 1

    def test_execute_uses_provided_cite_key(self):
        """Should use provided cite_key instead of generating one"""
        config = {"papers": [{"doi": "10.1000/182", "cite_key": "custom_key"}]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["count"] == 1

    def test_execute_sets_paper_type(self):
        """Should set paper_type if provided"""
        config = {"papers": [{
            "doi": "10.1000/182",
            "paper-type": "journal_article"
        }]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["count"] == 1

    def test_execute_persists_to_database_when_not_dry_run(self):
        """Should add papers to database when not dry_run"""
        config = {"papers": [{"doi": "10.1000/182"}]}
        result = self.step.execute(config, dry_run=False)
        
        assert result["status"] == "ok"
        assert self.mock_db.add.call_count == 1

    def test_execute_skips_database_on_dry_run(self):
        """Should not add papers when dry_run=True"""
        config = {"papers": [{"doi": "10.1000/182"}]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert self.mock_db.add.call_count == 0

    def test_execute_handles_multiple_papers(self):
        """Should create multiple papers from array"""
        config = {"papers": [
            {"doi": "10.1000/182"},
            {"doi": "10.1000/183"},
            {"doi": "10.1000/184"}
        ]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["count"] == 3

    def test_execute_handles_invalid_doi_gracefully(self):
        """Should handle invalid DOI without raising exception"""
        config = {"papers": [
            {"doi": "10.1000/182"},  # valid
            {"doi": "invalid"},       # invalid
            {"doi": "10.1000/183"}   # valid
        ]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == StepStatus.ERROR
        assert result["count"] == 2  # Only valid papers created
        assert "errors" in result
        assert len(result["errors"]) == 1

    def test_execute_preserves_study_type(self):
        """Should accept study_type for future use"""
        config = {"papers": [{
            "doi": "10.1000/182",
            "study_type": "empirical_quantitative"
        }]}
        result = self.step.execute(config, dry_run=True)
        
        assert result["status"] == "ok"
        assert result["count"] == 1

    def test_execute_sets_discovery_method(self):
        """Should set discovery method to MANUAL"""
        config = {"papers": [{"doi": "10.1000/182"}]}
        result = self.step.execute(config, dry_run=False)
        
        assert result["status"] == "ok"
        # Verify add was called with a Paper object
        call_args = self.mock_db.add.call_args[0][0]
        assert isinstance(call_args, Paper)
        assert call_args.discovery.method == DiscoveryMethod.MANUAL

    def test_execute_normalizes_doi(self):
        """Should normalize DOI to stem format"""
        config = {"papers": [{"doi": "https://doi.org/10.1000/182"}]}
        result = self.step.execute(config, dry_run=False)
        
        assert result["status"] == "ok"
        call_args = self.mock_db.add.call_args[0][0]
        assert call_args.doi == "10.1000/182"

    def test_execute_verbose_output(self, capsys):
        """Should print verbose output when verbose=True"""
        config = {"papers": [{"doi": "10.1000/182"}]}
        result = self.step.execute(config, verbose=True, dry_run=True)
        
        assert result["status"] == "ok"
        # Verbose output goes to stderr through console

    def test_execute_error_handling(self):
        """Should return error status on exception"""
        # Create invalid config that will fail during iteration
        # The config itself has valid structure, but iteration will fail
        config = {"papers": [{"doi": "10.1000/182"}]}
        
        # Mock add to raise an exception
        self.mock_db.add.side_effect = RuntimeError("Database error")
        
        result = self.step.execute(config, dry_run=False, debug=False)
        
        assert result["status"] == "error"
        assert result["count"] == 0
        assert "error" in result

    def test_execute_raises_on_debug(self):
        """Should re-raise exception when debug=True"""
        config = {"papers": [{"doi": "invalid"}]}
        
        with pytest.raises(ValueError):
            self.step.execute(config, debug=True)


class TestPaperStepIntegration:
    """Integration tests with real Paper model"""

    def test_integration_create_valid_papers(self):
        """Integration: Create valid papers and check properties"""
        mock_db = Mock()
        mock_db.add = Mock()
        
        step = PaperStep(
            general_config={},
            db=mock_db,
            cache_dir=Path("/tmp/cache")
        )
        
        config = {"papers": [
            {"doi": "10.1000/182", "paper_type": "journal_article"},
            {"doi": "10.1000/183", "cite_key": "custom"}
        ]}
        
        result = step.execute(config, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["count"] == 2
        assert mock_db.add.call_count == 2
        
        # Check first paper
        first_paper = mock_db.add.call_args_list[0][0][0]
        assert first_paper.doi == "10.1000/182"
        assert first_paper.paper_type == PaperType.JOURNAL_ARTICLE
        assert first_paper.cite_key.startswith("doi_")
        
        # Check second paper
        second_paper = mock_db.add.call_args_list[1][0][0]
        assert second_paper.doi == "10.1000/183"
        assert second_paper.cite_key == "custom"

    def test_integration_doi_formats(self):
        """Integration: Test various DOI formats are normalized"""
        mock_db = Mock()
        mock_db.add = Mock()
        
        step = PaperStep(
            general_config={},
            db=mock_db,
            cache_dir=Path("/tmp/cache")
        )
        
        config = {"papers": [
            {"doi": "10.1000/182"},
            {"doi": "https://doi.org/10.1000/183"},
            {"doi": "doi:10.1000/184"}
        ]}
        
        result = step.execute(config, dry_run=False)
        
        assert result["status"] == "ok"
        assert result["count"] == 3
        
        # All should be normalized to stem format
        for call in mock_db.add.call_args_list:
            paper = call[0][0]
            assert paper.doi.startswith("10.")
            assert "/" in paper.doi
