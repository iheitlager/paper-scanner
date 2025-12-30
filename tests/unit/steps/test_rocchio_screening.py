"""
Unit tests for rocchio_screening step

Tests for Rocchio-based semantic classification functionality.
"""

import pytest

from paper_scanner.steps.keyword_screening import is_substantive_abstract


class TestIsSubstantiveAbstract:
    """Test abstract validation function"""

    def test_substantive_abstract_valid(self):
        """Verify valid abstract is recognized"""
        abstract = (
            "This paper presents a novel approach to digital transformation in manufacturing. "
            "We conducted interviews with 20 companies and identified key success factors."
        )
        assert is_substantive_abstract(abstract) is True

    def test_substantive_abstract_minimum_length(self):
        """Verify abstract must be at least 20 characters"""
        abstract_short = "Short abstract here"
        assert is_substantive_abstract(abstract_short) is False

    def test_substantive_abstract_just_above_minimum(self):
        """Verify abstract just above minimum length is accepted"""
        abstract = "This is an abstract about innovation"
        assert len(abstract) >= 20
        assert is_substantive_abstract(abstract) is True

    def test_boilerplate_conflict_of_interest(self):
        """Verify conflict of interest statement is rejected"""
        abstract = "The authors declare no conflicts of interest."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_no_conflicts(self):
        """Verify 'no conflicts' statement is rejected"""
        abstract = "The authors declare no competing interests or conflicts of interest regarding this publication."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_competing_interests(self):
        """Verify competing interests statement is rejected"""
        abstract = "The authors have no competing interests to declare."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_acknowledgements(self):
        """Verify acknowledgements with funding/thanks is rejected"""
        abstract = "We acknowledge the funding support of our research institutions and sponsors."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_acknowledgments_american(self):
        """Verify American spelling acknowledgments with thanks is rejected"""
        abstract = "The authors would like to thank the reviewers for their helpful comments and feedback."
        assert is_substantive_abstract(abstract) is False

    def test_acknowledgements_standalone_accepted(self):
        """Verify simple acknowledge word in normal context is accepted"""
        abstract = (
            "We acknowledge that digital transformation is important. This study examines how companies "
            "implement new technologies and processes for competitive advantage."
        )
        # This should be accepted because it's actually about research, not just a thanks statement
        assert is_substantive_abstract(abstract) is True

    def test_empty_abstract(self):
        """Verify empty abstract is rejected"""
        assert is_substantive_abstract("") is False

    def test_none_abstract(self):
        """Verify None abstract is rejected"""
        assert is_substantive_abstract(None) is False

    def test_whitespace_only_abstract(self):
        """Verify whitespace-only abstract is rejected"""
        assert is_substantive_abstract("   \n\t  ") is False

    def test_case_insensitive_matching(self):
        """Verify boilerplate detection is case-insensitive"""
        abstract = "THE AUTHORS DECLARE NO CONFLICTS OF INTEREST."
        assert is_substantive_abstract(abstract) is False

    def test_boilerplate_in_middle_of_text(self):
        """Verify boilerplate is rejected even if mixed with real content"""
        abstract = (
            "This paper studies digital innovation in manufacturing. "
            "The authors declare no conflicts of interest. "
            "We conducted extensive research."
        )
        # This should be rejected because it contains conflict of interest statement
        assert is_substantive_abstract(abstract) is False

    def test_valid_abstract_with_long_content(self):
        """Verify long valid abstract is accepted"""
        abstract = (
            "This comprehensive study examines the role of digital transformation in supply chain management. "
            "We conducted interviews with 50 companies across 10 industries and performed statistical analysis. "
            "Our findings show that firms incorporating digital technologies in supplier collaboration achieve 25% "
            "improvement in supply chain efficiency. We identified three critical success factors and developed a "
            "framework for digital innovation adoption."
        )
        assert is_substantive_abstract(abstract) is True

    def test_valid_abstract_exactly_50_characters(self):
        """Verify abstract exactly at 20 character minimum is accepted"""
        abstract = "A" * 20  # Exactly 20 characters
        assert is_substantive_abstract(abstract) is True

    def test_abstract_49_characters_rejected(self):
        """Verify abstract below 20 character minimum is rejected"""
        abstract = "A" * 19  # 19 characters
        assert is_substantive_abstract(abstract) is False
