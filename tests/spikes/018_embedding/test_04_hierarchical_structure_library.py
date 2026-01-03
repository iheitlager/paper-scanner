#!/usr/bin/env python3
"""
Spike 018: Test 4 - Hierarchical Structure Extraction (Library-Based)
======================================================================

Uses citation_remover and extractor library modules to extract and analyze
all papers with PDF files in the dataset.
"""

import logging
import sys
from pathlib import Path

from paper_scanner.core.models import Paper
from paper_scanner.tools.embedding.citation_remover import CitationRemover
from paper_scanner.tools.embedding.extractor import PDFExtractor

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

# Setup logging
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


class HierarchicalStructureAnalysis:
    """Analyze hierarchical structure of academic papers."""

    def __init__(self):
        """Initialize analysis tools."""
        self.extractor = PDFExtractor()
        self.citation_remover = CitationRemover()
        self.results = []

    def analyze_papers(self, papers: list) -> None:
        """Analyze all papers with valid PDFs.
        
        Args:
            papers: List of Paper objects
        """
        # Filter papers with PDFs
        papers_with_pdfs = [
            p for p in papers
            if p.pdf_info and p.pdf_info.file_path and Path(p.pdf_info.file_path).exists()
        ]

        if not papers_with_pdfs:
            logger.error("✗ No papers with valid PDFs found")
            return

        print(f"\n{'='*80}")
        print(f"HIERARCHICAL STRUCTURE ANALYSIS")
        print(f"{'='*80}")
        print(f"\nPapers to analyze: {len(papers_with_pdfs)}\n")

        for idx, paper in enumerate(papers_with_pdfs, 1):
            logger.info(f"[{idx}/{len(papers_with_pdfs)}] Processing: {paper.cite_key}")
            self.analyze_single_paper(paper)

        # Print summary
        self.print_summary()

    def analyze_single_paper(self, paper: Paper) -> None:
        """Analyze a single paper.
        
        Args:
            paper: Paper object with PDF
        """
        if not paper.pdf_info or not paper.pdf_info.file_path:
            return

        pdf_path = paper.pdf_info.file_path
        
        # Extract structure
        extraction = self.extractor.extract(pdf_path)
        if not extraction:
            return

        text = extraction['text']
        coverage = extraction['coverage']
        
        # Remove citations
        cleaned_text, citation_stats = self.citation_remover.remove_citations(text)
        
        # Store results
        result = {
            'paper': paper.cite_key,
            'title': paper.title,
            'pdf': Path(pdf_path).name,
            'extraction': extraction,
            'citation_stats': citation_stats,
        }
        self.results.append(result)
        
        # Print paper results
        self.print_paper_result(result)

    def print_paper_result(self, result: dict) -> None:
        """Print formatted results for a single paper."""
        print(f"\nPaper: {result['paper']}")
        print(f"Title: {result['title']}")
        print(f"PDF: {result['pdf']}")
        print(f"\n{'-'*80}")
        
        # Text statistics
        stats = result['citation_stats']
        print(f"\nTEXT STATISTICS")
        print(f"  ────────────────────────────────────────────────────────────────────────────")
        print(f"  • Original size: {stats['original_chars']:,} chars ({stats['original_tokens']:,} tokens)")
        print(f"  • After citation removal: {stats['final_chars']:,} chars ({stats['final_tokens']:,} tokens)")
        print(f"  • Removed: {stats['removed_chars']:,} chars ({stats['removed_percentage_chars']}%)")
        
        # Raw sections
        extraction = result['extraction']
        raw_sections = extraction['raw_sections']
        print(f"\nRAW SECTION DETECTION")
        print(f"  ────────────────────────────────────────────────────────────────────────────")
        print(f"  • Raw sections found: {len(raw_sections)}")
        
        # Canonical structure
        coverage = extraction['coverage']
        found = coverage['found']
        missing = coverage['missing']
        coverage_pct = round(100 * len(found) / 10, 1)
        
        print(f"\nCANONICAL STRUCTURE")
        print(f"  ────────────────────────────────────────────────────────────────────────────")
        print(f"  • Coverage: {coverage_pct}% ({len(found)}/10 sections)")
        
        if found:
            found_str = ", ".join(found)
            print(f"  • Found: {found_str}")
        
        if missing:
            missing_str = ", ".join(missing)
            print(f"  • Missing: {missing_str}")
        
        # Citation removal
        print(f"\nCITATION REMOVAL")
        print(f"  ────────────────────────────────────────────────────────────────────────────")
        print(f"  • Citations found: {stats['citations_found']}")
        print(f"  • Chars removed: {stats['removed_chars']:,} ({stats['removed_percentage_chars']}%)")
        print(f"  • Tokens removed: {stats['removed_tokens']:,} ({stats['removed_percentage_tokens']}%)")
        print(f"  • Remaining tokens: {stats['final_tokens']:,}")
        
        print(f"\n{'-'*80}\n")

    def print_summary(self) -> None:
        """Print summary of all analyzed papers."""
        if not self.results:
            return
        
        print(f"\n{'='*80}")
        print(f"ANALYSIS SUMMARY")
        print(f"{'='*80}")
        
        # Coverage statistics
        coverage_scores = [
            len(r['extraction']['coverage']['found']) / 10 * 100
            for r in self.results
        ]
        avg_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0
        
        # Citation statistics
        citations = [r['citation_stats']['citations_found'] for r in self.results]
        avg_citations = sum(citations) / len(citations) if citations else 0
        
        # Text statistics
        chars_removed = [r['citation_stats']['removed_chars'] for r in self.results]
        avg_chars_removed = sum(chars_removed) / len(chars_removed) if chars_removed else 0
        
        print(f"\nPapers analyzed: {len(self.results)}")
        print(f"\nCANONICAL STRUCTURE COVERAGE:")
        print(f"  • Average: {avg_coverage:.1f}%")
        print(f"  • Range: {min(coverage_scores):.1f}% - {max(coverage_scores):.1f}%")
        
        print(f"\nCITATION DETECTION:")
        print(f"  • Average citations found: {avg_citations:.0f}")
        print(f"  • Total citations: {sum(citations)}")
        
        print(f"\nTEXT CLEANING:")
        print(f"  • Average chars removed: {avg_chars_removed:,.0f}")
        print(f"  • Total chars removed: {sum(chars_removed):,}")
        
        print(f"\n{'='*80}")
        print(f"✓ Analysis completed!")
        print(f"{'='*80}\n")


def load_papers_from_jsonl(jsonl_path: Path) -> list:
    """Load papers from JSONL file.
    
    Args:
        jsonl_path: Path to JSONL file
        
    Returns:
        List of Paper objects
    """
    import json
    
    papers = []
    if not jsonl_path.exists():
        logger.error(f"File not found: {jsonl_path}")
        return papers
    
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                try:
                    paper = Paper(**data)
                    papers.append(paper)
                except Exception as e:
                    logger.warning(f"Could not load paper from JSON: {e}")
    
    return papers


if __name__ == "__main__":
    # Find papers with PDFs
    this_dir = Path(__file__).parent
    jsonl_path = this_dir / "papers_with_pdfs.jsonl"
    
    logger.info(f"Loading papers from: {jsonl_path}")
    papers = load_papers_from_jsonl(jsonl_path)
    
    if not papers:
        logger.error("No papers found in JSONL file")
        sys.exit(1)
    
    logger.info(f"✓ Loaded {len(papers)} papers")
    
    # Run analysis
    analysis = HierarchicalStructureAnalysis()
    analysis.analyze_papers(papers)
