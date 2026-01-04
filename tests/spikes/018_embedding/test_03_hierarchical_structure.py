#!/usr/bin/env python3
"""
Spike 018: Test 3 - Hierarchical Structure Detection (Text-Based PDFs)
========================================================================

Compare two text-based document structure detection techniques on academic PDFs:
1. PyMuPDF (fitz) - Font-based heading detection via font size/weight changes
2. pdfplumber - Positional text extraction with bounding box inference

This test focuses on **born-digital PDFs with selectable text**—fast, CPU-friendly,
no OCR or vision transformers needed.

This test:
1. Loads 2 papers with PDF files
2. Extracts text with font metadata (PyMuPDF) or positional data (pdfplumber)
3. Uses sections.py to detect and canonicalize sections
4. Identifies and removes citations (report chars/tokens dropped)
5. Compares output quality and structure accuracy

Usage:
    python test_03_hierarchical_structure.py
    python test_03_hierarchical_structure.py --technique pymupdf
    python test_03_hierarchical_structure.py --technique pdfplumber
    python test_03_hierarchical_structure.py --verbose

Requires:
    PyMuPDF (fitz)      # For font-aware text extraction
    pdfplumber          # For positional text extraction
    tiktoken           # For token counting

Note: Structure detection is now delegated to sections.py module which provides:
    - detect_sections() - raw section detection via 70+ regex patterns
    - normalize_section_name() - maps to canonical types
    - group_sections_hierarchically() - groups by canonical section
    - validate_paper_structure() - validates coverage quality
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tiktoken

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from paper_scanner.core.models import Paper
from paper_scanner.tools.embedding.sections import (
    detect_sections,
    group_sections_hierarchically,
    validate_paper_structure,
)

# Setup logging - suppress debug logging from external libraries
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# Suppress debug logging from external libraries
logging.getLogger('pdfplumber').setLevel(logging.WARNING)
logging.getLogger('fitz').setLevel(logging.WARNING)
logging.getLogger('pymupdf').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)


class CitationRemover:
    """Detect and remove citations from extracted text."""

    # Common citation patterns
    CITATION_PATTERNS = [
        # [Author, Year] or [Author et al., Year]
        r'\[\s*[A-Z][a-z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\]',
        # (Author, Year) or (Author et al., Year)
        r'\(\s*[A-Z][a-z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\)',
        # Author (Year) - common in-text format
        r'[A-Z][a-z]+\s+\(\d{4}\)',
        # References section headers
        r'^\s*(References|Bibliography|Works Cited|Citations)\s*$',
        # Citation blocks (multiple lines of citations)
        r'\[[\d\s,]+\]',
    ]

    def __init__(self):
        """Initialize citation remover."""
        self.citation_blocks = []

    def remove_citations(self, text: str) -> Tuple[str, Dict]:
        """Remove citations from text and track removal statistics.
        
        Args:
            text: Input text with citations
            
        Returns:
            Tuple of (cleaned_text, stats_dict)
        """
        original_length = len(text)
        original_tokens = self._count_tokens(text)
        
        cleaned = text
        removed_chars = 0
        removed_tokens = 0
        matches_found = 0

        # Apply each pattern
        for pattern in self.CITATION_PATTERNS:
            matches = re.finditer(pattern, cleaned, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                citation_text = match.group(0)
                citation_chars = len(citation_text)
                citation_tokens = self._count_tokens(citation_text)
                
                self.citation_blocks.append({
                    'text': citation_text[:50] + ('...' if len(citation_text) > 50 else ''),
                    'chars': citation_chars,
                    'tokens': citation_tokens,
                })
                
                removed_chars += citation_chars
                removed_tokens += citation_tokens
                matches_found += 1

        # Remove all citations
        for pattern in self.CITATION_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)

        # Clean up extra whitespace
        cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
        cleaned = cleaned.strip()

        final_chars = len(cleaned)
        final_tokens = self._count_tokens(cleaned)

        return cleaned, {
            'original_chars': original_length,
            'original_tokens': original_tokens,
            'final_chars': final_chars,
            'final_tokens': final_tokens,
            'removed_chars': removed_chars,
            'removed_tokens': removed_tokens,
            'removed_percentage_chars': round(100 * removed_chars / original_length, 2) if original_length > 0 else 0,
            'removed_percentage_tokens': round(100 * removed_tokens / original_tokens, 2) if original_tokens > 0 else 0,
            'citations_found': matches_found,
        }

    @staticmethod
    def _count_tokens(text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback: rough estimate (1 token ≈ 4 chars)
            return len(text) // 4

    def get_citation_summary(self) -> str:
        """Get summary of removed citations."""
        if not self.citation_blocks:
            return "No citations removed"
        
        summary = f"Removed {len(self.citation_blocks)} citations:\n"
        for i, citation in enumerate(self.citation_blocks[:5], 1):
            summary += f"  {i}. {citation['text']} ({citation['chars']} chars, {citation['tokens']} tokens)\n"
        
        if len(self.citation_blocks) > 5:
            summary += f"  ... and {len(self.citation_blocks) - 5} more\n"
        
        return summary


class PyMuPDFStructureExtractor:
    """Extract text using PyMuPDF (font-aware extraction)."""

    def __init__(self):
        """Initialize PyMuPDF extractor."""
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if PyMuPDF is available."""
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    def extract(self, pdf_path: str) -> Optional[Dict]:
        """Extract text from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with text, detected sections (raw), canonical sections, and statistics
        """
        if not self.available:
            return None

        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            full_text = self._extract_text(doc)
            
            # Use sections.py for detection and canonicalization
            raw_sections = detect_sections(full_text)
            hierarchical = group_sections_hierarchically(raw_sections)
            coverage = validate_paper_structure(hierarchical)
            
            return {
                'tool': 'PyMuPDF',
                'pdf_path': pdf_path,
                'text': full_text,
                'raw_sections': raw_sections,
                'hierarchical_sections': hierarchical,
                'coverage': coverage,
                'canonical_sections_found': len([s for s in coverage['found']]),
            }
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            return None

    @staticmethod
    def _extract_text(doc) -> str:
        """Extract text from PDF.
        
        Args:
            doc: PyMuPDF document
            
        Returns:
            Combined text from all pages
        """
        full_text = ""
        total_pages = len(doc)
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            if text:
                full_text += text + "\n\n"

        return full_text


