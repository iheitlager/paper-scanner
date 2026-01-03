#!/usr/bin/env python3
"""
Spike 018: Test 6 - Hierarchical Embedder
==========================================

Two-pass embedding pipeline (3-level hierarchy):
- Pass 1: Create hierarchical TextChunk structure (from test_05)
  - Level 0: Paper (root)
  - Level 1: Sections (canonical sections)
  - Level 2: Paragraphs (logical text divisions)
- Pass 2: Generate embeddings for each chunk (section + paragraph level)
  - Embeds section-level (Level 1) and paragraph-level (Level 2) chunks
  - Stores embedding in TextChunk.embedding field
  - Skips root chunks (paper level) as they only anchor hierarchy

This creates a complete embedding dataset ready for semantic search and clustering.

Design note: 3-level hierarchy (not 4) because:
- Paragraph-level granularity is sufficient for retrieval
- Sentence-level would create 10x overhead without clear value
- LLM analysis (planned) handles fine-grained semantic understanding
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import torch
from sentence_transformers import SentenceTransformer

from paper_scanner.core.models import Embedding, Paper, TextChunk
from paper_scanner.tools.embedding.citation_remover import CitationRemover
from paper_scanner.tools.embedding.extractor import PDFExtractor
from paper_scanner.tools.embedding.sections import (
    detect_sections,
    group_sections_hierarchically,
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
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


class EmbeddingGenerator:
    """Generate hierarchical embeddings for papers."""

    def __init__(self, model_name: str = "all-mpnet-base-v2", device: Optional[str] = None):
        """Initialize embedding generator."""
        self.model_name = model_name
        self.device = self._select_device(device)
        self.model = None
        self.extractor = PDFExtractor()
        self.citation_remover = CitationRemover()
        self.results = []

        logger.info(f"Loading embedding model: {model_name}")
        logger.info(f"Device: {self.device}")

    def _select_device(self, user_device: Optional[str]) -> str:
        """Select compute device with fallback (MPS first for Apple)."""
        if user_device:
            return user_device

        # Prioritize MPS for Apple Silicon
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        else:
            return "cpu"

    def load_model(self) -> None:
        """Load embedding model to device."""
        self.model = SentenceTransformer(self.model_name)
        self.model.to(self.device)
        logger.info(f"✓ Model loaded ({self.model.get_sentence_embedding_dimension()}-dim)")

    def process_papers(self, papers: list) -> None:
        """Process all papers with two passes."""
        papers_with_pdfs = [p for p in papers if p.pdf_info and p.pdf_info.file_path]

        if not papers_with_pdfs:
            logger.error("No papers with PDFs found")
            return

        logger.info(f"\n{'='*80}")
        logger.info("PASS 1: Create Hierarchical Structure")
        logger.info(f"{'='*80}\n")

        # Pass 1: Create chunks for all papers
        chunks_by_paper = {}
        for idx, paper in enumerate(papers_with_pdfs, 1):
            logger.info(f"[{idx}/{len(papers_with_pdfs)}] {paper.source_key}")
            chunks = self._create_chunks(paper)
            if chunks:
                chunks_by_paper[paper.id] = chunks
                logger.info(f"  ✓ Created {len(chunks)} chunks")
            else:
                logger.info(f"  ✗ Failed to create chunks")

        logger.info(f"\n{'='*80}")
        logger.info("PASS 2: Generate Embeddings")
        logger.info(f"{'='*80}\n")

        # Pass 2: Generate embeddings for all chunks
        total_embeddings = 0
        for idx, paper in enumerate(papers_with_pdfs, 1):
            if paper.id not in chunks_by_paper:
                continue

            logger.info(f"[{idx}/{len(papers_with_pdfs)}] {paper.source_key}")
            chunks = chunks_by_paper[paper.id]

            # Generate embeddings
            chunks_with_embeddings = self._generate_embeddings(chunks)

            # Show summary
            self._print_embedding_summary(paper, chunks_with_embeddings)
            
            # Store result
            self.results.append({
                "paper": paper,
                "chunks": chunks_with_embeddings,
                "embedding_count": len([c for c in chunks_with_embeddings if c.embedding])
            })
            total_embeddings += len([c for c in chunks_with_embeddings if c.embedding])

        # Print final summary
        self._print_final_summary(total_embeddings)

    def _create_chunks(self, paper: Paper) -> List[TextChunk]:
        """Create hierarchical chunks for a paper (Pass 1 logic from test_05)."""
        try:
            # Extract text
            result = self.extractor.extract(paper.pdf_info.file_path)
            if not result:
                return []

            text = result["text"]
            hierarchical = result["hierarchical_sections"]

            # Create chunks hierarchy
            chunks = self._build_chunk_hierarchy(paper.id, hierarchical)
            return chunks

        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            return []

    def _build_chunk_hierarchy(
        self, paper_id: str, hierarchical_sections: dict
    ) -> List[TextChunk]:
        """Build TextChunk hierarchy from sections."""
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
            if not isinstance(section_list, list):
                continue

            for section_item in section_list:
                if not isinstance(section_item, dict):
                    continue

                section_content = section_item.get("content", "").strip()
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
                for paragraph in paragraphs:
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
        """Split text into paragraphs."""
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

        return [p for p in paragraphs if len(p) > 20]

    def _generate_embeddings(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Generate embeddings for all chunks (Pass 2)."""
        chunks_with_embeddings = []
        embeddable_chunks = []
        chunk_map = {}

        # Filter out root chunk and chunks without meaningful text
        for chunk in chunks:
            if chunk.hierarchy_level > 0 and chunk.text and len(chunk.text) > 5:
                embeddable_chunks.append(chunk)
                chunk_map[chunk.chunk_index] = chunk

        if not embeddable_chunks:
            return chunks

        # Extract texts for embedding
        texts = [chunk.text for chunk in embeddable_chunks]

        # Generate embeddings in batch
        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                device=self.device,
            )

        # Create Embedding objects and attach to chunks
        for chunk, embedding_vector in zip(embeddable_chunks, embeddings):
            chunk.embedding = Embedding(
                vector=embedding_vector.tolist(),
                model=self.model_name,
                text_source=chunk.section or "unknown",
                created_at=chunk.created_at,
            )

        # Combine: root chunk + chunks with embeddings
        result = [chunks[0]]  # Add root chunk
        for chunk in chunks[1:]:
            if chunk.embedding:
                result.append(chunk)
            else:
                result.append(chunk)

        return result

    def _print_embedding_summary(self, paper: Paper, chunks: List[TextChunk]) -> None:
        """Print embedding summary for a paper."""
        embedded_count = len([c for c in chunks if c.embedding])
        total_count = len([c for c in chunks if c.hierarchy_level > 0])

        level_counts = {}
        embedded_by_level = {}
        for chunk in chunks:
            level = chunk.hierarchy_level
            level_counts[level] = level_counts.get(level, 0) + 1
            if chunk.embedding:
                embedded_by_level[level] = embedded_by_level.get(level, 0) + 1

        logger.info(f"  Embeddings: {embedded_count}/{total_count}")
        logger.info(f"  Levels:")
        for level in sorted(level_counts.keys()):
            if level > 0:
                emb = embedded_by_level.get(level, 0)
                logger.info(f"    Level {level}: {emb}/{level_counts[level]} embedded")

    def _print_final_summary(self, total_embeddings: int) -> None:
        """Print final summary."""
        if not self.results:
            return

        total_papers = len(self.results)
        total_chunks = sum(len(r["chunks"]) for r in self.results)

        logger.info(f"\n{'='*80}")
        logger.info("EMBEDDING SUMMARY")
        logger.info(f"{'='*80}\n")

        logger.info(f"Papers processed: {total_papers}")
        logger.info(f"Total chunks: {total_chunks}")
        logger.info(f"Total embeddings: {total_embeddings}")
        logger.info(f"Average embeddings per paper: {total_embeddings // total_papers if total_papers > 0 else 0}")
        logger.info(f"\nEmbedding model: {self.model_name}")
        logger.info(f"Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        logger.info(f"Device: {self.device}")

        # Show sample similarities
        logger.info(f"\n{'='*80}")
        logger.info("SAMPLE SEMANTIC SIMILARITIES")
        logger.info(f"{'='*80}\n")

        self._show_sample_similarities()

        logger.info(f"\n{'='*80}")
        logger.info("✓ Embedding completed!")
        logger.info(f"{'='*80}")

    def _show_sample_similarities(self) -> None:
        """Show sample semantic similarities between chunks."""
        # Get all embedded chunks
        all_embedded = []
        for result in self.results:
            for chunk in result["chunks"]:
                if chunk.embedding and chunk.hierarchy_level > 0:
                    all_embedded.append(chunk)

        if len(all_embedded) < 3:
            logger.info("Not enough embeddings for similarity comparison")
            return

        # Pick 3 random chunks and show similarities
        import random

        sample_indices = random.sample(range(len(all_embedded)), min(3, len(all_embedded)))

        for i, idx in enumerate(sample_indices):
            chunk1 = all_embedded[idx]

            logger.info(f"\nChunk {i+1} ({chunk1.section}):")
            logger.info(f"  Text: {chunk1.text[:80]}...")

            # Find most similar chunks
            similarities = []
            for j, chunk2 in enumerate(all_embedded):
                if j == idx:
                    continue
                
                sim = chunk1.similarity_to(chunk2)
                if sim is not None:
                    similarities.append((sim, chunk2))

            # Show top 3 similar chunks
            if similarities:
                similarities.sort(reverse=True)
                logger.info(f"  Most similar chunks:")
                for sim, chunk in similarities[:3]:
                    logger.info(f"    • {chunk.section:15} | Similarity: {sim:.3f} | {chunk.text[:60]}...")


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
                    logger.warning(f"Could not load paper: {e}")

    return papers


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate hierarchical embeddings for papers")
    parser.add_argument(
        "--model",
        default="all-mpnet-base-v2",
        help="Embedding model name (default: all-mpnet-base-v2)",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "mps"],
        help="Compute device (default: auto-detect)",
    )

    args = parser.parse_args()

    # Find papers with PDFs
    this_dir = Path(__file__).parent
    jsonl_path = this_dir / "papers_with_pdfs.jsonl"

    logger.info(f"Loading papers from: {jsonl_path}")
    papers = load_papers_from_jsonl(jsonl_path)

    if not papers:
        logger.error("No papers found")
        sys.exit(1)

    logger.info(f"✓ Loaded {len(papers)} papers\n")

    # Run embedding pipeline
    generator = EmbeddingGenerator(model_name=args.model, device=args.device)
    generator.load_model()
    generator.process_papers(papers)
