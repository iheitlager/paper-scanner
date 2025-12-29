"""
Unit tests for paper_scanner.core.enum

Tests that all enums are properly defined and contain expected values.
"""

import pytest

from paper_scanner.core.enum import DiscoveryMethod, PaperType, QualityTier, ScreeningDecision, StudyType


class TestPaperType:
    """Test PaperType enum"""

    def test_paper_type_exists(self):
        """Verify PaperType enum can be imported"""
        assert PaperType is not None

    def test_paper_type_is_string_enum(self):
        """Verify PaperType is a string enum"""
        assert issubclass(PaperType, str)

    def test_paper_type_all_members(self):
        """Verify all expected PaperType members exist"""
        expected_members = [
            "JOURNAL_ARTICLE",
            "CONFERENCE_PAPER",
            "BOOK",
            "BOOK_CHAPTER",
            "THESIS",
            "TECHNICAL_REPORT",
            "WORKING_PAPER",
            "PREPRINT",
            "PATENT",
            "REPORT",
            "DATASET",
            "OTHER",
        ]
        actual_members = [member.name for member in PaperType]
        assert set(actual_members) == set(expected_members)
        assert len(actual_members) == 12

    def test_paper_type_values(self):
        """Verify PaperType values are correctly defined"""
        assert PaperType.JOURNAL_ARTICLE.value == "journal_article"
        assert PaperType.CONFERENCE_PAPER.value == "conference_paper"
        assert PaperType.BOOK.value == "book"
        assert PaperType.BOOK_CHAPTER.value == "book_chapter"
        assert PaperType.THESIS.value == "thesis"
        assert PaperType.TECHNICAL_REPORT.value == "technical_report"
        assert PaperType.WORKING_PAPER.value == "working_paper"
        assert PaperType.PREPRINT.value == "preprint"
        assert PaperType.PATENT.value == "patent"
        assert PaperType.OTHER.value == "other"

    def test_paper_type_from_string(self):
        """Verify PaperType can be instantiated from string values"""
        assert PaperType("journal_article") == PaperType.JOURNAL_ARTICLE
        assert PaperType("conference_paper") == PaperType.CONFERENCE_PAPER
        assert PaperType("book") == PaperType.BOOK

    def test_paper_type_string_operations(self):
        """Verify PaperType works as string"""
        paper_type = PaperType.JOURNAL_ARTICLE
        assert str(paper_type) == "PaperType.JOURNAL_ARTICLE"
        assert paper_type == "journal_article"
        assert paper_type.value == "journal_article"


class TestStudyType:
    """Test StudyType enum"""

    def test_study_type_exists(self):
        """Verify StudyType enum can be imported"""
        assert StudyType is not None

    def test_study_type_is_string_enum(self):
        """Verify StudyType is a string enum"""
        assert issubclass(StudyType, str)

    def test_study_type_all_members(self):
        """Verify all expected StudyType members exist"""
        expected_members = [
            "EMPIRICAL_QUALITATIVE",
            "EMPIRICAL_QUANTITATIVE",
            "EMPIRICAL_MIXED",
            "LITERATURE_REVIEW",
            "META_ANALYSIS",
            "CONCEPTUAL",
            "EDITORIAL",
            "THEORETICAL",
            "BOOK_REVIEW",
            "CASE_STUDY",
            "UNKNOWN",
        ]
        actual_members = [member.name for member in StudyType]
        assert set(actual_members) == set(expected_members)
        assert len(actual_members) == 11

    def test_study_type_values(self):
        """Verify StudyType values are correctly defined"""
        assert StudyType.EMPIRICAL_QUALITATIVE.value == "empirical_qualitative"
        assert StudyType.EMPIRICAL_QUANTITATIVE.value == "empirical_quantitative"
        assert StudyType.EMPIRICAL_MIXED.value == "empirical_mixed"
        assert StudyType.LITERATURE_REVIEW.value == "literature_review"
        assert StudyType.META_ANALYSIS.value == "meta_analysis"
        assert StudyType.CONCEPTUAL.value == "conceptual"
        assert StudyType.EDITORIAL.value == "editorial"
        assert StudyType.THEORETICAL.value == "theoretical"
        assert StudyType.BOOK_REVIEW.value == "book_review"
        assert StudyType.CASE_STUDY.value == "case_study"
        assert StudyType.UNKNOWN.value == "unknown"

    def test_study_type_from_string(self):
        """Verify StudyType can be instantiated from string values"""
        assert StudyType("empirical_qualitative") == StudyType.EMPIRICAL_QUALITATIVE
        assert StudyType("literature_review") == StudyType.LITERATURE_REVIEW


