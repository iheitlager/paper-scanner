"""
Unit tests for GenerateEmbeddingsStep.

Tests cover:
- Configuration validation
- Embedding generation
- Field selection
- Filtering options
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus, ScreeningDecision
from paper_scanner.core.models import Paper
from paper_scanner.steps.generate_embeddings import GenerateEmbeddingsStep


class TestGenerateEmbeddingsValidation:
    """Test configuration validation."""

    def test_validate_empty_config(self):
        """Empty config should be valid (uses defaults)."""
        is_valid, errors = GenerateEmbeddingsStep.validate({})
        assert is_valid
        assert len(errors) == 0

    def test_validate_valid_model(self):
        """Valid model name should pass."""
        config = {"model": "all-mpnet-base-v2"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_model_type(self):
        """Non-string model should fail."""
        config = {"model": 123}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid
        assert any("model" in e.lower() for e in errors)

    def test_validate_valid_device(self):
        """Valid device values should pass."""
        for device in ("cpu", "cuda"):
            config = {"device": device}
            is_valid, errors = GenerateEmbeddingsStep.validate(config)
            assert is_valid, f"Device '{device}' should be valid"

    def test_validate_invalid_device(self):
        """Invalid device should fail."""
        config = {"device": "gpu"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid
        assert any("device" in e.lower() for e in errors)

    def test_validate_batch_size(self):
        """Batch size must be positive integer."""
        # Valid
        config = {"batch_size": 32}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid - not integer
        config = {"batch_size": "32"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - not positive
        config = {"batch_size": 0}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

    def test_validate_fields(self):
        """Fields must be valid list."""
        # Valid
        config = {"fields": ["title", "abstract"]}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid - not list
        config = {"fields": "title"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - unknown field
        config = {"fields": ["title", "invalid_field"]}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid
        assert any("invalid_field" in e.lower() for e in errors)

    def test_validate_skip_existing(self):
        """skip_existing must be boolean."""
        # Valid
        config = {"skip_existing": True}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid
        config = {"skip_existing": "true"}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

    def test_validate_filter(self):
        """Filter must be dictionary with valid options."""
        # Valid
        config = {"filter": {"included_only": True, "min_year": 2020}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert is_valid

        # Invalid - not dict
        config = {"filter": ["included_only"]}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - wrong type for included_only
        config = {"filter": {"included_only": "true"}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid

        # Invalid - wrong type for min_year
        config = {"filter": {"min_year": "2020"}}
        is_valid, errors = GenerateEmbeddingsStep.validate(config)
        assert not is_valid


class TestGenerateEmbeddingsExecution:
    """Test step execution."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()  # Remove spec to allow any attribute
        return db

    @pytest.fixture
    def mock_general_config(self):
        """Create mock general config."""
        return {"project_name": "test"}

    @pytest.fixture
    def sample_paper(self):
        """Create sample paper for testing."""
        paper = Paper(
            cite_key="test2024",
            title="Test Paper on Machine Learning",
            abstract="This is a test abstract about machine learning and AI.",
            keywords=["machine learning", "AI", "deep learning"],
            year=2024,
        )
        paper.screening.final_decision = ScreeningDecision.INCLUDED
        return paper

    @pytest.fixture
    def step(self, mock_db, mock_general_config, tmp_path):
        """Create step instance."""
        return GenerateEmbeddingsStep(
            general_config=mock_general_config,
            db=mock_db,
            cache_dir=tmp_path,
        )

    def test_execute_no_papers(self, step, mock_db):
        """Should handle case with no papers."""
        mock_db.list_papers.return_value = []

        result = step.execute(step_config={})

        assert result.status == StepStatus.SUCCESS
        assert result.stats["papers_count"] == 0
        assert result.stats["papers_processed"] == 0

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_with_title_embedding(self, mock_model_class, step, mock_db, sample_paper):
        """Should generate title embedding."""
        # Setup
        mock_db.list_papers.return_value = [sample_paper]
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Mock encode to return proper vector
        import numpy as np
        vector = np.random.randn(768).tolist()
        mock_model.encode.return_value = vector

        # Execute
        result = step.execute(
            step_config={"fields": ["title"]},
            verbose=False,
        )

        # Verify
        assert result.status == StepStatus.SUCCESS
        assert result.stats["embeddings_generated"] >= 1
        assert sample_paper.title_abstract_embedding is not None

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_skip_existing(self, mock_model_class, step, mock_db, sample_paper):
        """Should skip papers with existing embeddings."""
        from paper_scanner.core.models import Embedding

        # Setup
        sample_paper.title_abstract_embedding = Embedding(
            vector=[0.0] * 768,
            model="test-model",
            text_source="title",
        )
        mock_db.list_papers.return_value = [sample_paper]

        # Execute
        result = step.execute(
            step_config={"skip_existing": True},
        )

        # Verify - should skip, not encode
        mock_model_class.return_value.encode.assert_not_called()
        assert result.stats["embeddings_skipped"] >= 1

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_with_filter_included_only(self, mock_model_class, step, mock_db, sample_paper):
        """Should filter by included_only."""
        # Create excluded paper
        excluded_paper = Paper(
            cite_key="excluded2024",
            title="Excluded Paper",
            abstract="This paper was excluded.",
            year=2024,
        )
        excluded_paper.screening.final_decision = ScreeningDecision.EXCLUDED

        mock_db.list_papers.return_value = [sample_paper, excluded_paper]

        # Execute
        result = step.execute(
            step_config={
                "filter": {"included_only": True},
                "fields": ["title"],
            },
        )

        # Verify - only included paper processed
        assert result.stats["papers_processed"] == 1

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_with_filter_min_year(self, mock_model_class, step, mock_db, sample_paper):
        """Should filter by minimum year."""
        # Create old paper
        old_paper = Paper(
            cite_key="old2015",
            title="Old Paper",
            abstract="This is old.",
            year=2015,
        )
        old_paper.screening.final_decision = ScreeningDecision.INCLUDED

        mock_db.list_papers.return_value = [sample_paper, old_paper]

        # Execute
        result = step.execute(
            step_config={
                "filter": {"min_year": 2020},
                "fields": ["title"],
            },
        )

        # Verify - only recent paper processed
        assert result.stats["papers_processed"] == 1

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_model_load_error(self, mock_model_class, step, mock_db, sample_paper):
        """Should handle model loading errors."""
        mock_db.list_papers.return_value = [sample_paper]
        mock_model_class.side_effect = RuntimeError("Model not found")

        result = step.execute(step_config={})

        assert result.status == StepStatus.ERROR
        assert "Model not found" in result.error

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_empty_text(self, mock_model_class, step, mock_db):
        """Should handle papers with empty text fields."""
        # Create paper with no title
        paper = Paper(
            cite_key="notext2024",
            title="",  # Empty title
            abstract="",  # Empty abstract
            keywords=[],  # Empty keywords
            year=2024,
        )
        paper.screening.final_decision = ScreeningDecision.INCLUDED

        mock_db.list_papers.return_value = [paper]
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        result = step.execute(step_config={"fields": ["title", "abstract", "keywords"]})

        # Should succeed but generate no embeddings
        assert result.status == StepStatus.SUCCESS
        assert result.stats["embeddings_generated"] == 0

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_execute_dry_run(self, mock_model_class, step, mock_db, sample_paper):
        """Should not modify database in dry_run mode."""
        import numpy as np

        mock_db.list_papers.return_value = [sample_paper]
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        vector = np.random.randn(768).tolist()
        mock_model.encode.return_value = vector

        # Execute in dry_run mode
        result = step.execute(
            step_config={"fields": ["title"]},
            dry_run=True,
        )

        # Verify - update_paper should not be called
        mock_db.update_paper.assert_not_called()
        assert result.status == StepStatus.SUCCESS


