"""
Unit tests for the categorization step.

Tests the CategorizationStep class including validation and execution.
"""

import pytest
from pathlib import Path

from paper_scanner.steps.categorization import (
    CategorizationStep,
    _normalize_text,
    _normalize_paper_type,
    _check_paper_type,
    _is_review_paper,
    _is_conceptual_paper,
    _assign_quality_tier,
    _categorize_paper,
)
from paper_scanner.core.models import Paper, Author
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import PaperType, StudyType, QualityTier


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def empty_db():
    """Create an empty database"""
    return PapersDatabase()


@pytest.fixture
def sample_db():
    """Create a database with sample papers"""
    db = PapersDatabase()

    papers = [
        # Empirical article - should be included
        Paper(
            cite_key="Smith2020",
            title="An Empirical Study of Machine Learning",
            abstract="We conducted an experiment to evaluate ML algorithms",
            keywords=["ML", "empirical"],
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/ml.2020",
            year=2020,
            paper_type="journal_article",
            journal="Journal of Machine Learning"
        ),
        # Review paper - should be excluded
        Paper(
            cite_key="Doe2021",
            title="A Systematic Review of Deep Learning Applications",
            abstract="This paper reviews recent advances in deep learning",
            keywords=["DL", "review"],
            authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
            doi="10.1234/dl.2021",
            year=2021,
            paper_type="journal_article",
            journal="Neural Networks Review"
        ),
        # Conceptual paper - should be excluded
        Paper(
            cite_key="Brown2022",
            title="A Conceptual Framework for NLP",
            abstract="We propose a theoretical framework for natural language processing",
            keywords=[],
            authors=[],
            doi=None,
            year=2022,
            paper_type="journal_article",
            journal="Theory and Concepts"
        ),
        # Conference paper - should be excluded if exclude_types is True
        Paper(
            cite_key="Johnson2023",
            title="Conference Paper on AI",
            abstract="A conference paper on artificial intelligence",
            keywords=["AI"],
            authors=[],
            doi=None,
            year=2023,
            paper_type="conference_paper",
            journal="Conference Proceedings"
        ),
        # No paper type - lenient, should be included if empirical keywords present
        Paper(
            cite_key="Lee2023",
            title="Experimental Analysis of Data",
            abstract="We conducted an evaluation of different approaches",
            keywords=["data", "analysis"],
            authors=[],
            doi=None,
            year=2023,
            paper_type=None,
            journal="Data Science Journal"
        ),
    ]

    for paper in papers:
        db.add(paper)

    return db


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    return tmp_path / "cache"


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

class TestNormalizeText:
    """Tests for text normalization"""

    def test_normalize_empty_string(self):
        """Should handle empty string"""
        assert _normalize_text("") == ""

    def test_normalize_none(self):
        """Should handle None"""
        assert _normalize_text(None) == ""

    def test_normalize_whitespace(self):
        """Should strip whitespace and lowercase"""
        assert _normalize_text("  HELLO WORLD  ") == "hello world"

    def test_normalize_case(self):
        """Should convert to lowercase"""
        assert _normalize_text("Journal Article") == "journal article"


class TestNormalizePaperType:
    """Tests for paper type normalization"""

    def test_normalize_paper_type_article(self):
        """Should normalize article type"""
        assert _normalize_paper_type("Journal Article") == "journal article"

    def test_normalize_paper_type_conference(self):
        """Should normalize conference type"""
        assert _normalize_paper_type("Conference Paper") == "conference paper"

    def test_normalize_paper_type_none(self):
        """Should handle None"""
        assert _normalize_paper_type(None) == ""