class TestQualityTier:
    """Test QualityTier enum"""

    def test_quality_tier_exists(self):
        """Verify QualityTier enum can be imported"""
        assert QualityTier is not None

    def test_quality_tier_is_string_enum(self):
        """Verify QualityTier is a string enum"""
        assert issubclass(QualityTier, str)

    def test_quality_tier_all_members(self):
        """Verify all expected QualityTier members exist"""
        expected_members = [
            "PEER_REVIEWED_JOURNAL",
            "NON_PEER_REVIEWED_ARTICLE",
            "PEER_REVIEWED_CONFERENCE",
            "BOOK_CHAPTER",
            "WORKING_PAPER",
            "PREPRINT",
            "GREY_LITERATURE",
            "UNKNOWN",
        ]
        actual_members = [member.name for member in QualityTier]
        assert set(actual_members) == set(expected_members)
        assert len(actual_members) == 8

    def test_quality_tier_values(self):
        """Verify QualityTier values are correctly defined"""
        assert QualityTier.PEER_REVIEWED_JOURNAL.value == "peer_reviewed_journal"
        assert QualityTier.NON_PEER_REVIEWED_ARTICLE.value == "non_peer_reviewed_article"
        assert (
            QualityTier.PEER_REVIEWED_CONFERENCE.value == "peer_reviewed_conference"
        )
        assert QualityTier.BOOK_CHAPTER.value == "book_chapter"
        assert QualityTier.WORKING_PAPER.value == "working_paper"
        assert QualityTier.PREPRINT.value == "preprint"
        assert QualityTier.GREY_LITERATURE.value == "grey_literature"
        assert QualityTier.UNKNOWN.value == "unknown"

    def test_quality_tier_from_string(self):
        """Verify QualityTier can be instantiated from string values"""
        assert (
            QualityTier("peer_reviewed_journal")
            == QualityTier.PEER_REVIEWED_JOURNAL
        )
        assert QualityTier("preprint") == QualityTier.PREPRINT


class TestDiscoveryMethod:
    """Test DiscoveryMethod enum"""

    def test_discovery_method_exists(self):
        """Verify DiscoveryMethod enum can be imported"""
        assert DiscoveryMethod is not None

    def test_discovery_method_is_string_enum(self):
        """Verify DiscoveryMethod is a string enum"""
        assert issubclass(DiscoveryMethod, str)

    def test_discovery_method_all_members(self):
        """Verify all expected DiscoveryMethod members exist"""
        expected_members = [
            "FILE_PATH",
            "KEYWORD_SEARCH",
            "BACKWARD_CITATION",
            "FORWARD_CITATION",
            "MANUAL",
            "LITERATURE_REVIEW_MINING",
            "RECOMMENDATION",
            "API",
        ]
        actual_members = [member.name for member in DiscoveryMethod]
        assert set(actual_members) == set(expected_members)
        assert len(actual_members) == 8

    def test_discovery_method_values(self):
        """Verify DiscoveryMethod values are correctly defined"""
        assert DiscoveryMethod.KEYWORD_SEARCH.value == "keyword_search"
        assert DiscoveryMethod.BACKWARD_CITATION.value == "backward_citation"
        assert DiscoveryMethod.FORWARD_CITATION.value == "forward_citation"
        assert DiscoveryMethod.MANUAL.value == "manual"
        assert (
            DiscoveryMethod.LITERATURE_REVIEW_MINING.value
            == "literature_review_mining"
        )
        assert DiscoveryMethod.RECOMMENDATION.value == "recommendation"

    def test_discovery_method_from_string(self):
        """Verify DiscoveryMethod can be instantiated from string values"""
        assert DiscoveryMethod("keyword_search") == DiscoveryMethod.KEYWORD_SEARCH
        assert DiscoveryMethod("manual") == DiscoveryMethod.MANUAL