class TestFilterLogic:
    """Test filtering logic."""

    @pytest.fixture
    def step(self):
        """Create step instance."""
        mock_db = MagicMock()
        return GenerateEmbeddingsStep(
            general_config={},
            db=mock_db,
            cache_dir=Path("/tmp"),
        )

    def test_apply_filters_no_filter(self, step):
        """No filter should return all papers."""
        papers = [
            Paper(cite_key="p1", title="Paper 1", year=2020),
            Paper(cite_key="p2", title="Paper 2", year=2021),
        ]
        result = step._apply_filters(papers, {})
        assert len(result) == 2

    def test_apply_filters_included_only(self, step):
        """Should filter by inclusion status."""
        p1 = Paper(cite_key="p1", title="Paper 1", year=2020)
        p1.screening.final_decision = ScreeningDecision.INCLUDED

        p2 = Paper(cite_key="p2", title="Paper 2", year=2021)
        p2.screening.final_decision = ScreeningDecision.EXCLUDED

        papers = [p1, p2]
        result = step._apply_filters(papers, {"included_only": True})

        assert len(result) == 1
        assert result[0].cite_key == "p1"

    def test_apply_filters_min_year(self, step):
        """Should filter by year."""
        papers = [
            Paper(cite_key="p1", title="Paper 1", year=2015),
            Paper(cite_key="p2", title="Paper 2", year=2020),
            Paper(cite_key="p3", title="Paper 3", year=2025),
        ]
        result = step._apply_filters(papers, {"min_year": 2020})

        assert len(result) == 2
        assert result[0].year >= 2020
        assert result[1].year >= 2020

    def test_apply_filters_combined(self, step):
        """Should apply multiple filters."""
        p1 = Paper(cite_key="p1", title="Paper 1", year=2015)
        p1.screening.final_decision = ScreeningDecision.INCLUDED

        p2 = Paper(cite_key="p2", title="Paper 2", year=2020)
        p2.screening.final_decision = ScreeningDecision.INCLUDED

        p3 = Paper(cite_key="p3", title="Paper 3", year=2025)
        p3.screening.final_decision = ScreeningDecision.EXCLUDED

        papers = [p1, p2, p3]
        result = step._apply_filters(
            papers, {"included_only": True, "min_year": 2020}
        )

        assert len(result) == 1
        assert result[0].cite_key == "p2"


