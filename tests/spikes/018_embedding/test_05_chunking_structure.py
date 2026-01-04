#!/usr/bin/env python3
"""
Spike 018: Test 5 - Hierarchical Chunking Structure
=====================================================

Creates hierarchical TextChunk structure for papers (3-level hierarchy):
- Level 0: Paper (root)
- Level 1: Sections (canonical sections like "introduction", "methods")
- Level 2: Paragraphs (logical text divisions within sections)

Why 3 levels (not 4)?
- Sentence-level creates 10x overhead (6,000+ sentences per 7 papers)
- Paragraph-level is sufficient for fine-grained retrieval
- LLM analysis (planned) handles semantic understanding
- Embedding focuses on structural retrieval, not sentence semantics

This sets up the hierarchy needed for later embedding (test_06).
"""

import json
import logging
import sys
from pathlib import Path

from paper_scanner.core.models import Paper, TextChunk
from paper_scanner.tools.embedding.citation_remover import CitationRemover
from paper_scanner.tools.embedding.extractor import PDFExtractor
from paper_scanner.tools.embedding.sections import (
    detect_sections,
    group_sections_hierarchically,
    normalize_section_name,
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Suppress debug logging from external libraries
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("fitz").setLevel(logging.WARNING)
logging.getLogger("pymupdf").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)


