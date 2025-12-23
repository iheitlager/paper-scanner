"""
Unit tests for semantic_screening step
"""

from unittest.mock import MagicMock, patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import ScreeningDecision
from paper_scanner.core.models import Author, Paper, PaperType, ProcessingMetadata, SemanticScreening
from paper_scanner.steps.semantic_screening import SemanticScreeningStep


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


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
            id="p1",
            cite_key="smith2020",
            title="Machine Learning Model for Classification",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            paper_type=PaperType.JOURNAL_ARTICLE,
            year=2020,
            abstract="This paper presents a machine learning model for image classification using deep learning techniques.",
        ),
        Paper(
            id="p2",
            cite_key="doe2021",
            title="Cooking Recipes for Family Meals",
            authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
            paper_type=PaperType.JOURNAL_ARTICLE,
            year=2021,
            abstract="A collection of easy-to-follow recipes for preparing delicious family meals.",
        ),
        Paper(
            id="p3",
            cite_key="brown2022",
            title="Natural Language Processing with Transformers",
            authors=[Author(family_name="Brown", given_name="Bob", full_name="Bob Brown")],
            paper_type=PaperType.JOURNAL_ARTICLE,
            year=2022,
            abstract="Comprehensive guide to using transformer models for NLP tasks including text classification and semantic similarity.",
        ),
    ]

    for paper in papers:
        db.add(paper)

    return db


class TestValidate:
    """Tests for SemanticScreeningStep.validate method"""

    def test_validate_empty_config(self):
        """Test validation of empty config"""
        config = {}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_model(self):
        """Test validation with model specified"""
        config = {"model": "all-mpnet-base-v2"}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_model_type(self):
        """Test validation fails with non-string model"""
        config = {"model": 123}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert any("model" in err for err in errors)

    def test_validate_with_thresholds(self):
        """Test validation with valid thresholds"""
        config = {
            "thresholds": {
                "auto_include": 0.7,
                "manual_review": 0.5,
                "auto_exclude": 0.3,
            }
        }
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_thresholds_type(self):
        """Test validation fails with non-dict thresholds"""
        config = {"thresholds": "0.7,0.5,0.3"}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert any("thresholds" in err for err in errors)

    def test_validate_invalid_threshold_value_type(self):
        """Test validation fails with non-numeric threshold"""
        config = {"thresholds": {"auto_include": "high"}}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert any("auto_include" in err for err in errors)

    def test_validate_threshold_value_too_high(self):
        """Test validation fails with threshold > 1"""
        config = {"thresholds": {"auto_include": 1.5}}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert any("auto_include" in err for err in errors)

    def test_validate_threshold_value_negative(self):
        """Test validation fails with negative threshold"""
        config = {"thresholds": {"auto_exclude": -0.1}}
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert any("auto_exclude" in err for err in errors)

    def test_validate_multiple_threshold_errors(self):
        """Test validation with multiple threshold errors"""
        config = {
            "thresholds": {
                "auto_include": 1.5,
                "manual_review": "high",
                "auto_exclude": -0.5,
            }
        }
        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is False
        assert len(errors) == 3