class TestScreeningDecision:
    """Test ScreeningDecision enum"""

    def test_screening_decision_exists(self):
        """Verify ScreeningDecision enum can be imported"""
        assert ScreeningDecision is not None

    def test_screening_decision_is_string_enum(self):
        """Verify ScreeningDecision is a string enum"""
        assert issubclass(ScreeningDecision, str)

    def test_screening_decision_all_members(self):
        """Verify all expected ScreeningDecision members exist"""
        expected_members = [
            "INCLUDED",
            "INCLUDED_MANUAL",
            "EXCLUDED",
            "EXCLUDED_DUPLICATE",
            "EXCLUDED_MANUAL",
            "PENDING",
            "MANUAL_REVIEW",
            "UNCERTAIN",
        ]
        actual_members = [member.name for member in ScreeningDecision]
        assert set(actual_members) == set(expected_members)
        assert len(actual_members) == 8

    def test_screening_decision_values(self):
        """Verify ScreeningDecision values are correctly defined"""
        assert ScreeningDecision.INCLUDED.value == "included"
        assert ScreeningDecision.INCLUDED_MANUAL.value == "included_manual"
        assert ScreeningDecision.EXCLUDED.value == "excluded"
        assert ScreeningDecision.EXCLUDED_DUPLICATE.value == "excluded_duplicate"
        assert ScreeningDecision.EXCLUDED_MANUAL.value == "excluded_manual"
        assert ScreeningDecision.PENDING.value == "pending"
        assert ScreeningDecision.MANUAL_REVIEW.value == "manual_review"
        assert ScreeningDecision.UNCERTAIN.value == "uncertain"

    def test_screening_decision_from_string(self):
        """Verify ScreeningDecision can be instantiated from string values"""
        assert ScreeningDecision("included") == ScreeningDecision.INCLUDED
        assert ScreeningDecision("excluded") == ScreeningDecision.EXCLUDED
        assert ScreeningDecision("pending") == ScreeningDecision.PENDING


class TestEnumIntegration:
    """Integration tests for all enums"""

    def test_all_enums_are_string_enums(self):
        """Verify all enums are string enums"""
        enums = [PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision]
        for enum_class in enums:
            assert issubclass(enum_class, str), f"{enum_class.__name__} should be str enum"

    def test_enum_values_are_lowercase_with_underscores(self):
        """Verify enum values follow naming convention (lowercase with underscores)"""
        enums = [PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision]
        for enum_class in enums:
            for member in enum_class:
                # Value should be lowercase with underscores
                assert member.value.islower() or member.value.replace("_", "").isdigit(), \
                    f"{enum_class.__name__}.{member.name} value '{member.value}' should be lowercase"
                # Value should only contain lowercase letters, digits, and underscores
                assert all(c.islower() or c == "_" or c.isdigit() for c in member.value), \
                    f"{enum_class.__name__}.{member.name} value '{member.value}' contains invalid characters"

    def test_enum_names_are_uppercase(self):
        """Verify enum member names follow naming convention (UPPERCASE with underscores)"""
        enums = [PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision]
        for enum_class in enums:
            for member in enum_class:
                # Member name should be uppercase
                assert member.name.isupper(), \
                    f"{enum_class.__name__}.{member.name} should be UPPERCASE"
                # Member name should only contain uppercase letters and underscores
                assert all(c.isupper() or c == "_" for c in member.name), \
                    f"{enum_class.__name__}.{member.name} contains invalid characters"

    def test_enum_string_equality(self):
        """Verify enums work correctly with string comparisons"""
        # Direct string comparison
        assert PaperType.JOURNAL_ARTICLE == "journal_article"
        assert StudyType.EMPIRICAL_QUALITATIVE == "empirical_qualitative"
        assert QualityTier.PEER_REVIEWED_JOURNAL == "peer_reviewed_journal"
        assert DiscoveryMethod.KEYWORD_SEARCH == "keyword_search"
        assert ScreeningDecision.INCLUDED == "included"

    def test_enum_invalid_value(self):
        """Verify enums raise ValueError for invalid values"""
        with pytest.raises(ValueError):
            PaperType("invalid_type")

        with pytest.raises(ValueError):
            StudyType("invalid_study")

        with pytest.raises(ValueError):
            QualityTier("invalid_tier")

        with pytest.raises(ValueError):
            DiscoveryMethod("invalid_discovery")

        with pytest.raises(ValueError):
            ScreeningDecision("invalid_decision")


class TestEnumDocumentation:
    """Test enum docstrings and documentation"""

    def test_enums_have_docstrings(self):
        """Verify all enums have docstrings"""
        enums = [PaperType, StudyType, QualityTier, DiscoveryMethod, ScreeningDecision]
        for enum_class in enums:
            assert enum_class.__doc__ is not None, \
                f"{enum_class.__name__} should have a docstring"
            assert len(enum_class.__doc__) > 0, \
                f"{enum_class.__name__} docstring should not be empty"