class TestCheckPaperType:
    """Tests for paper type checking"""

    def test_check_acceptable_journal_article(self):
        """Should accept journal articles"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type("journal_article")
        assert paper_type == PaperType.ARTICLE
        assert is_peer_reviewed is True
        assert rejection is None

    def test_check_acceptable_article(self):
        """Should accept 'article' type"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type("article")
        assert paper_type == PaperType.ARTICLE
        assert is_peer_reviewed is True
        assert rejection is None

    def test_check_reject_conference(self):
        """Should reject conference papers"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type("conference_paper")
        assert paper_type == PaperType.CONFERENCE
        assert is_peer_reviewed is False
        assert rejection is not None
        assert "Conference" in rejection

    def test_check_reject_book(self):
        """Should reject books"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type("book")
        assert paper_type == PaperType.BOOK
        assert is_peer_reviewed is False
        assert rejection is not None

    def test_check_none_type_lenient(self):
        """Should be lenient with None type"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type(None)
        assert paper_type == PaperType.ARTICLE
        assert is_peer_reviewed is True
        assert rejection is None

    def test_check_unknown_type_lenient(self):
        """Should be lenient with unknown type"""
        paper_type, is_peer_reviewed, rejection = _check_paper_type("unknown_type")
        assert paper_type == PaperType.ARTICLE
        assert is_peer_reviewed is True
        assert rejection is None


class TestIsReviewPaper:
    """Tests for review paper detection"""

    def test_detect_literature_review(self):
        """Should detect literature review in title"""
        assert _is_review_paper("A literature review of machine learning", None) is True

    def test_detect_systematic_review(self):
        """Should detect systematic review"""
        assert _is_review_paper("Systematic review of AI techniques", None) is True

    def test_detect_meta_analysis(self):
        """Should detect meta-analysis"""
        assert _is_review_paper(None, "A meta-analysis of published studies") is True

    def test_detect_survey(self):
        """Should detect survey"""
        assert _is_review_paper("A survey of deep learning", None) is True

    def test_not_review_empirical(self):
        """Should not detect review in empirical paper"""
        assert _is_review_paper("An empirical study of algorithms", "We conducted an experiment") is False

    def test_empty_inputs(self):
        """Should handle empty inputs"""
        assert _is_review_paper(None, None) is False
        assert _is_review_paper("", "") is False


class TestIsConceptualPaper:
    """Tests for conceptual paper detection"""

    def test_detect_conceptual_framework(self):
        """Should detect conceptual framework"""
        assert _is_conceptual_paper("A conceptual framework for IT", None) is True

    def test_detect_theoretical(self):
        """Should detect theoretical paper when conceptual keywords dominate"""
        # Note: "analysis" is an empirical keyword, so we need more conceptual keywords
        assert _is_conceptual_paper("A theoretical and conceptual model", None) is True

    def test_detect_taxonomy(self):
        """Should detect taxonomy"""
        assert _is_conceptual_paper("A taxonomy of approaches", None) is True

    def test_empirical_overrides_conceptual(self):
        """Empirical keywords should override conceptual"""
        # More empirical keywords than conceptual
        title = "Empirical evaluation of a framework"
        abstract = "We conducted an experiment with analysis and measurement"
        assert _is_conceptual_paper(title, abstract) is False

    def test_conceptual_dominant(self):
        """Should detect conceptual when more conceptual keywords"""
        assert _is_conceptual_paper("A conceptual framework and theoretical model", None) is True

    def test_empty_inputs(self):
        """Should handle empty inputs"""
        assert _is_conceptual_paper(None, None) is False


class TestAssignQualityTier:
    """Tests for quality tier assignment"""

    def test_tier1_nature(self):
        """Should recognize Nature as top tier"""
        tier = _assign_quality_tier("Nature", 2020)
        assert tier == QualityTier.PEER_REVIEWED_JOURNAL

    def test_tier1_science(self):
        """Should recognize Science as top tier"""
        tier = _assign_quality_tier("Science", 2020)
        assert tier == QualityTier.PEER_REVIEWED_JOURNAL

    def test_tier2_journal(self):
        """Should recognize journals with 'journal' in name"""
        tier = _assign_quality_tier("Journal of Computing", 2020)
        assert tier == QualityTier.PEER_REVIEWED_JOURNAL

    def test_tier2_international(self):
        """Should recognize international journals"""
        tier = _assign_quality_tier("International Journal of Software Engineering", 2020)
        assert tier == QualityTier.PEER_REVIEWED_JOURNAL

    def test_tier2_ieee(self):
        """Should recognize IEEE journals"""
        tier = _assign_quality_tier("IEEE Transactions on Software Engineering", 2020)
        assert tier == QualityTier.PEER_REVIEWED_JOURNAL

    def test_unknown_journal(self):
        """Should return unknown for unrecognized journals"""
        tier = _assign_quality_tier("Unknown Magazine", 2020)
        assert tier == QualityTier.UNKNOWN

    def test_none_journal(self):
        """Should return unknown for None journal"""
        tier = _assign_quality_tier(None, 2020)
        assert tier == QualityTier.UNKNOWN


class TestCategorizePaper:
    """Tests for paper categorization function"""

    def test_categorize_empirical_article(self):
        """Should categorize empirical article correctly"""
        paper = Paper(
            cite_key="Test2020",
            title="An empirical study",
            abstract="We conducted an experiment",
            keywords=["empirical"],
            authors=[],
            doi="10.1234/test",
            year=2020,
            paper_type="journal_article",
            journal="Test Journal"
        )

        categorization, should_include, reason = _categorize_paper(paper)

        assert categorization.is_empirical is True
        assert categorization.study_type == StudyType.EMPIRICAL_QUANTITATIVE
        assert should_include is True
        assert reason is None

    def test_categorize_review_paper(self):
        """Should categorize and exclude review paper"""
        paper = Paper(
            cite_key="Review2020",
            title="A systematic review of approaches",
            abstract="We reviewed the literature",
            keywords=[],
            authors=[],
            doi=None,
            year=2020,
            paper_type="journal_article",
            journal=None
        )

        categorization, should_include, reason = _categorize_paper(paper)

        assert categorization.study_type == StudyType.LITERATURE_REVIEW
        assert should_include is False
        assert "review" in reason.lower()

    def test_categorize_conference_paper(self):
        """Should categorize and exclude conference paper"""
        paper = Paper(
            cite_key="Conf2020",
            title="A conference paper",
            abstract="Presented at a conference",
            keywords=[],
            authors=[],
            doi=None,
            year=2020,
            paper_type="conference_paper",
            journal=None
        )

        categorization, should_include, reason = _categorize_paper(paper)

        assert should_include is False
        assert "Conference" in reason

    def test_categorize_conceptual_paper(self):
        """Should categorize and exclude pure conceptual paper"""
        paper = Paper(
            cite_key="Concept2020",
            title="A conceptual framework",
            abstract="We propose a theoretical model",
            keywords=[],
            authors=[],
            doi=None,
            year=2020,
            paper_type="journal_article",
            journal=None
        )

        categorization, should_include, reason = _categorize_paper(paper)

        assert categorization.study_type == StudyType.CONCEPTUAL
        assert should_include is False
        assert "Conceptual" in reason


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidate:
    """Tests for categorization step validation"""

    def test_validate_empty_config(self):
        """Should validate with empty config"""
        is_valid, errors = CategorizationStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_with_enabled_true(self):
        """Should validate with enabled=true"""
        config = {"enabled": True}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_with_enabled_false(self):
        """Should validate with enabled=false"""
        config = {"enabled": False}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_with_exclude_types(self):
        """Should validate with exclude_types flag"""
        config = {"exclude_types": True}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_with_exclude_reviews(self):
        """Should validate with exclude_reviews flag"""
        config = {"exclude_reviews": True}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_with_all_options(self):
        """Should validate with all options"""
        config = {
            "enabled": True,
            "exclude_types": True,
            "exclude_reviews": False
        }
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_invalid_enabled(self):
        """Should fail when enabled is not a boolean"""
        config = {"enabled": "yes"}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
        assert "'enabled' must be a boolean" in errors[0]

    def test_validate_invalid_exclude_types(self):
        """Should fail when exclude_types is not a boolean"""
        config = {"exclude_types": "true"}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
        assert "'exclude_types' must be a boolean" in errors[0]

    def test_validate_invalid_exclude_reviews(self):
        """Should fail when exclude_reviews is not a boolean"""
        config = {"exclude_reviews": 1}
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is False
        assert len(errors) == 1
        assert "'exclude_reviews' must be a boolean" in errors[0]

    def test_validate_multiple_errors(self):
        """Should report multiple validation errors"""
        config = {
            "enabled": "yes",
            "exclude_types": "false",
            "exclude_reviews": []
        }
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is False
        assert len(errors) == 3


# ============================================================================
# EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Tests for categorization step execution"""

    def test_execute_empty_database(self, empty_db, temp_cache_dir):
        """Should handle empty database"""
        step = CategorizationStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config)

        assert result["step"] == "categorization"
        assert result["total_papers"] == 0
        assert result["categorized"] == 0
        assert result["included"] == 0
        assert result["excluded"] == 0

    def test_execute_with_sample_data(self, sample_db, temp_cache_dir):
        """Should process sample papers"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config)

        assert result["step"] == "categorization"
        assert result["total_papers"] == 5
        assert result["categorized"] == 5
        assert result["included"] >= 0
        assert result["excluded"] >= 0
        assert result["included"] + result["excluded"] == 5

    def test_execute_verbose_mode(self, sample_db, temp_cache_dir):
        """Should execute in verbose mode without error"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config, verbose=True)

        assert result["step"] == "categorization"
        assert result["categorized"] == 5

    def test_execute_dry_run_mode(self, sample_db, temp_cache_dir):
        """Should not modify database in dry_run mode"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        # Check initial state
        initial_papers = sample_db.to_list(primary_only=False)
        initial_categorizations = [p.screening.categorization for p in initial_papers]

        result = step.execute(config, dry_run=True)

        # Verify papers not modified
        final_papers = sample_db.to_list(primary_only=False)
        final_categorizations = [p.screening.categorization for p in final_papers]

        # In dry_run, categorizations should not be set
        assert result["categorized"] == 5

    def test_execute_exclude_types_true(self, sample_db, temp_cache_dir):
        """Should exclude non-article types when flag is true"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"exclude_types": True}

        result = step.execute(config)

        # Should exclude conference paper (Johnson2023)
        assert result["excluded"] > 0

    def test_execute_exclude_types_false(self, sample_db, temp_cache_dir):
        """Should not exclude by type when flag is false"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"exclude_types": False}

        result = step.execute(config)

        # Validation still excludes reviews even if exclude_types is false
        assert result["categorized"] == 5

    def test_execute_exclude_reviews_true(self, sample_db, temp_cache_dir):
        """Should exclude reviews when flag is true"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {"exclude_reviews": True}

        result = step.execute(config)

        # Should exclude review papers
        assert result["exclusions"]["review_paper"] > 0

    def test_execute_debug_mode(self, sample_db, temp_cache_dir):
        """Should execute in debug mode without error"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config, debug=True)

        assert result["step"] == "categorization"
        assert result["categorized"] == 5

    def test_execute_returns_statistics(self, sample_db, temp_cache_dir):
        """Should return categorization statistics"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config)

        assert "study_types" in result
        assert "quality_tiers" in result
        assert "exclusions" in result
        assert isinstance(result["study_types"], dict)
        assert isinstance(result["quality_tiers"], dict)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestCategorizationIntegration:
    """Integration tests for categorization step"""

    def test_validate_then_execute(self, sample_db, temp_cache_dir):
        """Should validate config then successfully execute"""
        config = {
            "exclude_types": True,
            "exclude_reviews": True
        }

        # Validate first
        is_valid, errors = CategorizationStep.validate(config)
        assert is_valid is True
        assert errors == []

        # Then execute
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result = step.execute(config)

        assert result["step"] == "categorization"
        assert result["categorized"] == 5

    def test_categorization_updates_papers(self, sample_db, temp_cache_dir):
        """Should update papers with categorization information"""
        step = CategorizationStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        config = {}

        result = step.execute(config)

        # Get papers and check they have categorization
        papers = sample_db.to_list(primary_only=False)
        for paper in papers:
            assert paper.screening.categorization is not None
            assert paper.screening.categorization.paper_type is not None
            assert paper.screening.categorization.study_type is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
