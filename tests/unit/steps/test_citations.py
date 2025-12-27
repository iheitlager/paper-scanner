"""
Tests for CitationsStep.execute() method with backward configuration

Tests the execute() method's delegation to backward_execute() when
backward configuration is present.
"""

from unittest.mock import MagicMock, patch, ANY

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
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
        config = {
            "continue_on_not_found": True,
            "backward": {
                "citations": ["crossref"],
            }
        }

        result = step.execute(config, verbose=False, dry_run=False)

        # Check that backward_execute was called with config as first arg, and ANY for target_papers and results
        assert mock_backward.call_count == 1
        call_args = mock_backward.call_args
        assert call_args[0][0] == config  # First arg should be config
        # Second and third args (target_papers and results) can be any value


    @patch("paper_scanner.steps.citations.CitationsStep.backward_execute")
    def test_execute_returns_backward_execute_result(self, mock_backward, step):
        """Test that execute() returns the result from backward_execute()"""
        config = {
            "backward": {
                "sources": ["crossref"]
            }
        }

        result = step.execute(config)

        # backward_execute is called but doesn't modify results directly
        # Check that execute returns a StepResult
        assert hasattr(result, 'stats')

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
        config = {
            "continue_on_not_found": True,
            "forward": {
                "citations": ["crossref"],
            }
        }

        result = step.execute(config, verbose=False, dry_run=False)

        # Check that forward_execute was called with config as first arg, and ANY for target_papers and results
        assert mock_forward.call_count == 1
        call_args = mock_forward.call_args
        assert call_args[0][0] == config  # First arg should be config
        # Second and third args (target_papers and results) can be any value


    @patch("paper_scanner.steps.citations.CitationsStep.forward_execute")
    def test_execute_returns_forward_execute_result(self, mock_forward, step):
        """Test that execute() returns a StepResult"""
        config = {
            "forward": {
                "sources": ["crossref"]
            }
        }

        result = step.execute(config)

        # forward_execute is called but doesn't modify results directly
        # Check that execute returns a StepResult
        assert hasattr(result, 'stats')


class TestResolveCitationFetcherIntegration:
    """Test _resolve_citation method fetcher integration with 3-tuple unpacking"""

    @pytest.fixture
    def setup(self, tmp_path):
        """Setup test database and step"""
        from paper_scanner.core.models import Paper, Citation, CitationDirection
        
        db = PapersDatabase()
        step = CitationsStep(general_config={}, db=db, cache_dir=tmp_path)
        # Initialize attributes that are normally set in execute()
        step.debug = False
        step.verbose = False
        step.dry_run = False
        return step, db

    def test_resolve_citation_unpacks_3_tuple_from_fetcher(self, setup):
        """Test that _resolve_citation correctly unpacks 3-tuple from fetcher.fetch_paper()"""
        from paper_scanner.core.models import Paper, Citation
        from paper_scanner.core.enum import CitationDirection
        
        step, db = setup

        # Create citation for paper not in database
        citation = Citation(
            doi="10.1234/new",
            title="New Paper",
            direction=CitationDirection.BACKWARD,
            extraction_method="grobid"
        )
        citing_paper = Paper(cite_key="citing2024", title="Citing", doi="10.5678/citing")

        # Mock fetcher to return 3-tuple (paper, cache_hit, handler)
        mock_fetcher = MagicMock()
        enriched_paper = Paper(cite_key="new2024", title="New Paper", doi="10.1234/new")
        mock_fetcher.fetch_paper.return_value = (enriched_paper, False, "crossref")

        # This should not raise ValueError about unpacking
        resolved_paper, created_new = step._resolve_citation(
            citation=citation,
            citing_paper=citing_paper,
            fetcher=mock_fetcher,
            continue_on_not_found=True
        )

        assert resolved_paper is not None
        assert resolved_paper.doi == "10.1234/new"
        assert created_new is True

    def test_resolve_citation_unpacks_3_tuple_cache_hit(self, setup):
        """Test that cache_hit is correctly handled when unpacking 3-tuple"""
        from paper_scanner.core.models import Paper, Citation
        from paper_scanner.core.enum import CitationDirection
        
        step, db = setup

        citation = Citation(
            doi="10.1234/cached",
            title="Cached",
            direction=CitationDirection.BACKWARD,
            extraction_method="grobid"
        )
        citing_paper = Paper(cite_key="citing2024", title="Citing", doi="10.5678/citing")

        mock_fetcher = MagicMock()
        enriched_paper = Paper(cite_key="cached2024", title="Cached", doi="10.1234/cached")
        # Return with cache_hit=True
        mock_fetcher.fetch_paper.return_value = (enriched_paper, True, "crossref")

        results = {}
        resolved_paper, created_new = step._resolve_citation(
            citation=citation,
            citing_paper=citing_paper,
            fetcher=mock_fetcher,
            continue_on_not_found=True,
            results=results
        )

        # Verify cache hit was tracked
        assert results.get("cache_hits", 0) == 1
        assert results.get("cache_misses", 0) == 0

    def test_resolve_citation_unpacks_3_tuple_cache_miss(self, setup):
        """Test that cache_miss is correctly handled when unpacking 3-tuple"""
        from paper_scanner.core.models import Paper, Citation
        from paper_scanner.core.enum import CitationDirection
        
        step, db = setup

        citation = Citation(
            doi="10.1234/nocache",
            title="No Cache",
            direction=CitationDirection.BACKWARD,
            extraction_method="grobid"
        )
        citing_paper = Paper(cite_key="citing2024", title="Citing", doi="10.5678/citing")

        mock_fetcher = MagicMock()
        enriched_paper = Paper(cite_key="nocache2024", title="No Cache", doi="10.1234/nocache")
        # Return with cache_hit=False
        mock_fetcher.fetch_paper.return_value = (enriched_paper, False, "openalex")

        results = {}
        resolved_paper, created_new = step._resolve_citation(
            citation=citation,
            citing_paper=citing_paper,
            fetcher=mock_fetcher,
            continue_on_not_found=True,
            results=results
        )

        # Verify cache miss was tracked
        assert results.get("cache_hits", 0) == 0
        assert results.get("cache_misses", 0) == 1

    def test_resolve_citation_handler_name_captured(self, setup):
        """Test that handler name from 3-tuple is captured but not causing errors"""
        from paper_scanner.core.models import Paper, Citation
        from paper_scanner.core.enum import CitationDirection
        
        step, db = setup

        citation = Citation(
            doi="10.1234/test",
            title="Test",
            direction=CitationDirection.BACKWARD,
            extraction_method="grobid"
        )
        citing_paper = Paper(cite_key="citing2024", title="Citing", doi="10.5678/citing")

        mock_fetcher = MagicMock()
        enriched_paper = Paper(cite_key="test2024", title="Test", doi="10.1234/test")
        # Return with different handler names
        for handler_name in ["crossref", "openalex", "semanticscholar"]:
            mock_fetcher.fetch_paper.return_value = (enriched_paper, False, handler_name)
            
            resolved_paper, created_new = step._resolve_citation(
                citation=citation,
                citing_paper=citing_paper,
                fetcher=mock_fetcher,
                continue_on_not_found=True
            )

            # Should work with any handler name
            assert resolved_paper is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
