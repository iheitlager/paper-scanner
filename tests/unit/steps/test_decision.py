"""Tests for DecisionStep."""

import uuid

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import PaperType, ScreeningDecision, StepStatus
from paper_scanner.core.models import (
    Author,
    KeywordScreening,
    MetadataScreening,
    Paper,
    RelevanceScore,
)
from paper_scanner.steps.decision import DecisionStep, _parse_condition


def _make_paper(
    relevance=None,
    confidence=None,
    keyword_passed=None,
    metadata_passed=None,
    **kwargs,
):
    defaults = {
        "id": str(uuid.uuid4()),
        "cite_key": f"test_{uuid.uuid4().hex[:6]}",
        "title": "Test Paper",
        "paper_type": PaperType.JOURNAL_ARTICLE,
        "year": 2024,
        "authors": [Author(given_name="A", family_name="B", full_name="A B")],
    }
    defaults.update(kwargs)
    paper = Paper(**defaults)

    if relevance is not None and confidence is not None:
        paper.screening.relevance_scoring = RelevanceScore(
            relevance=relevance,
            confidence=confidence,
            justification="Test",
        )

    if keyword_passed is not None:
        paper.screening.keyword_screening = KeywordScreening(
            passed=keyword_passed,
            screening_decision=(
                ScreeningDecision.INCLUDED if keyword_passed else ScreeningDecision.EXCLUDED
            ),
            is_empirical=False,
            is_conceptual=False,
            is_literature_review=False,
            keyword_screening_confidence=0.8,
        )

    if metadata_passed is not None:
        paper.screening.metadata_screening = MetadataScreening(
            passed=metadata_passed,
            paper_type=PaperType.JOURNAL_ARTICLE,
            is_peer_reviewed=True,
        )

    return paper


def _make_step(papers, tmp_path, general_config=None):
    db = PapersDatabase()
    for p in papers:
        db.add(p)
    return DecisionStep(
        general_config=general_config or {},
        db=db,
        cache_dir=tmp_path,
    ), db


# ============================================================================
# Condition parsing tests
# ============================================================================


class TestParseCondition:
    def test_gte(self):
        op, val = _parse_condition(">= 0.6")
        assert op(0.7, val)
        assert op(0.6, val)
        assert not op(0.5, val)

    def test_lt(self):
        op, val = _parse_condition("< 0.3")
        assert op(0.2, val)
        assert not op(0.3, val)

    def test_eq_bool(self):
        op, val = _parse_condition("== true")
        assert op(True, val)
        assert not op(False, val)

    def test_ne_bool(self):
        op, val = _parse_condition("!= false")
        assert op(True, val)
        assert not op(False, val)

    def test_invalid(self):
        with pytest.raises(ValueError):
            _parse_condition("roughly 0.5")


# ============================================================================
# Validation tests
# ============================================================================


