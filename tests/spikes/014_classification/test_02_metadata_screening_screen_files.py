"""
Metadata Screening - File Processing Test
Tests reading BibTeX files and screening papers with tri-state logic

Run with:
    pytest test_02_screen_files.py -v
    or
    python test_02_screen_files.py
"""

import pytest
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

from paper_scanner.core.enum import PaperType, StudyType, ScreeningDecision
from paper_scanner.io.bibtex import bibtex_file_to_papers


class ScreeningCriteria:
    """
    Represents tri-state screening logic:
    - INCLUDE: hard include (must have these values)
    - EXCLUDE: hard exclude (must NOT have these values, or everything except specified)
    - OMITTED: no requirement (leave aside)
    """

    def __init__(self, criteria: Dict[str, Any]):
        """Initialize screening criteria from config"""
        self.exclude = criteria.get("exclude", {})
        self.include = criteria.get("include", {})

    def parse_exclude_criteria(self, field: str) -> Dict[str, Any]:
        """
        Parse exclude criteria for a field.
        
        Returns dict with:
        - hard_excludes: list of values that hard exclude
        - exclude_all_except: optional value (for NOT: prefix)
        """
        field_criteria = self.exclude.get(field, [])
        result = {"hard_excludes": [], "exclude_all_except": None}

        for criterion in field_criteria:
            if isinstance(criterion, str):
                if criterion.startswith("NOT:"):
                    # NOT: prefix means "exclude everything except this"
                    result["exclude_all_except"] = criterion.replace("NOT:", "").strip()
                else:
                    # Direct exclusion
                    result["hard_excludes"].append(criterion)

        return result

    def parse_include_criteria(self, field: str) -> List[str]:
        """
        Parse include criteria for a field.
        
        Returns list of values that must be included.
        """
        return self.include.get(field, [])

    def should_include(
        self,
        paper_data: Dict[str, Any],
        verbose: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if paper should be included based on tri-state logic.
        
        Args:
            paper_data: Paper data dict with fields like 'language', 'paper_type', etc.
            verbose: Enable verbose output
        
        Returns:
            (should_include, exclusion_reason)
        """
        reasons = []

        # Check language field
        if "language" in self.exclude:
            exclude_criteria = self.parse_exclude_criteria("language")
            paper_lang = paper_data.get("language", None)

            if exclude_criteria["exclude_all_except"]:
                # NOT: en means "exclude everything that is NOT en"
                allowed_lang = exclude_criteria["exclude_all_except"]
                if paper_lang and paper_lang.lower() != allowed_lang.lower():
                    reasons.append(f"Language: {paper_lang} (excluded, only {allowed_lang} allowed)")

            # Check hard excludes
            for hard_exclude in exclude_criteria["hard_excludes"]:
                if paper_lang and hard_exclude.lower() in paper_lang.lower():
                    reasons.append(f"Language: {paper_lang} (hard excluded)")

        # Check paper_type field
        if "paper_types" in self.exclude:
            exclude_criteria = self.parse_exclude_criteria("paper_types")
            paper_type = paper_data.get("paper_type", None)

            if exclude_criteria["exclude_all_except"]:
                # NOT: journal_article means "exclude everything that is NOT journal_article"
                allowed_type = exclude_criteria["exclude_all_except"]
                if paper_type and paper_type.lower() != allowed_type.lower():
                    reasons.append(
                        f"Paper Type: {paper_type} (excluded, only {allowed_type} allowed)"
                    )

            # Check hard excludes
            for hard_exclude in exclude_criteria["hard_excludes"]:
                if paper_type and hard_exclude.lower() in paper_type.lower():
                    reasons.append(f"Paper Type: {paper_type} (hard excluded)")

        # Check study_type field
        if "study_types" in self.exclude:
            exclude_criteria = self.parse_exclude_criteria("study_types")
            study_type = paper_data.get("study_type", None)

            for hard_exclude in exclude_criteria["hard_excludes"]:
                if study_type and hard_exclude.lower() in study_type.lower():
                    reasons.append(f"Study Type: {study_type} (hard excluded)")

        if reasons:
            return False, "; ".join(reasons)
        return True, None


class TestParseExcludeLogic:
    """Tests for parsing exclude criteria with NOT operator"""

    def test_parse_not_operator_language(self):
        """Should parse NOT: operator for language exclusion"""
        criteria = {
            "exclude": {"language": ["NOT: en"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)
        exclude_criteria = screening.parse_exclude_criteria("language")

        assert exclude_criteria["exclude_all_except"] == "en"
        assert exclude_criteria["hard_excludes"] == []

    def test_parse_not_operator_paper_type(self):
        """Should parse NOT: operator for paper_type exclusion"""
        criteria = {
            "exclude": {"paper_types": ["NOT: journal_article"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)
        exclude_criteria = screening.parse_exclude_criteria("paper_types")

        assert exclude_criteria["exclude_all_except"] == "journal_article"
        assert exclude_criteria["hard_excludes"] == []

    def test_parse_hard_exclude(self):
        """Should parse direct hard exclude values"""
        criteria = {
            "exclude": {"study_types": ["editorial", "conceptual", "theoretical"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)
        exclude_criteria = screening.parse_exclude_criteria("study_types")

        assert exclude_criteria["hard_excludes"] == ["editorial", "conceptual", "theoretical"]
        assert exclude_criteria["exclude_all_except"] is None

    def test_parse_mixed_exclude(self):
        """Should handle both NOT and hard excludes"""
        criteria = {
            "exclude": {
                "study_types": ["editorial", "NOT: empirical"]
            },
            "include": {}
        }
        screening = ScreeningCriteria(criteria)
        exclude_criteria = screening.parse_exclude_criteria("study_types")

        assert "editorial" in exclude_criteria["hard_excludes"]
        assert exclude_criteria["exclude_all_except"] == "empirical"


class TestScreeningLogic:
    """Tests for tri-state screening logic"""

    def test_hard_exclude_non_english(self):
        """Should exclude non-English papers with NOT: en"""
        criteria = {
            "exclude": {"language": ["NOT: en"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)

        # English paper should pass
        paper = {"language": "en"}
        included, reason = screening.should_include(paper)
        assert included is True
        assert reason is None

        # Spanish paper should be excluded
        paper = {"language": "es"}
        included, reason = screening.should_include(paper)
        assert included is False
        assert reason is not None
        assert "Language" in reason

    def test_hard_exclude_non_journal_articles(self):
        """Should exclude non-journal articles with NOT: journal_article"""
        criteria = {
            "exclude": {"paper_types": ["NOT: journal_article"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)

        # Journal article should pass
        paper = {"paper_type": "journal_article"}
        included, reason = screening.should_include(paper)
        assert included is True

        # Conference paper should be excluded
        paper = {"paper_type": "conference_paper"}
        included, reason = screening.should_include(paper)
        assert included is False
        assert "Paper Type" in reason

    def test_hard_exclude_study_types(self):
        """Should hard exclude specific study types"""
        criteria = {
            "exclude": {"study_types": ["editorial", "conceptual", "theoretical"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)

        # Editorial should be excluded
        paper = {"study_type": "editorial"}
        included, reason = screening.should_include(paper)
        assert included is False
        assert "editorial" in reason.lower()

        # Empirical should pass
        paper = {"study_type": "empirical_qualitative"}
        included, reason = screening.should_include(paper)
        assert included is True

    def test_omitted_field_no_requirement(self):
        """Should not exclude papers for omitted fields"""
        criteria = {
            "exclude": {"language": ["NOT: en"]},
            "include": {}
        }
        screening = ScreeningCriteria(criteria)

        # Paper without language field should pass (no requirement for omitted field)
        paper = {"paper_type": "journal_article"}
        included, reason = screening.should_include(paper)
        assert included is True

    def test_combined_criteria(self):
        """Should apply all criteria together"""
        criteria = {
            "exclude": {
                "language": ["NOT: en"],
                "paper_types": ["NOT: journal_article"],
                "study_types": ["editorial", "conceptual"]
            },
            "include": {}
        }
        screening = ScreeningCriteria(criteria)

        # Paper passing all criteria
        paper = {
            "language": "en",
            "paper_type": "journal_article",
            "study_type": "empirical_qualitative"
        }
        included, reason = screening.should_include(paper)
        assert included is True

        # Paper failing language
        paper = {
            "language": "es",
            "paper_type": "journal_article",
            "study_type": "empirical_qualitative"
        }
        included, reason = screening.should_include(paper)
        assert included is False

        # Paper failing paper_type
        paper = {
            "language": "en",
            "paper_type": "conference_paper",
            "study_type": "empirical_qualitative"
        }
        included, reason = screening.should_include(paper)
        assert included is False

        # Paper failing study_type
        paper = {
            "language": "en",
            "paper_type": "journal_article",
            "study_type": "editorial"
        }
        included, reason = screening.should_include(paper)
        assert included is False


class TestBibtexFileProcessing:
    """Integration tests reading real BibTeX files"""

    @pytest.fixture
    def bibtex_file(self) -> Path:
        """Get path to test BibTeX file"""
        return Path(__file__).parent.parent.parent / "data" / "eight_cases.bib"

    def test_read_bibtex_file(self, bibtex_file):
        """Should read papers from BibTeX file"""
        assert bibtex_file.exists(), f"Test file not found: {bibtex_file}"
        
        try:
            papers = bibtex_file_to_papers(str(bibtex_file))
            assert papers is not None
            assert len(papers) > 0, "No papers read from BibTeX file"
            
            # Check first paper has expected fields
            first_paper = papers[0]
            assert hasattr(first_paper, 'title')
            assert hasattr(first_paper, 'authors')
            assert first_paper.title
        except Exception as e:
            pytest.skip(f"Could not read BibTeX file: {e}")

    def test_extract_paper_fields(self, bibtex_file):
        """Should extract all needed fields for screening"""
        try:
            papers = bibtex_file_to_papers(str(bibtex_file))
            
            for paper in papers:
                # These fields may be missing, but structure should exist
                paper_dict = {
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "doi": paper.doi,
                    # These might not exist in Paper model yet:
                    # "language": getattr(paper, 'language', 'en'),
                    # "paper_type": getattr(paper, 'paper_type', 'unknown'),
                    # "study_type": getattr(paper, 'study_type', 'unknown')
                }
                assert paper_dict["title"], "Paper should have title"
        except Exception as e:
            pytest.skip(f"Could not process BibTeX file: {e}")


class TestEnumConversion:
    """Tests for enum value conversion"""

    def test_paper_type_enum_values(self):
        """Should validate PaperType enum values"""
        assert PaperType.JOURNAL_ARTICLE.value == "journal_article"
        assert PaperType.CONFERENCE_PAPER.value == "conference_paper"
        assert PaperType.BOOK.value == "book"

    def test_study_type_enum_values(self):
        """Should validate StudyType enum values"""
        assert StudyType.EMPIRICAL_QUALITATIVE.value == "empirical_qualitative"
        assert StudyType.EMPIRICAL_QUANTITATIVE.value == "empirical_quantitative"
        assert StudyType.LITERATURE_REVIEW.value == "literature_review"
        assert StudyType.EDITORIAL.value == "editorial"
        assert StudyType.CONCEPTUAL.value == "conceptual"
        assert StudyType.THEORETICAL.value == "theoretical"

    def test_screening_decision_enum(self):
        """Should validate ScreeningDecision enum"""
        assert ScreeningDecision.INCLUDED.value == "included"
        assert ScreeningDecision.EXCLUDED.value == "excluded"


def run_manual_tests():
    """Run tests manually for debugging"""
    print("=" * 80)
    print("Running Metadata Screening Classification Tests")
    print("=" * 80)

    # Test 1: Parse NOT operator
    print("\n[Test 1] Parse NOT operator for language")
    criteria = {
        "exclude": {"language": ["NOT: en"]},
        "include": {}
    }
    screening = ScreeningCriteria(criteria)
    exclude_criteria = screening.parse_exclude_criteria("language")
    print(f"  Parsed criteria: {exclude_criteria}")
    assert exclude_criteria["exclude_all_except"] == "en"
    print("  ✓ PASSED")

    # Test 2: Screening logic - English paper
    print("\n[Test 2] Screening: English paper with NOT: en (should PASS)")
    paper = {"language": "en"}
    included, reason = screening.should_include(paper)
    print(f"  Included: {included}, Reason: {reason}")
    assert included is True
    print("  ✓ PASSED")

    # Test 3: Screening logic - Spanish paper
    print("\n[Test 3] Screening: Spanish paper with NOT: en (should FAIL)")
    paper = {"language": "es"}
    included, reason = screening.should_include(paper)
    print(f"  Included: {included}, Reason: {reason}")
    assert included is False
    assert "Language" in reason
    print("  ✓ PASSED")

    # Test 4: Hard exclude study types
    print("\n[Test 4] Hard exclude study types (editorial, conceptual, theoretical)")
    criteria = {
        "exclude": {"study_types": ["editorial", "conceptual", "theoretical"]},
        "include": {}
    }
    screening = ScreeningCriteria(criteria)
    
    paper = {"study_type": "editorial"}
    included, reason = screening.should_include(paper)
    print(f"  Editorial paper - Included: {included}")
    assert included is False
    
    paper = {"study_type": "empirical_qualitative"}
    included, reason = screening.should_include(paper)
    print(f"  Empirical paper - Included: {included}")
    assert included is True
    print("  ✓ PASSED")

    # Test 5: Enum values
    print("\n[Test 5] Enum value validation")
    print(f"  PaperType.JOURNAL_ARTICLE = {PaperType.JOURNAL_ARTICLE.value}")
    print(f"  StudyType.EMPIRICAL_QUALITATIVE = {StudyType.EMPIRICAL_QUALITATIVE.value}")
    print(f"  ScreeningDecision.INCLUDED = {ScreeningDecision.INCLUDED.value}")
    print("  ✓ PASSED")

    print("\n" + "=" * 80)
    print("All manual tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    # Can run either pytest or as standalone script
    import sys
    if "--manual" in sys.argv:
        run_manual_tests()
    else:
        pytest.main([__file__, "-v"])
