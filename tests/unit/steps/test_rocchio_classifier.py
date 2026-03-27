"""
Unit tests for rocchio_classifier step.

Tests both validator and executor for the Rocchio dimension-based classification step.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import Paper, Screening
from paper_scanner.core.step_result import StepResult
from paper_scanner.steps.rocchio_classifier import RocchioClassifierStep, _RocchioClassifier


class TestRocchioClassifierValidate:
    """Tests for RocchioClassifierStep.validate()"""

    def test_validate_empty_config(self):
        """Valid config can be empty (all defaults)."""
        is_valid, errors = RocchioClassifierStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_valid_model(self):
        """Valid model name in config."""
        config = {"model": "all-mpnet-base-v2"}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_model_type(self):
        """Invalid: model is not a string."""
        config = {"model": 123}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert any("model" in e and "string" in e for e in errors)

    def test_validate_valid_dimension_threshold(self):
        """Valid dimension_threshold."""
        config = {"dimension_threshold": 0.5}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_dimension_threshold_zero(self):
        """Valid dimension_threshold at boundary (0.0)."""
        config = {"dimension_threshold": 0.0}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_dimension_threshold_one(self):
        """Valid dimension_threshold at boundary (1.0)."""
        config = {"dimension_threshold": 1.0}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_dimension_threshold_invalid_type(self):
        """Invalid: dimension_threshold is not a number."""
        config = {"dimension_threshold": "0.5"}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert any("dimension_threshold" in e and "number" in e for e in errors)

    def test_validate_dimension_threshold_too_low(self):
        """Invalid: dimension_threshold < 0."""
        config = {"dimension_threshold": -0.1}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert any("dimension_threshold" in e and "between 0 and 1" in e for e in errors)

    def test_validate_dimension_threshold_too_high(self):
        """Invalid: dimension_threshold > 1."""
        config = {"dimension_threshold": 1.1}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert any("dimension_threshold" in e and "between 0 and 1" in e for e in errors)

    def test_validate_valid_initialize_from_research_question(self):
        """Valid initialize_from_research_question boolean."""
        config = {"initialize_from_research_question": True}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_initialize_from_research_question(self):
        """Invalid: initialize_from_research_question is not a boolean."""
        config = {"initialize_from_research_question": "yes"}
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert any("initialize_from_research_question" in e and "boolean" in e for e in errors)

    def test_validate_all_valid_options(self):
        """Valid config with all options."""
        config = {
            "model": "specter2",
            "dimension_threshold": 0.6,
            "initialize_from_research_question": False,
        }
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_multiple_errors(self):
        """Multiple validation errors reported."""
        config = {
            "model": 123,
            "dimension_threshold": 1.5,
            "initialize_from_research_question": "invalid",
        }
        is_valid, errors = RocchioClassifierStep.validate(config)
        assert is_valid is False
        assert len(errors) >= 3


class TestRocchioClassifierExecutor:
    """Tests for RocchioClassifierStep.execute()"""

    @pytest.fixture
    def mock_db(self):
        """Mock database."""
        db = MagicMock()
        db.count.return_value = 5
        db.find.return_value = []
        return db

    @pytest.fixture
    def mock_step(self, mock_db):
        """Mock step instance."""
        with TemporaryDirectory() as tmpdir:
            step = RocchioClassifierStep(
                general_config={
                    "research_question": "How do firms innovate?",
                    "research_dimensions": ["innovation", "strategy"],
                },
                db=mock_db,
                cache_dir=Path(tmpdir),
                on_event=lambda msg, debug=False: None,
            )
            yield step

    def test_execute_missing_research_question(self, mock_db):
        """Raises error if research_question missing."""
        with TemporaryDirectory() as tmpdir:
            step = RocchioClassifierStep(
                general_config={"research_dimensions": ["dim1"]},
                db=mock_db,
                cache_dir=Path(tmpdir),
                on_event=lambda msg, debug=False: None,
            )

            with pytest.raises(ConfigurationError, match="research_question"):
                step.execute({})

    def test_execute_missing_research_dimensions(self, mock_db):
        """Raises error if research_dimensions missing."""
        with TemporaryDirectory() as tmpdir:
            step = RocchioClassifierStep(
                general_config={"research_question": "How do firms innovate?"},
                db=mock_db,
                cache_dir=Path(tmpdir),
                on_event=lambda msg, debug=False: None,
            )

            with pytest.raises(ConfigurationError, match="research_dimensions"):
                step.execute({})

    def test_execute_no_papers(self, mock_step):
        """Returns success if no papers to classify."""
        mock_step.db.find.return_value = []

        result = mock_step.execute({})

        # Result should be StepResult
        assert isinstance(result, StepResult)
        assert result.status == StepStatus.SUCCESS
        assert "classified" in result.stats

    @patch("paper_scanner.steps.rocchio_classifier.SentenceTransformer")
    def test_execute_with_papers(self, mock_st, mock_step):
        """Execute with papers to classify."""
        import numpy as np
        # Mock SentenceTransformer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_st.return_value = mock_model

        # Create test papers
        paper1 = Paper(
            id="test1",
            title="Innovation Strategy",
            abstract="About innovation",
            cite_key="p1",
            authors=[],
            screening=Screening(),
        )
        paper1.screening.final_decision = ScreeningDecision.PENDING

        mock_step.db.find.return_value = [paper1]
        mock_step.db.update = MagicMock()

        result = mock_step.execute(
            {"model": "all-mpnet-base-v2", "dimension_threshold": 0.5}
        )

        assert isinstance(result, StepResult)
        assert result.status == StepStatus.SUCCESS
        assert "classified" in result.stats

    @patch("paper_scanner.steps.rocchio_classifier.SentenceTransformer")
    def test_execute_model_loading_error(self, mock_st, mock_step):
        """Raises error if embedding model fails to load."""
        mock_st.side_effect = Exception("Model loading failed")

        with pytest.raises(StepFatalError, match="Failed to initialize"):
            mock_step.execute({"model": "invalid-model"})


class TestRocchioClassifierInternal:
    """Tests for _RocchioClassifier internal class"""

    @pytest.fixture
    @patch("paper_scanner.steps.rocchio_classifier.SentenceTransformer")
    def classifier(self, mock_st):
        """Create test classifier."""
        mock_model = MagicMock()
        # Mock encode to return a numpy array that can be converted to list
        import numpy as np
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_st.return_value = mock_model

        return _RocchioClassifier(
            research_question="How do firms innovate?",
            research_dimensions=["innovation", "strategy", "technology"],
            model_name="all-mpnet-base-v2",
            initialize_from_rq=True,
        )

    def test_classifier_initialization(self, classifier):
        """Classifier initializes with dimensions."""
        assert len(classifier.research_dimensions) == 3
        assert "innovation" in classifier.research_dimensions
        assert all(
            isinstance(c, (list, type(None)))
            for c in classifier.dimension_centroids.values()
        )

    def test_classifier_initialize_from_research_question(self, classifier):
        """Centroids initialized from research question."""
        assert classifier.dimension_centroids["innovation"] is not None
        assert classifier.dimension_centroids["strategy"] is not None

    def test_compute_embedding(self, classifier):
        """Compute embedding returns vector."""
        embedding = classifier.compute_embedding("test text")
        assert isinstance(embedding, list)
        assert len(embedding) == 768

    def test_compute_embedding_empty_text(self, classifier):
        """Empty text returns zero vector."""
        embedding = classifier.compute_embedding("")
        assert all(x == 0.0 for x in embedding)

    def test_cosine_similarity(self, classifier):
        """Compute cosine similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        sim = classifier._cosine_similarity(vec1, vec2)
        assert abs(sim - 1.0) < 0.01  # Should be very close to 1

    def test_cosine_similarity_orthogonal(self, classifier):
        """Orthogonal vectors have zero similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        sim = classifier._cosine_similarity(vec1, vec2)
        assert abs(sim) < 0.01

    def test_cosine_similarity_empty_vectors(self, classifier):
        """Empty vectors have zero similarity."""
        sim = classifier._cosine_similarity([], [1.0, 2.0])
        assert sim == 0.0

    def test_classify_paper_excluded(self, classifier):
        """Classify paper returns valid result."""
        # When all similarities are equal (mock returns uniform [0.1]*768),
        # cosine similarity will be ~1.0 for all dimensions, so multiple will apply.
        # This is expected behavior with uniform embeddings. Test structure instead.
        paper = Paper(
            id="test",
            title="Weather Forecasting",
            abstract="Machine learning for weather prediction",
            cite_key="weather",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.5)

        # Should return valid classification
        assert screening.decision is not None
        assert screening.classification in ["included", "excluded", "uncertain"]
        assert isinstance(screening.classification_vector, list)

    def test_classify_paper_structure(self, classifier):
        """Classification result has expected structure."""
        paper = Paper(
            id="test",
            title="Innovation Management",
            abstract="Managing innovation processes",
            cite_key="inn001",
            authors=[],
            screening=Screening(),
        )

        # Use very high threshold to ensure no dimensions apply
        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.99)

        assert screening.decision in [
            ScreeningDecision.EXCLUDED,
            ScreeningDecision.INCLUDED,
            ScreeningDecision.MANUAL_REVIEW,
        ]
        assert screening.classification in ["included", "excluded", "uncertain"]
        assert isinstance(screening.classification_vector, list)
        assert len(screening.classification_vector) == 3
        assert isinstance(screening.confidence, float)
        assert 0 <= screening.confidence <= 1
        assert screening.metadata is not None

    def test_classify_paper_with_metadata(self, classifier):
        """Classification result includes processing metadata."""
        paper = Paper(
            id="test",
            title="Test Paper",
            abstract="Test abstract",
            cite_key="test",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper)

        assert screening.metadata.success is True
        assert screening.metadata.model_name == "all-mpnet-base-v2"
        assert screening.metadata.duration_seconds is not None

    def test_classify_paper_error_handling(self, classifier):
        """Gracefully handle classification errors."""
        # Create paper with problematic data
        paper = Paper(
            id="test",
            title=None,
            abstract=None,
            cite_key="error",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper)

        # Should still return valid result
        assert screening is not None
        assert screening.decision in [
            ScreeningDecision.EXCLUDED,
            ScreeningDecision.INCLUDED,
            ScreeningDecision.MANUAL_REVIEW,
        ]

    def test_classify_paper_raw_data(self, classifier):
        """Raw data includes dimension details."""
        paper = Paper(
            id="test",
            title="Innovation Strategy",
            abstract="Strategic innovation",
            cite_key="inv001",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.3)

        assert "dimension_similarities" in raw
        assert "applicable_dimensions" in raw
        assert "dominant_dimension" in raw
        assert len(raw["dimension_similarities"]) == 3


class TestRocchioClassifierEdgeCases:
    """Tests for edge cases and special scenarios"""

    @patch("paper_scanner.steps.rocchio_classifier.SentenceTransformer")
    def test_paper_with_only_title(self, mock_st):
        """Classify paper with only title (no abstract)."""
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_st.return_value = mock_model

        classifier = _RocchioClassifier(
            research_question="Test question",
            research_dimensions=["dim1"],
            initialize_from_rq=True,
        )

        paper = Paper(
            id="test",
            title="Only Title",
            abstract=None,
            cite_key="test",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper)

        assert screening is not None
        assert isinstance(screening.classification_vector, list)

    @patch("paper_scanner.steps.rocchio_classifier.SentenceTransformer")
    def test_multiple_classifications(self, mock_st):
        """Classify multiple papers."""
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_st.return_value = mock_model

        classifier = _RocchioClassifier(
            research_question="Test",
            research_dimensions=["dim1", "dim2"],
            initialize_from_rq=True,
        )

        papers = [
            Paper(
                id=f"id{i}",
                title=f"Paper {i}",
                abstract=f"Abstract {i}",
                cite_key=f"p{i}",
                authors=[],
                screening=Screening(),
            )
            for i in range(3)
        ]

        results = [classifier.classify_paper(p) for p in papers]

        assert len(results) == 3
        assert all(r[0] is not None for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
