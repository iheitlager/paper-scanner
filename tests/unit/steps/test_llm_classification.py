"""
Execution/Integration tests for LLMClassificationStep

Tests actual execution flow including database updates, mocking Claude API responses,
and verification of classification results.

Run with:
    pytest tests/unit/steps/test_llm_classification_execution.py -v
"""

from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone
import uuid

import pytest

from paper_scanner.core.enum import ScreeningDecision, PaperType
from paper_scanner.core.models import Paper, Author, Screening, SemanticScreening, ProcessingMetadata
from paper_scanner.steps.llm_classification import LLMClassificationStep, _LLMClassifier



class TestValidate:
    """Tests for LLM classification step configuration validation"""

    def test_validate_empty_config(self):
        """Should accept empty config (all parameters are optional)"""
        is_valid, errors = LLMClassificationStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_model_string(self):
        """Should accept string model parameter"""
        config = {"model": "claude-opus-4-20250514"}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_model_not_string(self):
        """Should reject non-string model"""
        config = {"model": 123}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("model" in e.lower() and "string" in e.lower() for e in errors)

    def test_validate_thresholds_dict(self):
        """Should accept thresholds as dict"""
        config = {
            "thresholds": {
                "auto_include": 0.75,
                "manual_review": 0.55,
                "auto_exclude": 0.55
            }
        }
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_thresholds_not_dict(self):
        """Should reject thresholds not dict"""
        config = {"thresholds": 0.75}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("thresholds" in e.lower() and "dictionary" in e.lower() for e in errors)

    def test_validate_threshold_auto_include_valid(self):
        """Should accept auto_include threshold between 0 and 1"""
        config = {"thresholds": {"auto_include": 0.75}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_auto_include_not_number(self):
        """Should reject non-numeric auto_include"""
        config = {"thresholds": {"auto_include": "0.75"}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("auto_include" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_threshold_auto_include_below_zero(self):
        """Should reject auto_include below 0"""
        config = {"thresholds": {"auto_include": -0.1}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("auto_include" in e.lower() and ("0" in e and "1" in e) for e in errors)

    def test_validate_threshold_auto_include_above_one(self):
        """Should reject auto_include above 1"""
        config = {"thresholds": {"auto_include": 1.5}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("auto_include" in e.lower() and ("0" in e and "1" in e) for e in errors)

    def test_validate_threshold_manual_review_valid(self):
        """Should accept manual_review threshold between 0 and 1"""
        config = {"thresholds": {"manual_review": 0.55}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_manual_review_not_number(self):
        """Should reject non-numeric manual_review"""
        config = {"thresholds": {"manual_review": "0.55"}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("manual_review" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_threshold_manual_review_invalid_range(self):
        """Should reject manual_review outside [0, 1]"""
        config = {"thresholds": {"manual_review": 2.0}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("manual_review" in e.lower() for e in errors)

    def test_validate_threshold_auto_exclude_valid(self):
        """Should accept auto_exclude threshold between 0 and 1"""
        config = {"thresholds": {"auto_exclude": 0.55}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_auto_exclude_not_number(self):
        """Should reject non-numeric auto_exclude"""
        config = {"thresholds": {"auto_exclude": "0.55"}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("auto_exclude" in e.lower() and "number" in e.lower() for e in errors)

    def test_validate_threshold_auto_exclude_invalid_range(self):
        """Should reject auto_exclude outside [0, 1]"""
        config = {"thresholds": {"auto_exclude": -1.0}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert any("auto_exclude" in e.lower() for e in errors)

    def test_validate_threshold_boundary_zero(self):
        """Should accept threshold value of exactly 0"""
        config = {"thresholds": {"auto_include": 0}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_boundary_one(self):
        """Should accept threshold value of exactly 1"""
        config = {"thresholds": {"auto_include": 1}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_integer_value(self):
        """Should accept integer threshold values"""
        config = {"thresholds": {"auto_include": 1, "auto_exclude": 0}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_threshold_partial_thresholds(self):
        """Should accept partial threshold specification"""
        config = {"thresholds": {"auto_include": 0.8}}
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_multiple_errors(self):
        """Should collect multiple validation errors"""
        config = {
            "model": 123,
            "thresholds": {
                "auto_include": "invalid",
                "manual_review": 2.0
            }
        }
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is False
        assert len(errors) >= 2

    def test_validate_model_and_thresholds_together(self):
        """Should accept model and thresholds together"""
        config = {
            "model": "claude-3-5-sonnet-20241022",
            "thresholds": {
                "auto_include": 0.7,
                "manual_review": 0.5,
                "auto_exclude": 0.3
            }
        }
        is_valid, errors = LLMClassificationStep.validate(config)
        assert is_valid is True
        assert errors == []


def create_test_paper(title="Test", abstract="Abstract", **kwargs):
    """Helper to create a test Paper with required fields"""
    defaults = {
        "id": str(uuid.uuid4()),
        "cite_key": f"test_{hash(title) % 10000}",
        "title": title,
        "abstract": abstract,
        "paper_type": PaperType.JOURNAL_ARTICLE,
    }
    defaults.update(kwargs)
    return Paper(**defaults)


class TestLLMClassifierBasic:
    """Tests for _LLMClassifier basic functionality"""

    def test_classifier_initialization(self):
        """Should initialize classifier with required parameters"""
        classifier = _LLMClassifier(
            research_question="How to improve software quality?",
            research_dimensions=["Testing", "Code Review"],
            model_name="claude-3-5-sonnet-20241022",
            api_key="test-key",
            auto_include_threshold=0.75,
            manual_review_threshold=0.55,
        )
        
        assert classifier.research_question == "How to improve software quality?"
        assert classifier.research_dimensions == ["Testing", "Code Review"]
        assert classifier.model_name == "claude-3-5-sonnet-20241022"
        assert classifier.auto_include_threshold == 0.75
        assert classifier.manual_review_threshold == 0.55

    def test_format_paper_text_with_all_fields(self):
        """Should format paper text with all available fields"""
        author = Author(given_name="John", family_name="Doe", full_name="John Doe")
        paper = create_test_paper(
            title="Test Paper",
            abstract="This is a test",
            keywords=["testing", "qa"],
            year=2023,
            authors=[author],
        )
        
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Testing"],
            api_key="test-key",
        )
        
        formatted = classifier._format_paper_text(paper)
        
        assert "TITLE: Test Paper" in formatted
        assert "ABSTRACT: This is a test" in formatted
        assert "KEYWORDS: testing, qa" in formatted
        assert "YEAR: 2023" in formatted
        assert "John Doe" in formatted

    def test_format_paper_text_with_missing_fields(self):
        """Should handle missing fields gracefully"""
        paper = create_test_paper(title="Test Paper", abstract=None)
        
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Testing"],
            api_key="test-key",
        )
        
        formatted = classifier._format_paper_text(paper)
        
        assert "TITLE: Test Paper" in formatted
        assert "ABSTRACT:" not in formatted

    def test_build_prompt_structure(self):
        """Should build prompt with correct structure"""
        paper = create_test_paper(title="Test Paper", abstract="Test abstract")
        
        classifier = _LLMClassifier(
            research_question="How to test?",
            research_dimensions=["Unit Testing", "Integration Testing"],
            api_key="test-key",
        )
        
        prompt = classifier._build_prompt(paper)
        
        assert "RESEARCH QUESTION:" in prompt
        assert "How to test?" in prompt
        assert "RESEARCH DIMENSIONS" in prompt
        assert "Unit Testing" in prompt
        assert "Integration Testing" in prompt
        assert "PAPER TO CLASSIFY:" in prompt
        assert "Test Paper" in prompt


class TestClassificationDominanceScoring:
    """Tests for dominance score processing (0.0, 0.5, 1.0)"""

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_with_dominant_dimension(self, mock_claude_class):
        """Should handle 1.0 (dominant) dimension scores"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dimension A": {"applies": True, "dominance": 1.0, "reasoning": "Main focus"},
                    "Dimension B": {"applies": False, "dominance": 0.0, "reasoning": "Not relevant"},
                },
                "overall_decision": "include",
                "summary": "Focused on Dimension A",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dimension A", "Dimension B"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.classification_vector == [1.0, 0.0]
        assert result.classification_labels == ["Dimension A"]
        assert result.decision == ScreeningDecision.INCLUDED
        assert raw["dominant_count"] == 1

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_with_addressed_dimension(self, mock_claude_class):
        """Should handle 0.5 (addressed but not dominant) dimension scores"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dimension A": {"applies": True, "dominance": 0.5, "reasoning": "Discussed"},
                    "Dimension B": {"applies": True, "dominance": 0.5, "reasoning": "Also discussed"},
                },
                "overall_decision": "review",
                "summary": "Both dimensions addressed but not dominant",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dimension A", "Dimension B"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.classification_vector == [0.5, 0.5]
        assert "Dimension A" in result.classification_labels
        assert "Dimension B" in result.classification_labels
        assert raw["applies_count"] == 2
        assert raw["dominant_count"] == 0

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_mixed_scores(self, mock_claude_class):
        """Should handle mixed dominance scores"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 1.0, "reasoning": "Dominant"},
                    "Dim B": {"applies": True, "dominance": 0.5, "reasoning": "Addressed"},
                    "Dim C": {"applies": False, "dominance": 0.0, "reasoning": "Not relevant"},
                },
                "overall_decision": "include",
                "summary": "Mixed scores",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A", "Dim B", "Dim C"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.classification_vector == [1.0, 0.5, 0.0]
        assert raw["dominant_count"] == 1
        assert raw["applies_count"] == 2
        # Average: (1.0 + 0.5 + 0.0) / 3 = 0.5
        assert result.similarity_score == pytest.approx(0.5)

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_normalizes_confidence_to_dominance(self, mock_claude_class):
        """Should normalize old confidence scores to dominance levels"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        # Simulate old response format with confidence instead of dominance
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dimension A": {"applies": True, "confidence": 0.9, "reasoning": "High"},
                    "Dimension B": {"applies": True, "confidence": 0.3, "reasoning": "Low"},
                },
                "overall_decision": "include",
                "summary": "Test",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dimension A", "Dimension B"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        # 0.9 >= 0.75 → 1.0, 0.3 < 0.75 and >= 0.25 → 0.5
        assert result.classification_vector == [1.0, 0.5]


class TestDecisionLogic:
    """Tests for decision-making based on thresholds"""

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_include_decision_high_confidence(self, mock_claude_class):
        """Should mark INCLUDED when avg confidence >= auto_include threshold"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 1.0, "reasoning": "Dominant"},
                },
                "overall_decision": "include",
                "summary": "Clear inclusion",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A"],
            api_key="test-key",
            auto_include_threshold=0.75,
        )
        
        result, _ = classifier.classify_paper(paper)
        
        assert result.decision == ScreeningDecision.INCLUDED

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_exclude_decision_low_confidence(self, mock_claude_class):
        """Should mark EXCLUDED when avg confidence < auto_exclude threshold"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": False, "dominance": 0.0, "reasoning": "Not relevant"},
                },
                "overall_decision": "exclude",
                "summary": "Not relevant",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A"],
            api_key="test-key",
            auto_exclude_threshold=0.55,
        )
        
        result, _ = classifier.classify_paper(paper)
        
        assert result.decision == ScreeningDecision.EXCLUDED

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_manual_review_decision_borderline(self, mock_claude_class):
        """Should mark MANUAL_REVIEW when confidence is between thresholds"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        # Use 0.65 which normalizes to 0.5 (since >= 0.25 but < 0.75)
        # Then: avg = 0.5, which is >= 0.55 (manual_review) but < 0.75 (auto_include)
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 0.65, "reasoning": "Addressed"},
                },
                "overall_decision": "review",
                "summary": "Borderline case",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A"],
            api_key="test-key",
            auto_include_threshold=0.75,
            manual_review_threshold=0.45,
            auto_exclude_threshold=0.45,
        )
        
        result, _ = classifier.classify_paper(paper)
        
        assert result.decision == ScreeningDecision.MANUAL_REVIEW


class TestErrorHandling:
    """Tests for error handling during classification"""

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_api_error(self, mock_claude_class):
        """Should return error result when API fails"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.side_effect = ValueError("API Error")
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dimension A"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.decision == ScreeningDecision.MANUAL_REVIEW
        assert result.passed is False
        assert result.confidence == 0.0
        assert "API Error" in result.reason

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_empty_response(self, mock_claude_class):
        """Should handle empty API response"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        mock_claude.call.return_value = (None, {})
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dimension A"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.decision == ScreeningDecision.MANUAL_REVIEW
        assert result.passed is False


class TestMetadataTracking:
    """Tests for metadata and stats tracking"""

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_tracks_metadata(self, mock_claude_class):
        """Should track processing metadata"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 1.0, "reasoning": "Dominant"},
                },
                "overall_decision": "include",
                "summary": "Test",
            },
            {"output_tokens": 250, "input_tokens": 1000},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert result.metadata is not None
        assert result.metadata.success is True
        assert result.metadata.tokens_used == 250
        assert result.metadata.model_name == "claude-opus-4-20250514"

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_classify_paper_raw_data_completeness(self, mock_claude_class):
        """Should return complete raw data with all tracking info"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 1.0, "reasoning": "Dominant"},
                    "Dim B": {"applies": True, "dominance": 0.5, "reasoning": "Addressed"},
                },
                "overall_decision": "include",
                "summary": "Test summary",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A", "Dim B"],
            api_key="test-key",
        )
        
        result, raw = classifier.classify_paper(paper)
        
        assert "classifications" in raw
        assert "overall_decision" in raw
        assert "summary" in raw
        assert "classification_vector" in raw
        assert "classification_labels" in raw
        assert "applies_count" in raw
        assert "dominant_count" in raw
        assert "dimension_count" in raw
        assert raw["dimension_count"] == 2
        assert raw["applies_count"] == 2
        assert raw["dominant_count"] == 1


class TestSemanticScreeningModel:
    """Tests for SemanticScreening model integration"""

    @patch("paper_scanner.steps.llm_classification.ClaudeHandler")
    def test_semantic_screening_result_structure(self, mock_claude_class):
        """Should create properly structured SemanticScreening result"""
        mock_claude = MagicMock()
        mock_claude_class.return_value = mock_claude
        
        mock_claude.call.return_value = (
            {
                "classifications": {
                    "Dim A": {"applies": True, "dominance": 1.0, "reasoning": "Dominant"},
                },
                "overall_decision": "include",
                "summary": "Relevant paper",
            },
            {"output_tokens": 100, "input_tokens": 500},
        )
        
        paper = create_test_paper(title="Test", abstract="Abstract")
        classifier = _LLMClassifier(
            research_question="Test",
            research_dimensions=["Dim A"],
            api_key="test-key",
        )
        
        result, _ = classifier.classify_paper(paper)
        
        assert isinstance(result, SemanticScreening)
        assert result.passed is True
        assert result.classification_vector == [1.0]
        assert result.classification_labels == ["Dim A"]
        assert result.confidence is not None
        assert result.reason is not None
        assert result.decision == ScreeningDecision.INCLUDED
