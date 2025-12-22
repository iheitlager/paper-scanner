"""
Tests for CitationsStep.execute() method with backward configuration

Tests the execute() method's delegation to backward_execute() when
backward configuration is present.
"""

from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.citations import CitationsStep


class TestValidation:
    """Test CitationsStep.validate() static method for backward configuration"""

    def test_valid_config_keys(self):
        """Test valid config keys"""
        config = {
            "paper-type": ["journal_article", "conference_paper"],
            "limit": 100,
            "continue_on_not_found": True,
            "forward": {
                "citations": ["crossref"]
            },
            "backward": {
                "citations": ["crossref"]
            }
        }

        is_valid, errors = CitationsStep.validate(config)

        assert is_valid is True
        assert len(errors) == 0

    def test_invalid_config_keys(self):
        """Test validation with invalid config keys"""
        config = {
            "something_invalid": True,
        }

        is_valid, errors = CitationsStep.validate(config)

        assert is_valid is False
        assert any("Unknown configuration key: 'something_invalid'" in err for err in errors)
        assert len(errors) > 0

    def test_validate_invalid_paper_type(self):
        """Test validation fails with invalid paper_type"""
        config = {
            "paper-type": ["invalid_type"],
            "backward": {
                "citations": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("not a valid PaperType" in err for err in errors)

    def test_validate_paper_types_not_list(self):
        """Test validation fails when paper-types is not a list"""
        config = {
            "paper-type": "journal_article",
            "backward": {
                "sources": "crossref"
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'paper-types' must be a list" in err for err in errors)

    def test_validate_continue_on_not_found_not_bool(self):
        """Test validation fails when continue_on_not_found is not a boolean"""
        config = {
            "continue_on_not_found": "yes",
            "backward": {
                "citations": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'continue_on_not_found' must be a boolean" in err for err in errors)

    def test_validate_limit_not_positive_integer(self):
        """Test validation fails when limit is not a positive integer"""
        config = {
            "limit": -10,
            "backward": {
                "citations": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is False
        assert any("'limit' must be a positive integer" in err for err in errors)

    def test_validate_forward_and_backward_together(self):
        """Test validation succeeds with both forward and backward config.

            But we will only run backward.
        """
        config = {
            "forward": {
                "citations": ["crossref"]
            },
            "backward": {
                "citations": ["crossref"]
            }
        }
        
        is_valid, errors = CitationsStep.validate(config)
        
        assert is_valid is True
        assert len(errors) == 0

class TestExecuteIncompleteConfig:
    """Test CitationsStep.execute() with incomplete configuration"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance with mock database"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        return step

    def test_execute_raises_error_without_backward_or_forward(self, step):
        """Test execute raises ValueError when neither backward nor forward config provided"""
        config = {}

        with pytest.raises(ValueError, match="CitationsStep requires 'backward' or 'forward' configuration"):
            step.execute(config)

    def test_execute_raises_error_with_empty_backward_and_forward(self, step):
        """Test execute raises ValueError when both backward and forward are empty"""
        config = {
            "backward": {},
            "forward": {}
        }

        with pytest.raises(ValueError, match="CitationsStep requires 'backward' or 'forward' configuration"):
            step.execute(config)

    def test_execute_raises_error_with_only_paper_type(self, step):
        """Test execute raises ValueError when only paper-type is provided"""
        config = {
            "paper-type": ["journal_article"]
        }

        with pytest.raises(ValueError, match="CitationsStep requires 'backward' or 'forward' configuration"):
            step.execute(config)

    def test_execute_raises_error_with_only_continue_on_not_found(self, step):
        """Test execute raises ValueError when only continue_on_not_found is provided"""
        config = {
            "continue_on_not_found": True
        }

        with pytest.raises(ValueError, match="CitationsStep requires 'backward' or 'forward' configuration"):
            step.execute(config)


class TestExecuteWithBackwardConfig:
    """Test CitationsStep.execute() method with backward configuration"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance with mock database"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        return step

    @patch("paper_scanner.steps.citations.CitationsStep.backward_execute")
    def test_execute_calls_backward_execute_with_config(self, mock_backward, step):
        """Test that execute() calls backward_execute() when backward config present"""
        mock_backward.return_value = {
            "status": "ok",
            "errors": [],
            "total_papers": 5,
            "citations_fetched": 10
        }

        config = {
            "continue_on_not_found": True,
            "backward": {
                "citations": ["crossref"],
            }
        }

        result = step.execute(config, verbose=False, dry_run=False)

        mock_backward.assert_called_once_with(config)
        assert result["status"] == "ok"
        assert result["total_papers"] == 5
        assert result["citations_fetched"] == 10


    @patch("paper_scanner.steps.citations.CitationsStep.backward_execute")
    def test_execute_returns_backward_execute_result(self, mock_backward, step):
        """Test that execute() returns the result from backward_execute()"""
        expected_result = {
            "status": "completed_with_errors",
            "total_papers": 10,
            "target_papers": 8,
            "citations_fetched": 42,
            "papers_with_citations": 6,
            "citations_resolved": 35,
            "citations_created_new_paper": 7,
            "citations_unresolved": 0,
            "forward_links_created": 35,
            "reverse_links_created": 35,
            "errors": ["Error 1", "Error 2"]
        }

        mock_backward.return_value = expected_result

        config = {
            "backward": {
                "sources": ["crossref"]
            }
        }

        result = step.execute(config)

        assert result == expected_result
        assert result["status"] == "completed_with_errors"
        assert len(result["errors"]) == 2

class TestExecuteWithForwardConfig:
    """Test CitationsStep.execute() method with forward configuration"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        db = MagicMock(spec=PapersDatabase)
        return db

    @pytest.fixture
    def step(self, tmp_path, mock_db):
        """Create a CitationsStep instance with mock database"""
        step = CitationsStep(general_config={}, db=mock_db, cache_dir=tmp_path)
        return step

    @patch("paper_scanner.steps.citations.CitationsStep.forward_execute")
    def test_execute_calls_forward_execute_with_config(self, mock_forward, step):
        """Test that execute() calls forward_execute() when forward config present"""
        mock_forward.return_value = {
            "status": "ok",
            "errors": [],
            "total_papers": 5,
            "citations_fetched": 10
        }

        config = {
            "continue_on_not_found": True,
            "forward": {
                "citations": ["crossref"],
            }
        }

        result = step.execute(config, verbose=False, dry_run=False)

        mock_forward.assert_called_once_with(config)
        assert result["status"] == "ok"
        assert result["total_papers"] == 5
        assert result["citations_fetched"] == 10


    @patch("paper_scanner.steps.citations.CitationsStep.forward_execute")
    def test_execute_returns_forward_execute_result(self, mock_forward, step):
        """Test that execute() returns the result from forward_execute()"""
        expected_result = {
            "status": "completed_with_errors",
            "total_papers": 10,
            "target_papers": 8,
            "citations_fetched": 42,
            "papers_with_citations": 6,
            "citations_resolved": 35,
            "citations_created_new_paper": 7,
            "citations_unresolved": 0,
            "forward_links_created": 35,
            "reverse_links_created": 35,
            "errors": ["Error 1", "Error 2"]
        }

        mock_forward.return_value = expected_result

        config = {
            "forward": {
                "sources": ["crossref"]
            }
        }

        result = step.execute(config)

        assert result == expected_result
        assert result["status"] == "completed_with_errors"
        assert len(result["errors"]) == 2



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