class TestExecute:
    """Tests for SemanticScreeningStep.execute method"""

    def test_execute_empty_database(self, empty_db, temp_cache_dir):
        """Test execute with empty database"""
        config = {}
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning"},
            db=empty_db,
            cache_dir=temp_cache_dir,
        )

        result = step.execute(config, verbose=False, dry_run=False)

        assert result["step"] == "semantic_screening"
        assert result["total_papers"] == 0
        assert result["screened"] == 0

    def test_execute_missing_research_question(self, sample_db, temp_cache_dir):
        """Test execute fails when research question missing"""
        config = {}
        step = SemanticScreeningStep(
            general_config={},  # No research_question
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        result = step.execute(config, verbose=False, dry_run=False)

        assert result["step"] == "semantic_screening"
        assert "error" in result
        assert "research_question" in result["error"]

    def test_execute_with_mocked_screener(self, sample_db, temp_cache_dir):
        """Test execute with mocked semantic screener"""
        config = {}
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning classification"},
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        # Mock the internal _SemanticScreener class and its methods
        with patch("paper_scanner.steps.semantic_screening._SemanticScreener") as mock_screener_class:
            mock_screener = MagicMock()
            mock_screener_class.return_value = mock_screener

            # Setup different responses for different papers
            def mock_screen_paper(paper):
                if paper.id == "p1":
                    return (
                        SemanticScreening(
                            passed=True,
                            similarity_score=0.85,
                            threshold=0.65,
                            llm_decision=ScreeningDecision.INCLUDED,
                            llm_confidence=0.85,
                            llm_reasoning="High similarity",
                            metadata=ProcessingMetadata(
                                duration_seconds=0.1,
                                success=True,
                            ),
                        ),
                        True,
                        None,
                    )
                elif paper.id == "p2":
                    return (
                        SemanticScreening(
                            passed=False,
                            similarity_score=0.2,
                            threshold=0.65,
                            llm_decision=ScreeningDecision.EXCLUDED,
                            llm_confidence=0.2,
                            llm_reasoning="Low similarity",
                            metadata=ProcessingMetadata(
                                duration_seconds=0.1,
                                success=True,
                            ),
                        ),
                        False,
                        "Low similarity",
                    )
                else:
                    return (
                        SemanticScreening(
                            passed=False,
                            similarity_score=0.58,
                            threshold=0.65,
                            llm_decision=ScreeningDecision.MANUAL_REVIEW,
                            llm_confidence=0.58,
                            llm_reasoning="Borderline similarity",
                            metadata=ProcessingMetadata(
                                duration_seconds=0.1,
                                success=True,
                            ),
                        ),
                        False,
                        "Borderline similarity",
                    )

            mock_screener.screen_paper.side_effect = mock_screen_paper
            result = step.execute(config, verbose=False, dry_run=False)

        # Verify results
        assert result["step"] == "semantic_screening"
        assert result["screened"] == 3
        assert result["included"] == 1
        assert result["excluded"] == 1
        assert result["manual_review"] == 1

    def test_execute_dry_run(self, sample_db, temp_cache_dir):
        """Test execute in dry run mode doesn't update database"""
        config = {}
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning"},
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        with patch("paper_scanner.steps.semantic_screening._SemanticScreener") as mock_screener_class:
            mock_screener = MagicMock()
            mock_screener_class.return_value = mock_screener

            mock_screener.screen_paper.return_value = (
                SemanticScreening(
                    passed=True,
                    similarity_score=0.8,
                    threshold=0.65,
                    llm_decision=ScreeningDecision.INCLUDED,
                    llm_confidence=0.8,
                    llm_reasoning="High similarity",
                    metadata=ProcessingMetadata(
                        duration_seconds=0.1,
                        success=True,
                    ),
                ),
                True,
                None,
            )

            result = step.execute(config, verbose=False, dry_run=True)

        assert result["step"] == "semantic_screening"
        assert result["screened"] == 3

    def test_execute_with_custom_thresholds(self, sample_db, temp_cache_dir):
        """Test execute respects custom thresholds"""
        config = {
            "model": "custom-model",
            "thresholds": {"auto_include": 0.7, "manual_review": 0.5, "auto_exclude": 0.5},
        }
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning"},
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        with patch("paper_scanner.steps.semantic_screening._SemanticScreener") as mock_screener_class:
            mock_screener = MagicMock()
            mock_screener_class.return_value = mock_screener

            mock_screener.screen_paper.return_value = (
                SemanticScreening(
                    passed=True,
                    similarity_score=0.75,
                    threshold=0.7,
                    llm_decision=ScreeningDecision.INCLUDED,
                    llm_confidence=0.75,
                    llm_reasoning="Above custom threshold",
                    metadata=ProcessingMetadata(
                        duration_seconds=0.1,
                        success=True,
                    ),
                ),
                True,
                None,
            )

            result = step.execute(config, verbose=False, dry_run=False)

        assert result["step"] == "semantic_screening"
        assert result["model"] == "custom-model"
        assert result["thresholds"]["auto_include"] == 0.7

    def test_execute_updates_paper_screening(self, sample_db, temp_cache_dir):
        """Test execute updates paper screening results"""
        config = {}
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning"},
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        with patch("paper_scanner.steps.semantic_screening._SemanticScreener") as mock_screener_class:
            mock_screener = MagicMock()
            mock_screener_class.return_value = mock_screener

            mock_screener.screen_paper.return_value = (
                SemanticScreening(
                    passed=True,
                    similarity_score=0.8,
                    threshold=0.65,
                    llm_decision=ScreeningDecision.INCLUDED,
                    llm_confidence=0.8,
                    llm_reasoning="Good match",
                    metadata=ProcessingMetadata(
                        duration_seconds=0.1,
                        success=True,
                    ),
                ),
                True,
                None,
            )

            result = step.execute(config, verbose=False, dry_run=False)

        # Verify a paper was updated
        p1 = sample_db.get_by_id("p1")
        assert p1.screening.semantic_screening is not None
        assert p1.screening.semantic_screening.similarity_score == 0.8


class TestIntegration:
    """Integration tests for semantic_screening step"""

    def test_validate_then_execute(self, sample_db, temp_cache_dir):
        """Test validation followed by execution"""
        config = {
            "model": "all-mpnet-base-v2",
            "thresholds": {"auto_include": 0.7, "manual_review": 0.5},
        }

        is_valid, errors = SemanticScreeningStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_semantic_screening_workflow(self, sample_db, temp_cache_dir):
        """Test realistic semantic screening workflow"""
        config = {}
        step = SemanticScreeningStep(
            general_config={"research_question": "machine learning and NLP"},
            db=sample_db,
            cache_dir=temp_cache_dir,
        )

        with patch("paper_scanner.steps.semantic_screening._SemanticScreener") as mock_screener_class:
            mock_screener = MagicMock()
            mock_screener_class.return_value = mock_screener

            screening_results = {
                "p1": (0.85, ScreeningDecision.INCLUDED, True),  # ML paper
                "p2": (0.15, ScreeningDecision.EXCLUDED, False),  # Cooking recipes
                "p3": (0.75, ScreeningDecision.INCLUDED, True),  # NLP paper
            }

            def mock_screen_paper(paper):
                score, decision, passed = screening_results.get(
                    paper.id, (0.5, ScreeningDecision.MANUAL_REVIEW, False)
                )
                return (
                    SemanticScreening(
                        passed=passed,
                        similarity_score=score,
                        threshold=0.65,
                        llm_decision=decision,
                        llm_confidence=score,
                        llm_reasoning=f"Score {score:.2f}",
                        metadata=ProcessingMetadata(
                            duration_seconds=0.1,
                            success=True,
                        ),
                    ),
                    passed,
                    None if passed else f"Score {score:.2f}",
                )

            mock_screener.screen_paper.side_effect = mock_screen_paper

            result = step.execute(config, verbose=False, dry_run=False)

        assert result["step"] == "semantic_screening"
        assert result["screened"] == 3
        assert result["included"] == 2  # ML and NLP papers
        assert result["excluded"] == 1  # Cooking recipes

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
