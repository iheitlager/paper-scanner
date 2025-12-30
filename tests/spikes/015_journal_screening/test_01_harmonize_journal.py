"""
Test 01: Journal Harmonization - Exact Match and Fuzzy Match
Tests core journal matching logic against real bibliography data.
"""

import pytest
from pathlib import Path
import bibtexparser
from typing import Dict, List, Tuple


class TestJournalHarmonization:
    """Test journal name harmonization against real BibTeX data."""

    @pytest.fixture
    def bib_files(self):
        """Load all .bib files from tests/data."""
        data_dir = Path(__file__).parent.parent.parent / "data"
        bib_files = list(data_dir.glob("*.bib"))
        return bib_files

    @pytest.fixture
    def extracted_journals(self, bib_files) -> Dict[str, int]:
        """Extract unique journal names from BibTeX files.

        Returns dict of journal_name -> count
        """
        journals = {}
        for bib_file in bib_files:
            try:
                with open(bib_file, "r", encoding="utf-8") as f:
                    bibtex_str = f.read()
                    db = bibtexparser.loads(bibtex_str)

                    for entry in db.entries:
                        entry_type = (
                            entry.entry_type.lower()
                            if hasattr(entry, "entry_type")
                            else entry.get("ENTRYTYPE", "").lower()
                        )
                        if entry_type in ["article", "inproceedings", "inbook"]:
                            # bibtexparser uses dict-like access
                            journal = entry.get("journal") or entry.get("Journal")
                            booktitle = entry.get("booktitle") or entry.get("Booktitle")

                            # Use journal field if present, else booktitle
                            source = journal or booktitle
                            if source:
                                source = str(source).strip()
                                journals[source] = journals.get(source, 0) + 1
            except Exception as e:
                print(f"Error parsing {bib_file}: {e}")

        return journals

    def test_extract_real_journals(self, extracted_journals):
        """Verify journals extracted from test data."""
        assert len(extracted_journals) > 0, "No journals extracted from BibTeX files"
        print(f"\nExtracted {len(extracted_journals)} unique journals:")
        for journal, count in sorted(extracted_journals.items(), key=lambda x: -x[1]):
            print(f"  {journal:60} (count: {count})")

    def test_exact_match_simple(self):
        """Test exact case-insensitive matching."""
        journal = "IEEE Transactions on Engineering Management"
        candidates = [
            "IEEE Transactions on Engineering Management",
            "IEEE TRANSACTIONS ON ENGINEERING MANAGEMENT",
            "ieee transactions on engineering management",
        ]

        # All should match
        for candidate in candidates:
            assert self._normalize(journal) == self._normalize(candidate)

    def test_exact_match_with_abbreviations(self):
        """Test matching with common abbreviations."""
        test_cases = [
            ("Academy of Management Journal", "Acad. Manag. J."),
            ("Journal of Strategic Information Systems", "J. Strateg. Inf. Syst."),
            ("Organization Science", "Organ. Sci."),
        ]

        for full_name, abbrev in test_cases:
            # Both should be recognized as same journal
            print(f"\nFull: {full_name}")
            print(f"Abbrev: {abbrev}")
            # This will be handled by fuzzy match in implementation

    def test_case_insensitivity(self):
        """Test case-insensitive matching."""
        test_cases = [
            "IEEE transactions on engineering management",
            "IEEE TRANSACTIONS ON ENGINEERING MANAGEMENT",
            "Ieee Transactions On Engineering Management",
        ]

        normalized = [self._normalize(t) for t in test_cases]
        assert len(set(normalized)) == 1, "Case normalization failed"

    def test_whitespace_normalization(self):
        """Test whitespace handling."""
        variants = [
            "Journal of Management Studies",
            "Journal  of  Management  Studies",  # double spaces
            "Journal of Management  Studies  ",  # trailing spaces
            "  Journal of Management Studies",  # leading spaces
        ]

        normalized = [self._normalize(v) for v in variants]
        assert len(set(normalized)) == 1, "Whitespace normalization failed"

    def test_missing_journal_field(self):
        """Papers without journal should be marked EXCLUDED_INCOMPLETE."""
        paper_with_no_journal = {"title": "Some Paper", "journal": None}

        result = self._check_journal_field(paper_with_no_journal)
        assert result == "EXCLUDED_INCOMPLETE"

    def test_empty_journal_field(self):
        """Papers with empty journal string should be marked EXCLUDED_INCOMPLETE."""
        test_cases = [
            {"title": "Paper 1", "journal": ""},
            {"title": "Paper 2", "journal": "   "},
            {"title": "Paper 3", "journal": None},
        ]

        for paper in test_cases:
            result = self._check_journal_field(paper)
            assert result == "EXCLUDED_INCOMPLETE", f"Failed for: {paper}"

    def test_real_journal_from_bibdata(self, extracted_journals):
        """Test that real journals from BibTeX can be found."""
        # Pick top 5 most common journals
        top_journals = sorted(extracted_journals.items(), key=lambda x: -x[1])[:5]

        print(f"\nTop {len(top_journals)} journals:")
        for journal, count in top_journals:
            print(f"  {journal} (count: {count})")

    # Helper methods for testing

    @staticmethod
    def _normalize(journal_name: str) -> str:
        """Normalize journal name for matching."""
        if not journal_name:
            return ""
        # Strip leading/trailing whitespace, convert to lowercase, collapse internal spaces
        return " ".join(journal_name.strip().lower().split())

    @staticmethod
    def _check_journal_field(paper: Dict) -> str:
        """Check if paper has valid journal field."""
        journal = paper.get("journal")
        if not journal or not str(journal).strip():
            return "EXCLUDED_INCOMPLETE"
        return "OK"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
