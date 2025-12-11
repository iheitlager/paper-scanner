"""
Tests for keyword_screening step.

Tests cover:
- Keyword matching logic (word boundaries, case insensitivity)
- Field-specific matching (title, abstract, keywords)
- Hard exclusion logic
- Inclusion threshold logic
- Configuration parsing (flat and nested)
- Step execution and integration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from paper_scanner.core.models import Paper, Author, KeywordScreening, ProcessingMetadata
from paper_scanner.core.enum import PaperType, ScreeningDecision
from paper_scanner.steps.keyword_screening import (
    _normalize_text,
    _check_keyword_match,
    _get_field_matches,
    _parse_keyword_config,
    _screen_paper,
    execute
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_paper():
    """Create a sample paper for testing."""
    return Paper(
        id="test-1",
        citekey="test2024",
        title="Digital Innovation in Supply Chain Management",
        abstract="This paper examines how firms leverage digital technologies to transform supplier relationships and create innovation ecosystems.",
        year=2024,
        authors=[Author(name="John Doe")],
        paper_type=PaperType.ARTICLE,
        source_url="https://example.com/paper.pdf"
    )


@pytest.fixture
def sample_paper_no_keywords():
    """Create a paper without inclusion keywords."""
    return Paper(
        id="test-2",
        citekey="test2024b",
        title="Agricultural Technology Review",
        abstract="A comprehensive review of agricultural technologies and farming practices.",
        year=2024,
        authors=[Author(name="Jane Smith")],
        paper_type=PaperType.ARTICLE,
        source_url="https://example.com/paper2.pdf"
    )


@pytest.fixture
def sample_paper_excluded():
    """Create a paper with hard exclusion keywords."""
    return Paper(
        id="test-3",
        citekey="test2024c",
        title="Medical Device Innovation and Patient Care",
        abstract="Clinical outcomes and patient management in hospital settings.",
        year=2024,
        authors=[Author(name="Dr. Medical")],
        paper_type=PaperType.ARTICLE,
        source_url="https://example.com/paper3.pdf"
    )


@pytest.fixture
def keyword_config():
    """Create a keyword screening configuration."""
    return {
        "enabled": True,
        "hard_exclusions": ["medical", "healthcare", "patient", "agriculture", "farming"],
        "inclusion_keywords": ["digital innovation", "firm", "supplier", "ecosystem"],
        "threshold": 2,
        "word_boundaries": True
    }


@pytest.fixture
def keyword_config_nested():
    """Create a nested keyword screening configuration."""
    return {
        "enabled": True,
        "hard_exclusions": {
            "domains": ["medical", "healthcare"],
            "other": ["agriculture", "farming"]
        },
        "inclusion_keywords": {
            "innovation": ["digital innovation", "innovation"],
            "organization": ["firm", "company"],
            "collaboration": ["supplier", "ecosystem"]
        },
        "threshold": 2,
        "word_boundaries": True
    }


# ============================================================================
# TEXT NORMALIZATION TESTS
# ============================================================================

class TestTextNormalization:
    """Test text normalization utilities."""

    def test_normalize_text_empty(self):
        """Test normalization of empty/None text."""
        assert _normalize_text(None) == ""
        assert _normalize_text("") == ""

    def test_normalize_text_case(self):
        """Test that normalization converts to lowercase."""
        result = _normalize_text("HELLO WORLD")
        assert result == "hello world"

    def test_normalize_text_whitespace(self):
        """Test that normalization trims whitespace."""
        result = _normalize_text("  hello world  ")
        assert result == "hello world"

    def test_normalize_text_combined(self):
        """Test normalization with multiple transformations."""
        result = _normalize_text("  DIGITAL INNOVATION  ")
        assert result == "digital innovation"


# ============================================================================
# KEYWORD MATCHING TESTS
# ============================================================================

class TestKeywordMatching:
    """Test keyword matching logic."""

    def test_exact_match(self):
        """Test exact keyword match."""
        text = "digital innovation framework"
        keywords = ["digital innovation"]
        matched, count = _check_keyword_match(text, keywords)
        assert count == 1
        assert "digital innovation" in matched

    def test_case_insensitive_match(self):
        """Test that matching is case insensitive."""
        text = "DIGITAL INNOVATION"
        keywords = ["digital innovation"]
        matched, count = _check_keyword_match(text, keywords)
        assert count == 1

    def test_word_boundary_no_partial_match(self):
        """Test word boundary matching prevents partial matches."""
        text = "supplier ecosystem"
        keywords = ["supply"]
        matched, count = _check_keyword_match(text, keywords, use_word_boundaries=True)
        assert count == 0

    def test_word_boundary_matches_full_word(self):
        """Test word boundary matching matches full words."""
        text = "supplier ecosystem"
        keywords = ["supplier"]
        matched, count = _check_keyword_match(text, keywords, use_word_boundaries=True)
        assert count == 1

    def test_substring_match_without_boundaries(self):
        """Test substring matching without word boundaries."""
        text = "supplier ecosystem"
        keywords = ["supply"]
        matched, count = _check_keyword_match(text, keywords, use_word_boundaries=False)
        assert count == 1

    def test_multiple_keyword_matches(self):
        """Test matching multiple keywords."""
        text = "digital innovation in firms with suppliers"
        keywords = ["digital innovation", "firm", "supplier"]
        matched, count = _check_keyword_match(text, keywords)
        assert count == 3
        assert len(matched) == 3

    def test_no_matches(self):
        """Test when no keywords match."""
        text = "hello world"
        keywords = ["digital", "innovation"]
        matched, count = _check_keyword_match(text, keywords)
        assert count == 0
        assert len(matched) == 0

    def test_empty_keywords_list(self):
        """Test matching with empty keywords list."""
        text = "some text"
        keywords = []
        matched, count = _check_keyword_match(text, keywords)
        assert count == 0


# ============================================================================
# FIELD-SPECIFIC MATCHING TESTS
# ============================================================================

class TestFieldMatching:
    """Test field-specific keyword matching."""

    def test_title_matches(self, sample_paper):
        """Test matching keywords in title."""
        keywords = ["digital innovation", "supply chain"]
        title_matches, abstract_matches, kw_matches, all_matched = _get_field_matches(
            sample_paper, keywords
        )
        assert title_matches >= 1
        assert "digital innovation" in all_matched

    def test_abstract_matches(self, sample_paper):
        """Test matching keywords in abstract."""
        keywords = ["firm", "supplier", "ecosystem"]
        title_matches, abstract_matches, kw_matches, all_matched = _get_field_matches(
            sample_paper, keywords
        )
        # Paper abstract contains "firms", "supplier", "innovation"
        assert abstract_matches >= 1
        assert len(all_matched) >= 1

    def test_combined_matches(self, sample_paper):
        """Test that matches from different fields are combined."""
        keywords = ["digital innovation", "firm", "supplier"]
        title_matches, abstract_matches, kw_matches, all_matched = _get_field_matches(
            sample_paper, keywords
        )
        # Should find matches in both title and abstract
        assert len(all_matched) >= 2

    def test_no_field_matches(self):
        """Test when paper has no matches."""
        paper = Paper(
            id="test",
            citekey="test",
            title="Hello World",
            abstract="Simple text",
            year=2024,
            authors=[],
            paper_type=PaperType.ARTICLE
        )
        keywords = ["digital", "innovation"]
        title_matches, abstract_matches, kw_matches, all_matched = _get_field_matches(
            paper, keywords
        )
        assert len(all_matched) == 0

    def test_paper_without_abstract(self):
        """Test matching when paper has no abstract."""
        paper = Paper(
            id="test",
            citekey="test",
            title="Digital Innovation Framework",
            year=2024,
            authors=[],
            paper_type=PaperType.ARTICLE
        )
        keywords = ["digital innovation"]
        title_matches, abstract_matches, kw_matches, all_matched = _get_field_matches(
            paper, keywords
        )
        assert len(all_matched) == 1
        assert title_matches == 1


# ============================================================================
# CONFIGURATION PARSING TESTS
# ============================================================================

class TestConfigParsing:
    """Test configuration parsing."""

    def test_parse_flat_config(self, keyword_config):
        """Test parsing flat keyword configuration."""
        hard_exc, incl_kw, threshold = _parse_keyword_config(keyword_config)
        assert len(hard_exc) == 5
        assert len(incl_kw) == 4
        assert threshold == 2
        assert "medical" in hard_exc
        assert "digital innovation" in incl_kw

    def test_parse_nested_config(self, keyword_config_nested):
        """Test parsing nested keyword configuration."""
        hard_exc, incl_kw, threshold = _parse_keyword_config(keyword_config_nested)
        assert len(hard_exc) == 4  # medical, healthcare, agriculture, farming
        assert len(incl_kw) == 6  # all values from nested dicts
        assert threshold == 2

    def test_parse_default_threshold(self):
        """Test that threshold defaults to 1."""
        config = {
            "hard_exclusions": ["bad"],
            "inclusion_keywords": ["good"]
        }
        hard_exc, incl_kw, threshold = _parse_keyword_config(config)
        assert threshold == 1

    def test_parse_case_normalization(self):
        """Test that keywords are normalized to lowercase."""
        config = {
            "hard_exclusions": ["Medical", "HEALTHCARE"],
            "inclusion_keywords": ["Digital Innovation", "FIRM"]
        }
        hard_exc, incl_kw, threshold = _parse_keyword_config(config)
        assert "medical" in hard_exc
        assert "healthcare" in hard_exc
        assert "digital innovation" in incl_kw
        assert "firm" in incl_kw

    def test_parse_empty_config(self):
        """Test parsing empty configuration."""
        config = {}
        hard_exc, incl_kw, threshold = _parse_keyword_config(config)
        assert len(hard_exc) == 0
        assert len(incl_kw) == 0
        assert threshold == 1


# ============================================================================
# SCREENING LOGIC TESTS
# ============================================================================

class TestScreeningLogic:
    """Test paper screening logic."""

    def test_hard_exclusion_detected(self, sample_paper_excluded):
        """Test that hard exclusions are detected."""
        hard_exc = ["medical", "patient"]
        incl_kw = ["innovation", "firm"]
        
        screening, passed, reason = _screen_paper(
            sample_paper_excluded, hard_exc, incl_kw, inclusion_threshold=1
        )
        
        assert not passed
        assert screening.passed is False
        assert len(screening.exclusion_keywords) > 0
        assert reason is not None

    def test_no_exclusion_with_threshold_met(self, sample_paper):
        """Test paper passes when threshold is met."""
        hard_exc = ["medical"]
        incl_kw = ["digital innovation", "firm", "supplier"]
        
        screening, passed, reason = _screen_paper(
            sample_paper, hard_exc, incl_kw, inclusion_threshold=2
        )
        
        assert passed
        assert screening.passed is True
        assert screening.score >= 2

    def test_threshold_not_met(self, sample_paper_no_keywords):
        """Test paper fails when threshold is not met."""
        hard_exc = []
        incl_kw = ["digital", "innovation", "firm"]
        
        screening, passed, reason = _screen_paper(
            sample_paper_no_keywords, hard_exc, incl_kw, inclusion_threshold=2
        )
        
        assert not passed
        assert screening.score < 2

    def test_threshold_exactly_met(self, sample_paper):
        """Test paper passes when threshold is exactly met."""
        hard_exc = []
        incl_kw = ["digital innovation", "firm"]
        
        screening, passed, reason = _screen_paper(
            sample_paper, hard_exc, incl_kw, inclusion_threshold=2
        )
        
        assert passed
        assert screening.score >= 2

    def test_screening_metadata_captured(self, sample_paper):
        """Test that screening metadata is properly captured."""
        hard_exc = []
        incl_kw = ["digital innovation"]
        
        screening, passed, reason = _screen_paper(
            sample_paper, hard_exc, incl_kw, inclusion_threshold=1
        )
        
        assert screening.metadata is not None
        assert screening.metadata.processed_at is not None
        assert screening.metadata.duration_seconds >= 0


# ============================================================================
# STEP EXECUTION TESTS
# ============================================================================

class TestStepExecution:
    """Test step execution."""

    def test_execute_disabled_step(self, sample_paper):
        """Test that disabled step is skipped."""
        config = {"enabled": False}
        results = execute(config, [sample_paper])
        
        assert results["status"] == "skipped"
        assert results["step"] == "keyword_screening"

    def test_execute_filters_papers(self, sample_paper, sample_paper_excluded, keyword_config):
        """Test that execute properly filters papers."""
        papers_db = [sample_paper, sample_paper_excluded]
        results = execute(keyword_config, papers_db)
        
        assert results["step"] == "keyword_screening"
        assert results["total_papers"] == 2
        assert results["passed"] >= 1
        assert results["failed"] >= 1

    def test_execute_updates_screening_model(self, sample_paper, keyword_config):
        """Test that execute updates paper screening model."""
        papers_db = [sample_paper]
        execute(keyword_config, papers_db, dry_run=False)
        
        assert papers_db[0].screening.keyword_screening is not None
        assert isinstance(papers_db[0].screening.keyword_screening, KeywordScreening)

    def test_execute_dry_run_no_updates(self, sample_paper, keyword_config):
        """Test that dry_run doesn't modify papers."""
        papers_db = [sample_paper]
        original_screening = papers_db[0].screening.keyword_screening
        
        execute(keyword_config, papers_db, dry_run=True)
        
        assert papers_db[0].screening.keyword_screening == original_screening

    def test_execute_returns_statistics(self, sample_paper, keyword_config):
        """Test that execute returns proper statistics."""
        papers_db = [sample_paper]
        results = execute(keyword_config, papers_db)
        
        assert "total_papers" in results
        assert "passed" in results
        assert "failed" in results
        assert "screened" in results
        assert "score_distribution" in results
        assert "top_matched_keywords" in results
        assert "duration_seconds" in results

    def test_execute_with_multiple_papers(self, sample_paper, sample_paper_no_keywords, 
                                          sample_paper_excluded, keyword_config):
        """Test execute with multiple papers."""
        papers_db = [sample_paper, sample_paper_no_keywords, sample_paper_excluded]
        results = execute(keyword_config, papers_db)
        
        assert results["total_papers"] == 3
        assert results["screened"] == 3
        assert results["passed"] + results["failed"] == 3


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test integration scenarios."""

    def test_realistic_workflow(self):
        """Test realistic screening workflow."""
        # Create papers with varying characteristics
        papers = [
            Paper(
                id="p1", citekey="p1", year=2024,
                title="Digital Innovation in Supply Chain",
                abstract="Firms leverage digital technologies with suppliers.",
                authors=[], paper_type=PaperType.ARTICLE
            ),
            Paper(
                id="p2", citekey="p2", year=2024,
                title="Medical Device Technology",
                abstract="Patient outcomes in clinical settings.",
                authors=[], paper_type=PaperType.ARTICLE
            ),
            Paper(
                id="p3", citekey="p3", year=2024,
                title="Agricultural Farming Practices",
                abstract="Crop management and farm technology.",
                authors=[], paper_type=PaperType.ARTICLE
            ),
        ]
        
        config = {
            "enabled": True,
            "hard_exclusions": ["medical", "patient", "agriculture", "farming"],
            "inclusion_keywords": ["digital", "firm", "supplier", "innovation"],
            "threshold": 2
        }
        
        results = execute(config, papers)
        
        # Should pass p1, fail p2 and p3
        assert results["failed"] >= 2
        assert papers[1].screening.keyword_screening is not None
        assert papers[1].screening.keyword_screening.passed is False

    def test_configurable_threshold(self, sample_paper):
        """Test different threshold values."""
        config_low = {
            "enabled": True,
            "hard_exclusions": [],
            "inclusion_keywords": ["digital innovation"],
            "threshold": 1
        }
        
        config_high = {
            "enabled": True,
            "hard_exclusions": [],
            "inclusion_keywords": ["digital innovation"],
            "threshold": 10
        }
        
        papers_low = [sample_paper]
        papers_high = [sample_paper]
        
        results_low = execute(config_low, papers_low)
        results_high = execute(config_high, papers_high)
        
        # Low threshold should allow more papers
        assert results_low["passed"] >= results_high["passed"]