class TestEmbeddingGeneration:
    """Test embedding generation logic."""

    @pytest.fixture
    def step(self):
        """Create step instance."""
        mock_db = MagicMock()
        return GenerateEmbeddingsStep(
            general_config={},
            db=mock_db,
            cache_dir=Path("/tmp"),
        )

    def test_has_embeddings_with_embedding(self, step):
        """Should detect existing embedding."""
        from paper_scanner.core.models import Embedding

        paper = Paper(cite_key="p1", title="Paper 1")
        paper.title_abstract_embedding = Embedding(
            vector=[0.0] * 768,
            model="test",
            text_source="title",
        )

        assert step._has_embeddings(paper)

    def test_has_embeddings_without_embedding(self, step):
        """Should return False for paper without embedding."""
        paper = Paper(cite_key="p1", title="Paper 1")
        assert not step._has_embeddings(paper)

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_generate_embedding_success(self, mock_model_class, step):
        """Should generate valid embedding."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(768).tolist()

        embedding = step._generate_embedding("Test text", mock_model, 32, "title", "test-model")

        assert embedding is not None
        assert len(embedding.vector) == 768
        assert embedding.text_source == "title"

    @patch("paper_scanner.steps.generate_embeddings.SentenceTransformer")
    def test_generate_embedding_empty_text(self, mock_model_class, step):
        """Should handle empty text."""
        mock_model = MagicMock()

        embedding = step._generate_embedding("", mock_model, 32, "title", "test-model")
        embedding = step._generate_embedding(None, mock_model, 32, "title", "test-model")

        assert embedding is None
        mock_model.encode.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