class ChunkingAnalysis:
    """Build hierarchical TextChunk structure for papers."""

    def __init__(self):
        """Initialize analysis tools."""
        self.extractor = PDFExtractor()
        self.citation_remover = CitationRemover()
        self.results = []

    def analyze_papers(self, papers: list) -> None:
        """Analyze all papers with valid PDFs."""
        papers_with_pdfs = [p for p in papers if p.pdf_info and p.pdf_info.file_path]

        if not papers_with_pdfs:
            logger.error("No papers with PDFs found")
            return

        logger.info(f"\n[1/{len(papers_with_pdfs)}] Processing papers...\n")

        for idx, paper in enumerate(papers_with_pdfs, 1):
            logger.info(f"[{idx}/{len(papers_with_pdfs)}] Processing: {paper.source_key}")

            # Extract and chunk paper
            chunks = self._process_paper(paper)

            if chunks:
                self._print_paper_summary(paper, chunks)
                self._print_hierarchy_tree(chunks)
                self.results.append({"paper": paper, "chunks": chunks})

            logger.info("")

        # Print final summary
        self._print_summary()

    def _process_paper(self, paper: Paper) -> list:
        """Process paper: extract text, detect sections, create chunks."""
        try:
            # Extract text
            result = self.extractor.extract(paper.pdf_info.file_path)
            if not result:
                logger.error(f"  ✗ Extraction failed")
                return []

            text = result["text"]
            raw_sections = result["raw_sections"]
            hierarchical = result["hierarchical_sections"]

            # Remove citations
            cleaned_text = self.citation_remover.remove_citations(text)

            # Create chunks hierarchy
            chunks = self._create_chunks(paper.id, hierarchical, cleaned_text)

            return chunks

        except Exception as e:
            logger.error(f"  ✗ Processing failed: {e}")
            return []

    def _create_chunks(
        self, paper_id: str, hierarchical_sections: dict, full_text: str
    ) -> list:
        """Create TextChunk hierarchy from sections."""
        chunks = []
        chunk_index = 0

        # Root chunk for the paper (Level 0)
        paper_chunk = TextChunk(
            id=paper_id,
            chunk_index=chunk_index,
            text="[Paper root]",
            section=None,
            hierarchy_level=0,
            parent_id=None,
            parent_type=None,
            word_count=0,
        )
        chunks.append(paper_chunk)
        chunk_index += 1

        # Process each canonical section
        for section_name, section_list in hierarchical_sections.items():
            # section_list is a list of dicts with 'title', 'content', 'canonical' keys
            if not isinstance(section_list, list):
                continue

            for section_item in section_list:
                if not isinstance(section_item, dict):
                    continue

                section_content = section_item.get("content", "").strip()
                section_title = section_item.get("title", section_name)

                if not section_content:
                    continue

                # Section chunk (Level 1)
                section_chunk = TextChunk(
                    chunk_index=chunk_index,
                    text=section_content[:100] + "..." if len(section_content) > 100 else section_content,
                    section=section_name,
                    hierarchy_level=1,
                    parent_id=paper_id,
                    parent_type="paper",
                    word_count=len(section_content.split()),
                )
                chunks.append(section_chunk)
                section_id = section_chunk.id
                chunk_index += 1

                # Create paragraph chunks (Level 2)
                paragraphs = self._split_paragraphs(section_content)
                for para_idx, paragraph in enumerate(paragraphs):
                    para_chunk = TextChunk(
                        chunk_index=chunk_index,
                        text=paragraph.strip(),
                        section=section_name,
                        hierarchy_level=2,
                        parent_id=section_id,
                        parent_type="section",
                        word_count=len(paragraph.split()),
                    )
                    chunks.append(para_chunk)
                    chunk_index += 1

        return chunks

    @staticmethod
    def _split_paragraphs(text: str) -> list:
        """Split text into paragraphs (by double newlines or heuristic)."""
        # Split by double newlines or 4+ spaces
        paragraphs = []
        current = ""

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                if current.strip():
                    paragraphs.append(current.strip())
                    current = ""
            else:
                current += " " + line if current else line

        if current.strip():
            paragraphs.append(current.strip())

        # Filter out very short paragraphs (< 20 chars)
        return [p for p in paragraphs if len(p) > 20]

    def _print_paper_summary(self, paper: Paper, chunks: list) -> None:
        """Print paper summary."""
        level_counts = {}
        for chunk in chunks:
            level = chunk.hierarchy_level
            level_counts[level] = level_counts.get(level, 0) + 1

        logger.info(f"  Title: {paper.title}")
        logger.info(f"  Authors: {paper.author_string}")
        logger.info(f"  Year: {paper.year}")
        logger.info(f"\n  CHUNK HIERARCHY (3-Level: Paper → Sections → Paragraphs):")
        logger.info(f"  ────────────────────────────────────────────────────────────────────────────")
        for level in sorted(level_counts.keys()):
            level_names = {0: "Papers", 1: "Sections", 2: "Paragraphs"}
            logger.info(f"  • Level {level} ({level_names.get(level, 'Unknown')}): {level_counts[level]}")

    def _print_hierarchy_tree(self, chunks: list) -> None:
        """Print hierarchical tree of chunks."""
        logger.info(f"\n  HIERARCHY TREE:")
        logger.info(f"  ────────────────────────────────────────────────────────────────────────────")

        # Build hierarchy map
        children_map = {}
        for chunk in chunks:
            if chunk.parent_id:
                if chunk.parent_id not in children_map:
                    children_map[chunk.parent_id] = []
                children_map[chunk.parent_id].append(chunk)

        # Print tree starting from root (Level 0)
        root = next((c for c in chunks if c.hierarchy_level == 0), None)
        if root:
            self._print_tree_node(root, children_map, indent=0)

    def _print_tree_node(self, chunk: TextChunk, children_map: dict, indent: int) -> None:
        """Recursively print tree node and children."""
        prefix = "  " * indent
        marker = ["📄", "📋", "📝", "📄"][min(chunk.hierarchy_level, 3)]

        # Format text preview
        text_preview = chunk.text[:60].replace("\n", " ")
        if len(chunk.text) > 60:
            text_preview += "..."

        if chunk.hierarchy_level == 0:
            logger.info(f"{prefix}{marker} Paper ({len(children_map.get(chunk.id, []))} sections)")
        else:
            word_info = f" [{chunk.word_count} words]" if chunk.word_count > 0 else ""
            logger.info(f"{prefix}{marker} {text_preview}{word_info}")

        # Print children (but limit output for deep levels)
        children = children_map.get(chunk.id, [])
        if children:
            # For sections and paragraphs, show some children
            if chunk.hierarchy_level <= 1:
                for child in children[:5]:  # Show first 5
                    self._print_tree_node(child, children_map, indent + 1)
                if len(children) > 5:
                    logger.info(f"{'  ' * (indent + 1)}... and {len(children) - 5} more")
            else:
                # For sentences, just show count
                logger.info(f"{'  ' * (indent + 1)}└─ {len(children)} children")

    def _print_summary(self) -> None:
        """Print overall summary with per-level breakdown."""
        if not self.results:
            return

        logger.info("\n")
        logger.info("=" * 80)
        logger.info("CHUNKING SUMMARY - BY LEVEL")
        logger.info("=" * 80)

        total_chunks = sum(len(r["chunks"]) for r in self.results)
        total_papers = len(self.results)

        # Count chunks by level
        level_totals = {0: 0, 1: 0, 2: 0}
        for result in self.results:
            for chunk in result["chunks"]:
                level = chunk.hierarchy_level
                if level in level_totals:
                    level_totals[level] += 1

        logger.info(f"\nPapers analyzed: {total_papers}")
        logger.info(f"Total chunks created: {total_chunks}")
        logger.info(f"Average chunks per paper: {total_chunks // total_papers if total_papers > 0 else 0}")
        
        logger.info(f"\n{'─'*80}")
        logger.info("Chunks by Hierarchy Level:")
        logger.info(f"{'─'*80}")
        logger.info(f"  Level 0 (Papers):      {level_totals[0]:4d} ({100*level_totals[0]/total_chunks:5.1f}%)")
        logger.info(f"  Level 1 (Sections):    {level_totals[1]:4d} ({100*level_totals[1]/total_chunks:5.1f}%)")
        logger.info(f"  Level 2 (Paragraphs):  {level_totals[2]:4d} ({100*level_totals[2]/total_chunks:5.1f}%)")

        logger.info(f"\n{'='*80}")
        logger.info("✓ Chunking completed!")
        logger.info("=" * 80)


def load_papers_from_jsonl(jsonl_path: Path) -> list:
    """Load papers from JSONL file."""
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
    analysis = ChunkingAnalysis()
    analysis.analyze_papers(papers)
