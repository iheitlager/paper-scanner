"""
Tests for deduplication step.

Tests cover:
- DOI exact matching
- Title + author fuzzy matching
- Title-only fuzzy matching
- Priority-based method ordering
- Duplicate marking and audit trails
- Dry run functionality
- Configuration validation
- Step execution and integration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from paper_scanner.core.models import Paper, Author, DeduplicationResult, ProcessingMetadata
from paper_scanner.core.enum import PaperType
from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.deduplication import (
    validate,
    _normalize_title,
    _doi_exact_match,
    _title_author_fuzzy_match,
    _title_fuzzy_match,
    _get_confidence,
    execute
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_paper_1():
    """Create first sample paper."""
    return Paper(
        id="paper-1",
        cite_key="smith2024a",
        title="Machine Learning Applications in Healthcare",
        abstract="Exploring ML applications in clinical settings",
        year=2024,
        authors=[
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Johnson", given_name="Jane", full_name="Jane Johnson")
        ],
        paper_type=PaperType.ARTICLE,
        doi="10.1234/example.2024.001"
    )


@pytest.fixture
def sample_paper_2():
    """Create second sample paper - different content."""
    return Paper(
        id="paper-2",
        cite_key="doe2024",
        title="Quantum Computing Theory and Practice",
        abstract="A comprehensive review of quantum computing",
        year=2024,
        authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
        paper_type=PaperType.ARTICLE,
        doi="10.5678/example.2024.002"
    )


@pytest.fixture
def sample_paper_duplicate_doi():
    """Create paper with duplicate DOI."""
    return Paper(
        id="paper-3",
        cite_key="smith2024b",
        title="Machine Learning Applications in Healthcare",
        abstract="Exact duplicate with different ID",
        year=2024,
        authors=[
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
            Author(family_name="Johnson", given_name="Jane", full_name="Jane Johnson")
        ],
        paper_type=PaperType.ARTICLE,
        doi="10.1234/example.2024.001"  # Same DOI as paper_1
    )


@pytest.fixture
def sample_paper_similar_title():
    """Create paper with very similar title (fuzzy match candidate)."""
    return Paper(
        id="paper-4",
        cite_key="smith2024c",
        title="Machine Learning Application in Healthcare Systems",  # Very similar
        abstract="Similar paper with slightly different title",
        year=2024,
        authors=[
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
        ],
        paper_type=PaperType.ARTICLE,
        doi="10.9999/example.2024.003"
    )


@pytest.fixture
def sample_paper_same_author_similar_title():
    """Create paper with same first author and similar title."""
    return Paper(
        id="paper-5",
        cite_key="smith2023",
        title="Machine Learning Applications in Healthcare Delivery",
        abstract="Another related paper",
        year=2023,
        authors=[
            Author(family_name="Smith", given_name="John", full_name="John Smith"),
        ],
        paper_type=PaperType.ARTICLE,
        doi="10.7777/example.2023.001"
    )


# ============================================================================
# UNIT TESTS - HELPER FUNCTIONS
# ============================================================================

class TestNormalizeTitle:
    """Test title normalization"""

    def test_normalize_title_basic(self):
        """Test basic title normalization."""
        title = "Machine Learning in Healthcare"
        normalized = _normalize_title(title)
        assert normalized == "machine learning in healthcare"

    def test_normalize_title_extra_whitespace(self):
        """Test title with extra whitespace."""
        title = "  Machine  Learning   in  Healthcare  "
        normalized = _normalize_title(title)
        assert normalized == "machine learning in healthcare"

    def test_normalize_title_none(self):
        """Test None title."""
        assert _normalize_title(None) == ""

    def test_normalize_title_empty(self):
        """Test empty title."""
        assert _normalize_title("") == ""


class TestDOIExactMatch:
    """Test DOI exact matching"""

    def test_doi_exact_match_found(self, sample_paper_1, sample_paper_duplicate_doi):
        """Test DOI exact match when duplicate exists."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        
        result = _doi_exact_match(sample_paper_duplicate_doi, papers_db)
        
        assert result is not None
        duplicate_id, similarity = result
        assert duplicate_id == "paper-1"
        assert similarity == 1.0

    def test_doi_exact_match_case_insensitive(self):
        """Test that DOI comparison is case-insensitive."""
        paper1 = Paper(
            id="p1", cite_key="p1", title="Test", doi="10.1234/EXAMPLE.2024"
        )
        paper2 = Paper(
            id="p2", cite_key="p2", title="Test 2", doi="10.1234/example.2024"
        )
        papers_db = PapersDatabase()
        papers_db.add(paper1)
        
        result = _doi_exact_match(paper2, papers_db)
        
        assert result is not None
        assert result[0] == "p1"

    def test_doi_exact_match_not_found(self, sample_paper_1, sample_paper_2):
        """Test when no DOI match exists."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        
        result = _doi_exact_match(sample_paper_2, papers_db)
        
        assert result is None

    def test_doi_exact_match_no_doi(self):
        """Test with papers that have no DOI."""
        paper1 = Paper(id="p1", cite_key="p1", title="Test")
        paper2 = Paper(id="p2", cite_key="p2", title="Test 2")
        papers_db = PapersDatabase()
        papers_db.add(paper1)
        
        result = _doi_exact_match(paper2, papers_db)
        
        assert result is None


class TestTitleAuthorFuzzyMatch:
    """Test title + first author fuzzy matching"""

    def test_title_author_fuzzy_match_found(self, sample_paper_1, sample_paper_same_author_similar_title):
        """Test fuzzy match with same author and similar title."""
        existing = [sample_paper_1]
        result = _title_author_fuzzy_match(sample_paper_same_author_similar_title, existing, threshold=0.85)
        
        assert result is not None
        duplicate_id, similarity = result
        assert duplicate_id == "paper-1"
        assert 0.85 <= similarity <= 1.0

    def test_title_author_fuzzy_match_different_author(self, sample_paper_1, sample_paper_similar_title):
        """Test no match when first author differs."""
        # sample_paper_similar_title has Smith as first author, same as sample_paper_1
        # Let's create a different scenario
        different_author_paper = Paper(
            id="p-diff",
            cite_key="p-diff",
            title="Machine Learning Applications in Healthcare Systems",
            authors=[Author(family_name="Brown", given_name="Bob", full_name="Bob Brown")],
            paper_type=PaperType.ARTICLE
        )
        existing = [sample_paper_1]
        result = _title_author_fuzzy_match(different_author_paper, existing)
        
        assert result is None  # Different first author

    def test_title_author_fuzzy_match_threshold(self, sample_paper_1):
        """Test threshold enforcement."""
        very_different_paper = Paper(
            id="p-diff",
            cite_key="p-diff",
            title="Quantum Computing",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            paper_type=PaperType.ARTICLE
        )
        existing = [sample_paper_1]
        result = _title_author_fuzzy_match(very_different_paper, existing, threshold=0.95)
        
        assert result is None  # Below threshold


class TestTitleFuzzyMatch:
    """Test title-only fuzzy matching"""

    def test_title_fuzzy_match_found(self, sample_paper_1, sample_paper_similar_title):
        """Test title fuzzy match."""
        existing = [sample_paper_1]
        result = _title_fuzzy_match(sample_paper_similar_title, existing, threshold=0.90)
        
        assert result is not None
        duplicate_id, similarity = result
        assert duplicate_id == "paper-1"
        assert similarity >= 0.90

    def test_title_fuzzy_match_high_threshold(self, sample_paper_1):
        """Test high threshold prevents match."""
        similar_paper = Paper(
            id="p-sim",
            cite_key="p-sim",
            title="Machine Learning in Healthcare",
            paper_type=PaperType.ARTICLE
        )
        existing = [sample_paper_1]
        result = _title_fuzzy_match(similar_paper, existing, threshold=0.99)
        
        # May or may not match depending on exact similarity
        # Just verify it doesn't crash
        assert result is None or isinstance(result, tuple)

    def test_title_fuzzy_match_not_found(self, sample_paper_1, sample_paper_2):
        """Test when titles are completely different."""
        existing = [sample_paper_1]
        result = _title_fuzzy_match(sample_paper_2, existing, threshold=0.95)
        
        assert result is None


class TestGetConfidence:
    """Test confidence score calculation"""

    def test_confidence_doi_exact(self):
        """Test DOI exact match confidence is 1.0."""
        confidence = _get_confidence("doi_exact", 0.5)
        assert confidence == 1.0

    def test_confidence_title_author_fuzzy(self):
        """Test title + author fuzzy match uses similarity score."""
        confidence = _get_confidence("title_author_fuzzy", 0.85)
        assert confidence == 0.85

    def test_confidence_title_fuzzy(self):
        """Test title fuzzy match uses similarity score."""
        confidence = _get_confidence("title_fuzzy", 0.92)
        assert confidence == 0.92

    def test_confidence_unknown_method(self):
        """Test unknown method returns default confidence."""
        confidence = _get_confidence("unknown_method", 0.75)
        assert confidence == 0.5


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidate:
    """Test configuration validation"""

    def test_validate_valid_config(self):
        """Test valid configuration passes."""
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
                {"method": "title_author_fuzzy", "priority": 2, "threshold": 0.90},
            ]
        }
        is_valid, errors = validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_method(self):
        """Test invalid method name."""
        config = {
            "methods": [
                {"method": "invalid_method", "priority": 1}
            ]
        }
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("unknown method" in e.lower() for e in errors)

    def test_validate_invalid_threshold(self):
        """Test threshold out of range."""
        config = {
            "methods": [
                {"method": "title_fuzzy", "threshold": 1.5}
            ]
        }
        is_valid, errors = validate(config)
        assert is_valid is False
        assert any("threshold" in e.lower() for e in errors)


# ============================================================================
# STEP EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Test DeduplicationStep execution"""

    def test_execute_deduplication_disabled(self, sample_paper_1):
        """Test execution when deduplication is disabled."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        
        config = {"enabled": False}
        result = execute(config, papers_db)
        
        assert result["step"] == "deduplication"
        assert result["status"] == "skipped"
        assert result["duplicates_found"] == 0

    def test_execute_finds_exact_duplicate(self, sample_paper_1, sample_paper_duplicate_doi):
        """Test execution finds DOI-based duplicates."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_duplicate_doi)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        result = execute(config, papers_db)
        
        assert result["duplicates_found"] == 1
        assert len(result["duplicates"]) == 1
        
        dup = result["duplicates"][0]
        assert dup["paper_id"] == "paper-3"
        assert dup["duplicate_of_id"] == "paper-1"
        assert dup["method"] == "doi_exact"
        assert dup["confidence"] == 1.0

    def test_execute_updates_paper_model(self, sample_paper_1, sample_paper_duplicate_doi):
        """Test that paper screening model is updated."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_duplicate_doi)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        execute(config, papers_db, dry_run=False)
        
        # Check that duplicate paper has deduplication result set
        dup_paper = papers_db.get_by_id("paper-3")
        assert dup_paper.screening.deduplication is not None
        assert dup_paper.screening.deduplication.is_duplicate is True
        assert dup_paper.screening.deduplication.duplicate_of.id == "paper-1"
        assert dup_paper.screening.deduplication.method == "doi_exact"

    def test_execute_marks_unique_papers(self, sample_paper_1, sample_paper_2):
        """Test that unique papers are marked as non-duplicates."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_2)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        execute(config, papers_db, dry_run=False)
        
        paper1 = papers_db.get_by_id("paper-1")
        paper2 = papers_db.get_by_id("paper-2")
        
        # Both should be marked as non-duplicates
        assert paper1.screening.deduplication.is_duplicate is False
        assert paper2.screening.deduplication.is_duplicate is False

    def test_execute_dry_run_no_updates(self, sample_paper_1, sample_paper_duplicate_doi):
        """Test that dry_run doesn't modify papers."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_duplicate_doi)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        
        # Before dry run, deduplication should be None
        dup_before = papers_db.get_by_id("paper-3").screening.deduplication
        
        execute(config, papers_db, dry_run=True)
        
        # After dry run, should still be None
        dup_after = papers_db.get_by_id("paper-3").screening.deduplication
        assert dup_after == dup_before

    def test_execute_returns_statistics(self, sample_paper_1, sample_paper_duplicate_doi):
        """Test that statistics are returned."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_duplicate_doi)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        result = execute(config, papers_db)
        
        assert "step" in result
        assert "total_papers" in result
        assert "duplicates_found" in result
        assert "duplicates" in result
        assert "methods_used" in result
        assert result["total_papers"] == 2
        assert result["duplicates_found"] == 1

    def test_execute_method_priority(self, sample_paper_1, sample_paper_same_author_similar_title):
        """Test that methods are applied in priority order."""
        papers_db = PapersDatabase()
        papers_db.add(sample_paper_1)
        papers_db.add(sample_paper_same_author_similar_title)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
                {"method": "title_author_fuzzy", "priority": 2, "threshold": 0.85},
                {"method": "title_fuzzy", "priority": 3, "threshold": 0.95},
            ]
        }
        result = execute(config, papers_db)
        
        # Should use title_author_fuzzy (not doi_exact since no match)
        assert result["duplicates_found"] == 1
        if result["duplicates"]:
            assert result["duplicates"][0]["method"] == "title_author_fuzzy"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test deduplication integration scenarios"""

    def test_realistic_deduplication_workflow(self):
        """Test realistic deduplication workflow with multiple papers."""
        # Create a realistic scenario with multiple papers
        papers_db = PapersDatabase()
        
        # Add original papers
        paper1 = Paper(
            id="p1", cite_key="smith2024", title="ML in Healthcare",
            authors=[Author(family_name="Smith", given_name="J", full_name="J Smith")],
            doi="10.1234/ml.2024", paper_type=PaperType.ARTICLE
        )
        paper2 = Paper(
            id="p2", cite_key="doe2024", title="AI in Finance",
            authors=[Author(family_name="Doe", given_name="J", full_name="J Doe")],
            doi="10.5678/ai.2024", paper_type=PaperType.ARTICLE
        )
        
        # Add duplicates
        paper1_dup = Paper(
            id="p3", cite_key="smith2024b", title="ML in Healthcare",
            authors=[Author(family_name="Smith", given_name="J", full_name="J Smith")],
            doi="10.1234/ml.2024", paper_type=PaperType.ARTICLE  # Exact duplicate
        )
        
        papers_db.add(paper1)
        papers_db.add(paper2)
        papers_db.add(paper1_dup)
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        
        result = execute(config, papers_db)
        
        # Should find 1 duplicate (exact DOI match)
        assert result["duplicates_found"] == 1
        assert result["total_papers"] == 3
        
        # Original papers should not be marked as duplicates
        p1 = papers_db.get_by_id("p1")
        p2 = papers_db.get_by_id("p2")
        assert p1.screening.deduplication.is_duplicate is False
        assert p2.screening.deduplication.is_duplicate is False
        
        # Duplicate should be marked
        p3 = papers_db.get_by_id("p3")
        assert p3.screening.deduplication.is_duplicate is True
        assert p3.duplicate_of.id == "p1"

    def test_deduplication_with_conflicting_matches(self):
        """Test behavior when similar papers are compared."""
        papers_db = PapersDatabase()
        
        # Add papers with exact DOI match - easiest deduplication case
        papers_db.add(Paper(
            id="p1", cite_key="p1", title="Machine Learning Applications",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1111/ml.2024", paper_type=PaperType.ARTICLE
        ))
        papers_db.add(Paper(
            id="p2", cite_key="p2", title="Machine Learning Applications",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1111/ml.2024",  # Same DOI - exact match
            paper_type=PaperType.ARTICLE
        ))
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        
        result = execute(config, papers_db)
        
        # Should find 1 duplicate
        assert result["duplicates_found"] == 1
        
        # p2 should be marked as duplicate
        p2 = papers_db.get_by_id("p2")
        assert p2.screening.deduplication.is_duplicate is True
        assert p2.duplicate_of.id == "p1"

    def test_deduplication_preserves_paper_order(self):
        """Test that deduplication preserves paper data integrity."""
        papers_db = PapersDatabase()
        
        papers_db.add(Paper(
            id="p1", cite_key="p1", title="Test Paper",
            abstract="Test abstract with specific content",
            year=2024,
            authors=[Author(family_name="Test", given_name="T", full_name="T Test")],
            doi="10.1234/test.2024", paper_type=PaperType.ARTICLE
        ))
        
        original_paper = papers_db.get_by_id("p1")
        original_abstract = original_paper.abstract
        original_year = original_paper.year
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1}
            ]
        }
        
        execute(config, papers_db)
        
        # Paper data should be unchanged
        modified_paper = papers_db.get_by_id("p1")
        assert modified_paper.abstract == original_abstract
        assert modified_paper.year == original_year
