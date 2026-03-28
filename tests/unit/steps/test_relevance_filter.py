"""Tests for RelevanceFilterStep."""

import uuid

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import PaperType, ScreeningDecision, StepStatus
from paper_scanner.core.models import Author, Paper, RelevanceScore
from paper_scanner.steps.relevance_filter import RelevanceFilterStep


def _make_paper(relevance=None, confidence=None, **kwargs):
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

    return paper


def _make_step(papers, tmp_path, general_config=None):
    db = PapersDatabase()
    for p in papers:
        db.add(p)
    return RelevanceFilterStep(
        general_config=general_config or {},
        db=db,
        cache_dir=tmp_path,
    ), db


# ============================================================================
# Validation tests
# ============================================================================


class TestValidate:
    def test_empty_config(self):
        is_valid, errors = RelevanceFilterStep.validate({})
        assert is_valid is True

    def test_valid_thresholds(self):
        config = {"relevance_threshold": 0.6, "confidence_threshold": 0.8}
        is_valid, errors = RelevanceFilterStep.validate(config)
        assert is_valid is True

    def test_invalid_relevance_threshold_type(self):
        is_valid, errors = RelevanceFilterStep.validate({"relevance_threshold": "high"})
        assert is_valid is False

    def test_out_of_range_threshold(self):
        is_valid, errors = RelevanceFilterStep.validate({"relevance_threshold": 1.5})
        assert is_valid is False

    def test_invalid_require_both(self):
        is_valid, errors = RelevanceFilterStep.validate({"require_both": "yes"})
        assert is_valid is False

    def test_invalid_action(self):
        is_valid, errors = RelevanceFilterStep.validate({"action": "delete"})
        assert is_valid is False

    def test_valid_action_exclude(self):
        is_valid, errors = RelevanceFilterStep.validate({"action": "exclude"})
        assert is_valid is True

    def test_valid_action_flag(self):
        is_valid, errors = RelevanceFilterStep.validate({"action": "flag_for_review"})
        assert is_valid is True


# ============================================================================
# Execute tests
# ============================================================================


class TestExecute:
    def test_passes_above_thresholds(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"relevance_threshold": 0.5, "confidence_threshold": 0.7})
        assert result.status == StepStatus.SUCCESS
        assert result.stats["passed"] == 1
        assert result.stats["filtered"] == 0

    def test_excludes_below_thresholds(self, tmp_path):
        paper = _make_paper(relevance=0.3, confidence=0.4)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"relevance_threshold": 0.5, "confidence_threshold": 0.7})
        assert result.stats["passed"] == 0
        assert result.stats["filtered"] == 1
        assert paper.screening.final_decision == ScreeningDecision.EXCLUDED

    def test_require_both_true(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.3)  # high relevance, low confidence
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "relevance_threshold": 0.5,
            "confidence_threshold": 0.7,
            "require_both": True,
        })
        assert result.stats["filtered"] == 1

    def test_require_both_false(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.3)  # high relevance, low confidence
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "relevance_threshold": 0.5,
            "confidence_threshold": 0.7,
            "require_both": False,
        })
        assert result.stats["passed"] == 1  # passes because relevance is high

    def test_flag_for_review_action(self, tmp_path):
        paper = _make_paper(relevance=0.3, confidence=0.4)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({
            "relevance_threshold": 0.5,
            "action": "flag_for_review",
        })
        assert result.stats["flagged"] == 1
        assert paper.screening.final_decision == ScreeningDecision.MANUAL_REVIEW

    def test_skips_papers_without_scores(self, tmp_path):
        paper = _make_paper()  # no relevance scores
        step, db = _make_step([paper], tmp_path)

        result = step.execute({})
        assert result.stats["total_papers"] == 0

    def test_skips_excluded_papers(self, tmp_path):
        paper = _make_paper(relevance=0.8, confidence=0.9)
        paper.screening.final_decision = ScreeningDecision.EXCLUDED
        step, db = _make_step([paper], tmp_path)

        result = step.execute({})
        assert result.stats["total_papers"] == 0

    def test_mixed_papers(self, tmp_path):
        high = _make_paper(relevance=0.9, confidence=0.95)
        low = _make_paper(relevance=0.1, confidence=0.2)
        medium = _make_paper(relevance=0.6, confidence=0.5)
        step, db = _make_step([high, low, medium], tmp_path)

        result = step.execute({
            "relevance_threshold": 0.5,
            "confidence_threshold": 0.7,
        })
        assert result.stats["passed"] == 1  # only high
        assert result.stats["filtered"] == 2  # low + medium (medium has low confidence)

    def test_exact_threshold_passes(self, tmp_path):
        paper = _make_paper(relevance=0.5, confidence=0.7)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"relevance_threshold": 0.5, "confidence_threshold": 0.7})
        assert result.stats["passed"] == 1

    def test_dry_run_does_not_persist(self, tmp_path):
        paper = _make_paper(relevance=0.1, confidence=0.1)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({"relevance_threshold": 0.5}, dry_run=True)
        assert result.stats["filtered"] == 1
        assert paper.screening.final_decision == ScreeningDecision.PENDING  # not changed

    def test_no_papers_returns_success(self, tmp_path):
        step, db = _make_step([], tmp_path)
        result = step.execute({})
        assert result.status == StepStatus.SUCCESS
        assert result.stats["total_papers"] == 0

    def test_default_thresholds(self, tmp_path):
        # Default: relevance >= 0.5, confidence >= 0.7, require_both=True
        paper = _make_paper(relevance=0.55, confidence=0.75)
        step, db = _make_step([paper], tmp_path)

        result = step.execute({})
        assert result.stats["passed"] == 1
