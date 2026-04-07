"""
Test 04: PDF-to-Markdown Metadata Extraction

Tests for extracting metadata by converting PDF to markdown-like structure first,
then parsing the structured text.

This approach uses pypdf for text extraction. For better results, consider:
- pymupdf4llm: Better markdown conversion with layout preservation
- marker-pdf: ML-based PDF to markdown conversion

Run with: uv run pytest tests/spikes/020_parsing/test_04_markdown_extractor.py -v -s
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


class MarkdownExtractor:
    """Extract metadata by converting PDF to markdown-like structure."""

    name = "markdown"

    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata from PDF via markdown conversion."""
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))

        # Extract text with page structure
        pages_text = []
        for i, page in enumerate(reader.pages[:5]):  # First 5 pages
            text = page.extract_text() or ""
            pages_text.append(f"--- Page {i+1} ---\n{text}")

        full_text = "\n\n".join(pages_text)

        # Convert to pseudo-markdown structure
        md_text = self._to_markdown_structure(full_text)

        return {
            "title": self._extract_title_from_md(md_text),
            "authors": self._extract_authors_from_md(md_text),
            "year": self._extract_year_from_md(md_text),
            "journal": self._extract_journal_from_md(md_text),
            "doi": self._extract_doi_from_md(md_text),
            "abstract": self._extract_abstract_from_md(md_text),
            "table_of_contents": self._extract_toc_from_md(md_text),
        }

    def _to_markdown_structure(self, text: str) -> str:
        """Convert raw PDF text to markdown-like structure."""
        lines = text.split("\n")
        md_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                md_lines.append("")
                continue

            # Detect potential headers (all caps, short lines)
            if line.isupper() and len(line) < 80:
                md_lines.append(f"## {line}")
            # Detect numbered sections
            elif re.match(r"^\d+\.\s+[A-Z]", line):
                md_lines.append(f"## {line}")
            elif re.match(r"^\d+\.\d+\s+[A-Z]", line):
                md_lines.append(f"### {line}")
            else:
                md_lines.append(line)

        return "\n".join(md_lines)

    def _extract_title_from_md(self, text: str) -> Optional[str]:
        """Extract title from markdown structure."""
        lines = text.split("\n")
        # Title is usually in first few non-empty lines, before authors
        for line in lines[:20]:
            line = line.strip()
            if line and not line.startswith("##") and len(line) > 30:
                # Skip common non-title patterns
                if any(skip in line.lower() for skip in ["journal", "volume", "doi", "http"]):
                    continue
                return line
        return None

    def _extract_authors_from_md(self, text: str) -> List[Dict[str, str]]:
        """Extract authors from markdown structure."""
        authors = []
        # Look for lines with multiple names separated by commas or "and"
        author_pattern = r"([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)"

        # Focus on first page
        first_page = text.split("--- Page 2 ---")[0] if "--- Page 2 ---" in text else text[:3000]

        matches = re.findall(author_pattern, first_page)
        seen = set()
        for name in matches[:10]:
            if name not in seen and len(name) > 5:
                seen.add(name)
                authors.append({"name": name})
        return authors

    def _extract_year_from_md(self, text: str) -> Optional[int]:
        """Extract year from markdown structure."""
        year_pattern = r"\b(199\d|20[0-2]\d)\b"
        matches = re.findall(year_pattern, text[:2000])
        return int(matches[0]) if matches else None

    def _extract_journal_from_md(self, text: str) -> Optional[str]:
        """Extract journal from markdown structure."""
        patterns = [
            r"(?:Published in|Journal:?)\s+([A-Z][^\n]{10,50})",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Journal|Review))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:2000], re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_doi_from_md(self, text: str) -> Optional[str]:
        """Extract DOI from markdown structure."""
        doi_pattern = r"10\.\d{4,}/[^\s]+"
        match = re.search(doi_pattern, text)
        return match.group(0) if match else None

    def _extract_abstract_from_md(self, text: str) -> Optional[str]:
        """Extract abstract from markdown structure."""
        # Look for ABSTRACT header
        abstract_match = re.search(
            r"(?:##\s*)?ABSTRACT[:\s]*\n(.*?)(?=\n##|\n\d+\.\s|Keywords|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if abstract_match:
            abstract = abstract_match.group(1).strip()
            return abstract[:500] if abstract else None
        return None

    def _extract_toc_from_md(self, text: str) -> List[Dict[str, Any]]:
        """Extract table of contents from markdown headers."""
        toc = []
        current_section = None

        # Find markdown headers
        for line in text.split("\n"):
            line = line.strip()

            # Main section (## or numbered like "1. Introduction")
            if line.startswith("## ") or re.match(r"^\d+\.\s+[A-Z]", line):
                if current_section:
                    toc.append(current_section)
                section_name = line.lstrip("# ").strip()
                current_section = {"section": section_name, "subsections": []}

            # Subsection (### or numbered like "1.1 Background")
            elif (line.startswith("### ") or re.match(r"^\d+\.\d+\s+[A-Z]", line)) and current_section:
                subsection_name = line.lstrip("# ").strip()
                current_section["subsections"].append(subsection_name)

        if current_section:
            toc.append(current_section)

        return toc

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


# =============================================================================
# TEST CASES
# =============================================================================


class TestMarkdownExtractor:
    """Tests for markdown-based extraction."""

    def test_extractor_initializes(self):
        """Test extractor can be created."""
        extractor = MarkdownExtractor()
        assert extractor.name == "markdown"

    def test_extracts_from_single_pdf(self, corpus_files):
        """Test extraction from a single PDF."""
        extractor = MarkdownExtractor()
        result = extractor.extract(corpus_files[0])

        assert isinstance(result, dict)
        print(f"\nExtracted from {corpus_files[0].stem[:8]}...")
        print(f"  Title: {result.get('title', 'N/A')[:60] if result.get('title') else 'N/A'}...")
        print(f"  Year: {result.get('year')}")
        print(f"  DOI: {result.get('doi')}")
        print(f"  TOC sections: {len(result.get('table_of_contents', []))}")

    def test_extracts_toc(self, corpus_files):
        """Test TOC extraction from PDFs."""
        extractor = MarkdownExtractor()
        results = extractor.extract_all(corpus_files)

        print("\nTOC extraction results:")
        for result in results:
            toc = result.metadata.get("table_of_contents", [])
            print(f"  {result.paper_id[:8]}...: {len(toc)} sections")
            for section in toc[:3]:
                print(f"    - {section.get('section', 'N/A')[:50]}")

    def test_extracts_all_pdfs(self, corpus_files):
        """Test extraction from all corpus PDFs."""
        extractor = MarkdownExtractor()
        results = extractor.extract_all(corpus_files)

        assert len(results) == len(corpus_files)
        for result in results:
            assert result.success, f"Failed on {result.paper_id}: {result.error}"


class TestMarkdownAccuracy:
    """Tests comparing markdown extraction against ground truth."""

    def test_accuracy_vs_ground_truth(self, corpus_files, ground_truth):
        """Test markdown extraction accuracy against ground truth."""
        extractor = MarkdownExtractor()
        results = extractor.extract_all(corpus_files)

        year_match = 0
        doi_match = 0
        toc_section_count = 0
        expected_section_count = 0
        total = 0

        for result in results:
            expected = ground_truth.get(result.paper_id, {})
            if not expected:
                continue

            total += 1
            extracted = result.metadata

            # Year comparison
            if extracted.get("year") == expected.get("year"):
                year_match += 1

            # DOI comparison (partial match OK)
            ext_doi = extracted.get("doi") or ""
            exp_doi = expected.get("doi") or ""
            if exp_doi and ext_doi and exp_doi in ext_doi:
                doi_match += 1

            # TOC comparison (count sections)
            ext_toc = extracted.get("table_of_contents", [])
            exp_toc = expected.get("table_of_contents", [])
            toc_section_count += len(ext_toc)
            expected_section_count += len(exp_toc)

        if total > 0:
            print(f"\nMarkdown extraction accuracy:")
            print(f"  Year: {year_match}/{total} ({year_match/total:.0%})")
            print(f"  DOI: {doi_match}/{total} ({doi_match/total:.0%})")
            print(f"  TOC sections found: {toc_section_count} vs {expected_section_count} expected")


class TestPyMuPDF4LLMAvailability:
    """Test for better markdown extraction library."""

    def test_pymupdf4llm_not_installed(self):
        """Document that pymupdf4llm is not installed."""
        try:
            import pymupdf4llm
            pytest.skip("pymupdf4llm is installed - can use better extraction")
        except ImportError:
            print("\npymupdf4llm not installed.")
            print("For better PDF-to-markdown conversion, install with:")
            print("  uv add --group dev pymupdf4llm")
            print("\nThis would provide:")
            print("  - Better layout preservation")
            print("  - Table extraction")
            print("  - Image handling")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