class PDFPlumberStructureExtractor:
    """Extract text using pdfplumber (positional extraction)."""

    def __init__(self):
        """Initialize pdfplumber extractor."""
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if pdfplumber is available."""
        try:
            import pdfplumber
            return True
        except ImportError:
            return False

    def extract(self, pdf_path: str) -> Optional[Dict]:
        """Extract text from PDF using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with text, detected sections (raw), canonical sections, and statistics
        """
        if not self.available:
            return None

        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                text = self._extract_text(pdf)
                
                # Use sections.py for detection and canonicalization
                raw_sections = detect_sections(text)
                hierarchical = group_sections_hierarchically(raw_sections)
                coverage = validate_paper_structure(hierarchical)
                
                return {
                    'tool': 'pdfplumber',
                    'pdf_path': pdf_path,
                    'text': text,
                    'raw_sections': raw_sections,
                    'hierarchical_sections': hierarchical,
                    'coverage': coverage,
                    'canonical_sections_found': len([s for s in coverage['found']]),
                }
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return None

    @staticmethod
    def _extract_text(pdf) -> str:
        """Extract text from all pages.
        
        Args:
            pdf: pdfplumber PDF object
            
        Returns:
            Combined text from all pages
        """
        full_text = ""
        total_pages = len(pdf.pages)
        
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n\n"
        
        return full_text


class HierarchicalStructureTest:
    """Test hierarchical structure extraction with citation removal."""

    def __init__(self, technique: str = 'both', verbose: bool = False):
        """Initialize test.
        
        Args:
            technique: 'pymupdf', 'pdfplumber', or 'both'
            verbose: Enable verbose logging
        """
        self.technique = technique
        self.verbose = verbose
        self.pymupdf = PyMuPDFStructureExtractor()
        self.pdfplumber = PDFPlumberStructureExtractor()
        self.citation_remover = CitationRemover()
        self.all_results = {}  # Track results for final comparison

    def test_papers(self, papers: List[Paper]) -> None:
        """Test structure extraction on papers.
        
        Args:
            papers: List of Paper objects with PDFs
        """
        papers_with_pdfs = [
            p for p in papers
            if p.pdf_info and p.pdf_info.file_path and Path(p.pdf_info.file_path).exists()
        ]

        if not papers_with_pdfs:
            logger.error("✗ No papers with valid PDFs found")
            return

        # Test first 2 papers
        test_papers = papers_with_pdfs[:2]
        
        print(f"\n{'='*80}")
        print(f"HIERARCHICAL STRUCTURE EXTRACTION TEST")
        print(f"{'='*80}")
        print(f"\nPapers to process: {len(test_papers)}")
        print(f"Extraction techniques: {self.technique.upper()}")
        print(f"\n{'-'*80}\n")

        for idx, paper in enumerate(test_papers, 1):
            if self.verbose:
                logger.debug(f"Scanning paper [{idx}/{len(test_papers)}]: {paper.cite_key}")
            else:
                logger.info(f"[{idx}/{len(test_papers)}] Processing: {paper.cite_key}")
            self.test_single_paper(paper)

    def test_single_paper(self, paper: Paper) -> None:
        """Test structure extraction on a single paper.
        
        Args:
            paper: Paper object with PDF
        """
        pdf_path = paper.pdf_info.file_path
        results = {}

        # Test PyMuPDF if requested
        if self.technique in ['pymupdf', 'both']:
            pymupdf_result = self.pymupdf.extract(pdf_path)
            if pymupdf_result:
                results['pymupdf'] = self._process_result(pymupdf_result)

        # Test pdfplumber if requested
        if self.technique in ['pdfplumber', 'both']:
            pdfplumber_result = self.pdfplumber.extract(pdf_path)
            if pdfplumber_result:
                results['pdfplumber'] = self._process_result(pdfplumber_result)

        # Store results for final comparison
        self.all_results[paper.cite_key] = results
        
        # Print comparison
        self._print_comparison(paper, results)

    def _process_result(self, result: Dict) -> Dict:
        """Process extraction result: remove citations and gather stats.
        
        Args:
            result: Extraction result with text
            
        Returns:
            Processed result with citation statistics and canonical sections
        """
        text = result.get('text', '')
        
        # Remove citations
        cleaned_text, citation_stats = self.citation_remover.remove_citations(text)
        
        return {
            'tool': result['tool'],
            'original_text_chars': len(text),
            'cleaned_text_chars': len(cleaned_text),
            'raw_sections_detected': len(result.get('raw_sections', [])),
            'canonical_sections_found': result.get('canonical_sections_found', 0),
            'canonical_coverage': result.get('coverage', {}).get('coverage_percentage', 0),
            'canonical_sections_list': result.get('coverage', {}).get('found', []),
            'citation_stats': citation_stats,
        }

    def _print_comparison(self, paper: Paper, results: Dict) -> None:
        """Print comparison of extraction techniques with structure overview.
        
        Args:
            paper: Paper object being analyzed
            results: Dict of results keyed by technique
        """
        if not results:
            logger.warning(f"✗ No extraction results for {paper.cite_key}")
            return

        print(f"\nPaper: {paper.cite_key}")
        print(f"Title: {paper.title}")
        print(f"PDF: {Path(paper.pdf_info.file_path).name}")
        print(f"\n{'-'*80}\n")

        for tool_name, result in results.items():
            print(f"{tool_name.upper()}")
            print(f"  {'─' * 76}\n")
            
            print(f"  Text Statistics:")
            print(f"    • Original size: {result['original_text_chars']:,} chars")
            print(f"    • After citation removal: {result['cleaned_text_chars']:,} chars")
            
            print(f"\n  Raw Section Detection:")
            print(f"    • Raw sections found: {result['raw_sections_detected']}")
            
            print(f"\n  Canonical Structure:")
            print(f"    • Coverage: {result['canonical_coverage']:.1f}% ({result['canonical_sections_found']}/10 sections)")
            if result['canonical_sections_list']:
                print(f"    • Found: {', '.join(result['canonical_sections_list'])}")
                missing = [s for s in ['title', 'abstract', 'keywords', 'introduction', 'background', 'research_question', 'literature', 'methods', 'findings', 'conclusion'] if s not in result['canonical_sections_list']]
                if missing:
                    print(f"    • Missing: {', '.join(missing)}")
            
            cs = result['citation_stats']
            print(f"\n  Citation Removal:")
            print(f"    • Citations found: {cs['citations_found']}")
            print(f"    • Chars removed: {cs['removed_chars']:,} ({cs['removed_percentage_chars']}%)")
            print(f"    • Tokens removed: {cs['removed_tokens']:,} ({cs['removed_percentage_tokens']}%)")
            print(f"    • Remaining tokens: {cs['final_tokens']:,}")
            
            print(f"\n")

    def print_conclusion(self) -> None:
        """Print final conclusion comparing extraction methods."""
        if not self.all_results or len(self.all_results) == 0:
            return
        
        if self.technique != 'both':
            return  # Only show conclusion when comparing both
        
        # Aggregate metrics across all papers
        pymupdf_scores = {'coverage': [], 'sections': [], 'citations': []}
        pdfplumber_scores = {'coverage': [], 'sections': [], 'citations': []}
        
        for paper_key, results in self.all_results.items():
            if 'pymupdf' in results:
                pymupdf_scores['coverage'].append(results['pymupdf']['canonical_coverage'])
                pymupdf_scores['sections'].append(results['pymupdf']['canonical_sections_found'])
                pymupdf_scores['citations'].append(results['pymupdf']['citation_stats']['citations_found'])
            
            if 'pdfplumber' in results:
                pdfplumber_scores['coverage'].append(results['pdfplumber']['canonical_coverage'])
                pdfplumber_scores['sections'].append(results['pdfplumber']['canonical_sections_found'])
                pdfplumber_scores['citations'].append(results['pdfplumber']['citation_stats']['citations_found'])
        
        # Calculate averages
        def avg_list(lst):
            return sum(lst) / len(lst) if lst else 0
        
        print(f"\n{'='*80}")
        print("CONCLUSION: METHOD COMPARISON")
        print(f"{'='*80}\n")
        
        print(f"Papers analyzed: {len(self.all_results)}\n")
        
        print("CANONICAL STRUCTURE COVERAGE:")
        pymupdf_avg = avg_list(pymupdf_scores['coverage'])
        pdfplumber_avg = avg_list(pdfplumber_scores['coverage'])
        print(f"  PyMuPDF:   {pymupdf_avg:.1f}%")
        print(f"  pdfplumber: {pdfplumber_avg:.1f}%")
        winner = "PyMuPDF" if pymupdf_avg > pdfplumber_avg else "pdfplumber"
        print(f"  ✓ Winner: {winner}\n")
        
        print("CANONICAL SECTIONS FOUND (average):")
        pymupdf_sections = avg_list(pymupdf_scores['sections'])
        pdfplumber_sections = avg_list(pdfplumber_scores['sections'])
        print(f"  PyMuPDF:   {pymupdf_sections:.1f}/10")
        print(f"  pdfplumber: {pdfplumber_sections:.1f}/10")
        winner = "PyMuPDF" if pymupdf_sections > pdfplumber_sections else "pdfplumber"
        print(f"  ✓ Winner: {winner}\n")
        
        print("CITATION DETECTION (average citations found):")
        pymupdf_cites = avg_list(pymupdf_scores['citations'])
        pdfplumber_cites = avg_list(pdfplumber_scores['citations'])
        print(f"  PyMuPDF:   {pymupdf_cites:.0f}")
        print(f"  pdfplumber: {pdfplumber_cites:.0f}")
        winner = "PyMuPDF" if pymupdf_cites > pdfplumber_cites else "pdfplumber"
        print(f"  ✓ Winner: {winner}\n")
        
        # Overall recommendation
        print("RECOMMENDATION:")
        if pymupdf_avg > pdfplumber_avg and pymupdf_sections > pdfplumber_sections:
            print("  ✓ PyMuPDF is the recommended method for structure extraction.")
            print("    • Better coverage of canonical sections")
            print("    • More reliable section detection")
        elif pdfplumber_avg > pymupdf_avg and pdfplumber_sections > pymupdf_sections:
            print("  ✓ pdfplumber is the recommended method for structure extraction.")
            print("    • Better coverage of canonical sections")
            print("    • More reliable section detection")
        else:
            print("  • Both methods perform similarly.")
            print("    • PyMuPDF advantages: Font-aware detection, better for structured PDFs")
            print("    • pdfplumber advantages: Position-aware, robust text extraction")
            print("    • Recommendation: Use PyMuPDF as default, fallback to pdfplumber if needed")
        
        print(f"\n{'='*80}\n")


def main():
    """Run hierarchical structure test."""
    parser = argparse.ArgumentParser(
        description="Test hierarchical structure detection with citation removal (text-based PDFs)"
    )
    parser.add_argument(
        "--technique",
        choices=["pymupdf", "pdfplumber", "both"],
        default="both",
        help="Which technique to use (default: both)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # DON'T set root logger to DEBUG - PyMuPDF respects this level and enables its own debug output
    # Instead, pass verbose as a flag to the test and let it handle logging
    # Keep PyMuPDF quiet even in verbose mode (it's C-level debug output, not our logging)
    logging.getLogger('fitz').setLevel(logging.WARNING)
    logging.getLogger('pymupdf').setLevel(logging.WARNING)

    # Paths
    this_dir = Path(__file__).parent
    jsonl_path = this_dir / "papers_with_pdfs.jsonl"

    if not jsonl_path.exists():
        print(f"\n✗ JSONL file not found: {jsonl_path}")
        print(f"  Run: uv run python {this_dir}/prepare_papers.py\n")
        sys.exit(1)

    try:
        # Load papers
        papers = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip():
                    paper_dict = json.loads(line)
                    paper = Paper.model_validate(paper_dict)
                    papers.append(paper)

        # Run test
        test = HierarchicalStructureTest(technique=args.technique, verbose=args.verbose)
        test.test_papers(papers)
        
        # Print conclusion
        test.print_conclusion()

        print(f"{'='*80}")
        print("✓ Hierarchical structure test completed!")
        print(f"{'='*80}\n")

    except Exception as e:
        print(f"\n✗ Test failed: {e}\n")
        if args.verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
