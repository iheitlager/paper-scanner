"""
Test 01: Regex-based Metadata Extraction

Tests for extracting metadata from PDFs using PyPDF + regex patterns.
This approach is free, fast, and local but fragile to format variations.

Run with: uv run pytest tests/spikes/020_parsing/test_01_regex_extractor.py -v
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Mark entire module as spike test
pytestmark = pytest.mark.spike


@dataclass
class ExtractionResult:
    """Result from a metadata extraction attempt."""

    paper_id: str
    extractor: str
    metadata: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0


class RegexExtractor:
    """Extract metadata using PyPDF text extraction + regex patterns."""

    name = "regex"

    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata from a single PDF."""
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))

        # Extract text from first 3 pages (where metadata usually is)
        text = ""
        for page in reader.pages[:3]:
            text += page.extract_text() or ""

        return {
            "title": self._extract_title(text),
            "authors": self._extract_authors(text),
            "year": self._extract_year(text),
            "journal": self._extract_journal(text),
            "doi": self._extract_doi(text),
            "volume": self._extract_volume(text),
            "pages": self._extract_pages(text),
        }

    def extract_all(self, pdf_files: List[Path]) -> List[ExtractionResult]:
        """Extract metadata from multiple PDF files."""
        import time

        results = []
        for pdf_path in pdf_files:
            paper_id = pdf_path.stem
            start_time = time.time()
            try:
                metadata = self.extract(pdf_path)
                duration = time.time() - start_time
                results.append(
                    ExtractionResult(
                        paper_id=paper_id,
                        extractor=self.name,
                        metadata=metadata,
                        duration_seconds=duration,
                    )
                )
            except Exception as e:
                duration = time.time() - start_time
                results.append(
                    ExtractionResult(
                        paper_id=paper_id,
                        extractor=self.name,
                        metadata={},
                        success=False,
                        error=str(e),
                        duration_seconds=duration,
                    )
                )
        return results

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title - usually the first prominent text."""
        lines = text.strip().split("\n")
        for line in lines[:10]:
            line = line.strip()
            # Title is typically longer than 20 chars and not a URL
            if len(line) > 20 and not line.startswith("http"):
                return line
        return None

    def _extract_authors(self, text: str) -> List[Dict[str, str]]:
        """Extract author names using common patterns."""
        authors = []
        # Pattern: "Firstname Lastname" or "F. Lastname"
        author_pattern = r"([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)"
        matches = re.findall(author_pattern, text[:2000])
        seen = set()
        for name in matches[:10]:
            if name not in seen and len(name) > 5:
                seen.add(name)
                authors.append({"name": name})
        return authors

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract publication year (1990-2029)."""
        year_pattern = r"\b(199\d|20[0-2]\d)\b"
        matches = re.findall(year_pattern, text)
        return int(matches[0]) if matches else None

    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal name using common indicators."""
        journal_patterns = [
            r"(?:Published in|Journal of|Proceedings of)\s+([A-Z][^\n]{10,50})",
            r"([A-Z][a-z]+\s+(?:Journal|Review|Proceedings|Letters)(?:\s+of\s+[A-Z][a-z]+)?)",
        ]
        for pattern in journal_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI using standard pattern."""
        doi_pattern = r"10\.\d{4,}/[^\s]+"
        match = re.search(doi_pattern, text)
        return match.group(0) if match else None

    def _extract_volume(self, text: str) -> Optional[int]:
        """Extract volume number."""
        vol_pattern = r"[Vv]ol(?:ume)?\.?\s*(\d+)"
        match = re.search(vol_pattern, text)
        return int(match.group(1)) if match else None

    def _extract_pages(self, text: str) -> Optional[str]:
        """Extract page range."""
        pages_pattern = r"(?:pp?\.?\s*)?(\d+)\s*[-–]\s*(\d+)"
        match = re.search(pages_pattern, text)
        return f"{match.group(1)}-{match.group(2)}" if match else None


# =============================================================================
# TEST CASES
# =============================================================================


class TestRegexExtractor:
    """Tests for regex-based metadata extraction."""

    def test_extractor_initializes(self):
        """Test extractor can be created."""
        extractor = RegexExtractor()
        assert extractor.name == "regex"

    def test_extracts_from_single_pdf(self, corpus_files):
        """Test extraction from a single PDF."""
        extractor = RegexExtractor()
        result = extractor.extract(corpus_files[0])
        assert isinstance(result, dict)
        assert "title" in result
        assert "authors" in result
        assert "year" in result

    def test_extracts_from_all_pdfs(self, corpus_files):
        """Test extraction from all corpus PDFs."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)
        assert len(results) == len(corpus_files)
        for result in results:
            assert result.success, f"Failed on {result.paper_id}: {result.error}"

    def test_extracts_year(self, corpus_files):
        """Test year extraction from all PDFs."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)
        years_found = sum(1 for r in results if r.metadata.get("year") is not None)
        assert years_found > 0, "Should extract at least one year"
        # Print for debugging
        for r in results:
            print(f"  {r.paper_id[:8]}...: year={r.metadata.get('year')}")

    def test_extracts_doi(self, corpus_files):
        """Test DOI extraction."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)
        dois_found = sum(1 for r in results if r.metadata.get("doi") is not None)
        # DOIs should be in most academic papers
        assert dois_found >= len(corpus_files) // 2, f"Only found {dois_found} DOIs"
        for r in results:
            print(f"  {r.paper_id[:8]}...: doi={r.metadata.get('doi')}")

    def test_extracts_title(self, corpus_files):
        """Test title extraction."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)
        titles_found = sum(1 for r in results if r.metadata.get("title") is not None)
        assert titles_found > 0, "Should extract at least one title"


class TestRegexAccuracy:
    """Tests comparing regex extraction against ground truth."""

    def test_year_accuracy(self, corpus_files, ground_truth):
        """Test year extraction accuracy against ground truth."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)

        correct = 0
        total = 0
        for result in results:
            expected = ground_truth.get(result.paper_id, {})
            if expected and expected.get("year"):
                total += 1
                if result.metadata.get("year") == expected.get("year"):
                    correct += 1
                else:
                    print(f"  Mismatch {result.paper_id[:8]}: "
                          f"got {result.metadata.get('year')}, expected {expected.get('year')}")

        if total > 0:
            accuracy = correct / total
            print(f"\nYear accuracy: {accuracy:.0%} ({correct}/{total})")
            # Year should be relatively easy to extract
            assert accuracy >= 0.6, f"Year accuracy too low: {accuracy:.0%}"

    def test_doi_accuracy(self, corpus_files, ground_truth):
        """Test DOI extraction accuracy against ground truth."""
        extractor = RegexExtractor()
        results = extractor.extract_all(corpus_files)

        correct = 0
        total = 0
        for result in results:
            expected = ground_truth.get(result.paper_id, {})
            if expected and expected.get("doi"):
                total += 1
                extracted_doi = result.metadata.get("doi", "")
                expected_doi = expected.get("doi", "")
                # DOIs might have trailing characters, check if expected is in extracted
                if expected_doi and extracted_doi and expected_doi in extracted_doi:
                    correct += 1
                else:
                    print(f"  Mismatch {result.paper_id[:8]}: "
                          f"got '{extracted_doi}', expected '{expected_doi}'")

        if total > 0:
            accuracy = correct / total
            print(f"\nDOI accuracy: {accuracy:.0%} ({correct}/{total})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