class TestValidate:
    def test_empty_config_fails(self):
        is_valid, errors = DecisionStep.validate({})
        assert is_valid is False
        assert "At least one" in errors[0]

    def test_valid_include_only(self):
        config = {"include_when": {"relevance_score": ">= 0.6"}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is True

    def test_valid_exclude_only(self):
        config = {"exclude_when": {"relevance_score": "< 0.3"}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is True

    def test_valid_both(self):
        config = {
            "include_when": {"relevance_score": ">= 0.6", "confidence": ">= 0.7"},
            "exclude_when": {"relevance_score": "< 0.3"},
            "otherwise": "manual_review",
        }
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is True

    def test_unknown_field(self):
        config = {"include_when": {"magic_score": ">= 0.5"}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is False
        assert "Unknown field" in errors[0]

    def test_invalid_condition(self):
        config = {"include_when": {"relevance_score": "roughly 0.5"}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is False

    def test_non_string_condition(self):
        config = {"include_when": {"relevance_score": 0.5}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is False
        assert "must be a string" in errors[0]

    def test_non_dict_block(self):
        config = {"include_when": "high"}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is False
        assert "must be a mapping" in errors[0]

    def test_invalid_otherwise(self):
        config = {"include_when": {"relevance_score": ">= 0.6"}, "otherwise": "delete"}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is False

    def test_otherwise_pending(self):
        config = {"include_when": {"relevance_score": ">= 0.6"}, "otherwise": "pending"}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is True

    def test_boolean_field_condition(self):
        config = {"include_when": {"keyword_passed": "== true"}}
        is_valid, errors = DecisionStep.validate(config)
        assert is_valid is True


# ============================================================================
# Execute tests
# ============================================================================


class TestExecute:
    def test_includes_above_threshold(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.6", "confidence": ">= 0.7"},
        })
        assert result.status == StepStatus.SUCCESS
        assert result.stats["included"] == 1
        assert paper.screening.final_decision == ScreeningDecision.INCLUDED
        assert paper.screening.final_decision_by == "automated:decision"

    def test_excludes_below_threshold(self, tmp_path):
        paper = _make_paper(relevance=0.2, confidence=0.3)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.6"},
            "exclude_when": {"relevance_score": "< 0.3"},
        })
        assert result.stats["excluded"] == 1
        assert paper.screening.final_decision == ScreeningDecision.EXCLUDED

    def test_otherwise_manual_review(self, tmp_path):
        paper = _make_paper(relevance=0.4, confidence=0.5)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.6"},
            "exclude_when": {"relevance_score": "< 0.3"},
            "otherwise": "manual_review",
        })
        assert result.stats["manual_review"] == 1
        assert paper.screening.final_decision == ScreeningDecision.MANUAL_REVIEW

    def test_otherwise_pending(self, tmp_path):
        paper = _make_paper(relevance=0.4, confidence=0.5)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.6"},
            "exclude_when": {"relevance_score": "< 0.3"},
            "otherwise": "pending",
        })
        assert result.stats["pending"] == 1
        assert paper.screening.final_decision == ScreeningDecision.PENDING

    def test_skips_already_excluded(self, tmp_path):
        paper = _make_paper(relevance=0.9, confidence=0.9)
        paper.screening.final_decision = ScreeningDecision.EXCLUDED
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"include_when": {"relevance_score": ">= 0.5"}})
        assert result.stats["total_papers"] == 0

    def test_skips_already_included(self, tmp_path):
        paper = _make_paper(relevance=0.1, confidence=0.1)
        paper.screening.final_decision = ScreeningDecision.INCLUDED
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"exclude_when": {"relevance_score": "< 0.3"}})
        assert result.stats["total_papers"] == 0

    def test_skips_missing_data(self, tmp_path):
        paper = _make_paper()  # no relevance scores
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"include_when": {"relevance_score": ">= 0.5"}})
        assert result.stats["skipped_missing"] == 1

    def test_dry_run_does_not_persist(self, tmp_path):
        paper = _make_paper(relevance=0.9, confidence=0.9)
        step, db = _make_step([paper], tmp_path)

        result = step.execute(
            {"include_when": {"relevance_score": ">= 0.5"}},
            dry_run=True,
        )
        assert result.stats["included"] == 1
        assert paper.screening.final_decision == ScreeningDecision.PENDING

    def test_no_papers_returns_success(self, tmp_path):
        step, db = _make_step([], tmp_path)
        result = step.execute({"include_when": {"relevance_score": ">= 0.5"}})
        assert result.status == StepStatus.SUCCESS
        assert result.stats["total_papers"] == 0

    def test_mixed_papers(self, tmp_path):
        high = _make_paper(relevance=0.9, confidence=0.95)
        low = _make_paper(relevance=0.1, confidence=0.2)
        mid = _make_paper(relevance=0.5, confidence=0.6)
        step, db = _make_step([high, low, mid], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.7", "confidence": ">= 0.7"},
            "exclude_when": {"relevance_score": "< 0.3"},
            "otherwise": "manual_review",
        })
        assert result.stats["included"] == 1
        assert result.stats["excluded"] == 1
        assert result.stats["manual_review"] == 1

    def test_keyword_boolean_condition(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9, keyword_passed=True)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {
                "relevance_score": ">= 0.6",
                "keyword_passed": "== true",
            },
        })
        assert result.stats["included"] == 1

    def test_keyword_false_blocks_include(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9, keyword_passed=False)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {
                "relevance_score": ">= 0.6",
                "keyword_passed": "== true",
            },
            "otherwise": "manual_review",
        })
        assert result.stats["included"] == 0
        assert result.stats["manual_review"] == 1

    def test_metadata_condition(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9, metadata_passed=True)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {
                "relevance_score": ">= 0.6",
                "metadata_passed": "== true",
            },
        })
        assert result.stats["included"] == 1

    def test_include_takes_priority_over_exclude(self, tmp_path):
        """If both include and exclude conditions match, include wins."""
        paper = _make_paper(relevance=0.8, confidence=0.9)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "include_when": {"relevance_score": ">= 0.6"},
            "exclude_when": {"confidence": ">= 0.5"},  # also matches
        })
        assert result.stats["included"] == 1
        assert result.stats["excluded"] == 0

    def test_exclude_only_config(self, tmp_path):
        high = _make_paper(relevance=0.8, confidence=0.9)
        low = _make_paper(relevance=0.1, confidence=0.1)
        step, db = _make_step([high, low], tmp_path)

        result = step.execute({
            "exclude_when": {"relevance_score": "< 0.3"},
            "otherwise": "manual_review",
        })
        assert result.stats["excluded"] == 1
        assert result.stats["manual_review"] == 1

    def test_current_stage_set(self, tmp_path):
        paper = _make_paper(relevance=0.9, confidence=0.9)
        step, db = _make_step([paper], tmp_path)

        step.execute({"include_when": {"relevance_score": ">= 0.5"}})
        assert paper.screening.current_stage == "decision_complete"
