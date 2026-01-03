"""
Unit tests for LLMClassificationStep

Tests LLM-based paper classification using Claude.

Run with:
    pytest tests/unit/steps/test_llm_classification.py -v
"""

import pytest

from paper_scanner.steps.llm_classification import LLMClassificationStep


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
