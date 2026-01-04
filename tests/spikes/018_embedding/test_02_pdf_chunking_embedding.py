#!/usr/bin/env python3
"""
Spike 018: Test 2 - PDF Chunking & Embedding
=============================================

Test PDF extraction, intelligent chunking with section detection, 
and embedding generation for paper text chunks.

This test:
1. Loads papers with pdf_info.file_path pointing to actual PDF files
2. Uses PDFChunker to extract text and detect sections (Introduction, Methods, Results, etc.)
3. Generates embeddings for each chunk using sentence-transformers
4. Stores chunks with embeddings in Paper.text_chunks list
5. Tests chunk-level semantic search and aggregation
6. Demonstrates storage in Paper model before persistence

Usage:
    python test_02_pdf_chunking_embedding.py
    python test_02_pdf_chunking_embedding.py --verbose
    python test_02_pdf_chunking_embedding.py --chunk-size 512 --overlap 50

Requires:
    sentence-transformers  # For embedding generation
    pypdf                  # For PDF text extraction
    tiktoken              # For token counting
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from paper_scanner.core.models import Embedding, Paper, TextChunk
from paper_scanner.tools.embedding.chunker import PDFChunker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PDFEmbeddingPipeline:
    """Pipeline for PDF chunking and embedding."""

    def __init__(
        self,
        model_name: str = "all-mpnet-base-v2",
        device: str = "cpu",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """Initialize PDF embedding pipeline.
        
        Args:
            model_name: Hugging Face model identifier
            device: "cpu" or "cuda"
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
        """
        self.model_name = model_name
        self.device = device
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model: Optional[SentenceTransformer] = None
        self.chunker: Optional[PDFChunker] = None
        self.stats = {
            "papers_processed": 0,
            "pdfs_found": 0,
            "pdfs_processed": 0,
            "chunks_generated": 0,
            "embeddings_generated": 0,
            "errors": 0,
        }

    def load_model(self) -> None:
        """Load the embedding model."""
        logger.info(f"Loading model: {self.model_name}")
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.chunker = PDFChunker(
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap,
            )
            logger.info(f"✓ Model and chunker loaded (device: {self.device})")
        except Exception as e:
            logger.error(f"✗ Failed to load model: {e}")
            raise

    def embed_text(self, text: Optional[str]) -> Optional[List[float]]:
        """Generate embedding for a text string.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (768 dimensions) or None if text is empty
        """
        if not text or not text.strip():
            return None

        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Failed to embed text: {e}")
            return None

    def create_embedding_object(
        self, vector: List[float], text_source: str
    ) -> Embedding:
        """Create an Embedding model object.
        
        Args:
            vector: Embedding vector
            text_source: Description of what was embedded
            
        Returns:
            Embedding model instance
        """
        # Ensure exactly 768 dimensions
        if len(vector) != 768:
            logger.debug(
                f"Vector has {len(vector)} dims, expected 768. Adjusting..."
            )
            if len(vector) < 768:
                vector = vector + [0.0] * (768 - len(vector))
            else:
                vector = vector[:768]

        return Embedding(
            vector=vector,
            model=self.model_name,
            text_source=text_source,
            created_at=datetime.now(timezone.utc),
        )

    def process_paper_pdf(self, paper: Paper) -> int:
        """Process a paper PDF and generate chunk embeddings.
        
        Args:
            paper: Paper object with pdf_info.file_path
            
        Returns:
            Number of chunks processed (0 if no PDF or error)
        """
        self.stats["papers_processed"] += 1

        # Check if PDF path is available
        if not paper.pdf_info or not paper.pdf_info.file_path:
            logger.debug(f"Paper {paper.cite_key}: No PDF path available")
            return 0

        pdf_path = Path(paper.pdf_info.file_path)
        
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return 0

        self.stats["pdfs_found"] += 1
        logger.info(f"Processing PDF for {paper.cite_key}: {pdf_path.name}")

        try:
            # Step 1: Chunk the PDF
            chunks = self.chunker.chunk_paper(str(pdf_path), strategy="hybrid")

            if not chunks:
                logger.warning(f"No chunks generated for {paper.cite_key}")
                return 0

            logger.debug(f"  → Generated {len(chunks)} chunks")

            # Step 2: Process each chunk
            paper.text_chunks = []  # Initialize empty list
            successful_chunk_index = 0  # Track index of successfully processed chunks

            for raw_chunk_index, chunk in enumerate(chunks):
                try:
                    logger.debug(f"    [Chunk {raw_chunk_index + 1}/{len(chunks)}] Processing...")
                    
                    # Extract chunk text
                    chunk_text = chunk.get("content", chunk.get("text", ""))
                    section = chunk.get("section", None)

                    if not chunk_text.strip():
                        logger.debug(f"      ✗ Skipped: empty text")
                        continue

                    # Generate embedding for chunk
                    embedding_vector = self.embed_text(chunk_text)
                    if not embedding_vector:
                        logger.debug(f"      ✗ Skipped: embedding failed")
                        continue

                    embedding_obj = self.create_embedding_object(
                        embedding_vector, f"chunk_{section or 'unknown'}"
                    )

                    # Create TextChunk object
                    # Note: TextChunk.id is auto-generated UUID, chunk_index is sequential
                    text_chunk = TextChunk(
                        chunk_index=successful_chunk_index,
                        text=chunk_text,
                        section=section,
                        start_char=chunk.get("start_char"),
                        end_char=chunk.get("end_char"),
                        embedding=embedding_obj,
                        word_count=len(chunk_text.split()),
                        created_at=datetime.now(timezone.utc),
                    )

                    paper.text_chunks.append(text_chunk)
                    self.stats["embeddings_generated"] += 1
                    successful_chunk_index += 1
                    logger.debug(f"      ✓ Chunk embedded (section: {section}, index: {successful_chunk_index - 1})")

                except Exception as e:
                    logger.warning(
                        f"    Error processing chunk {chunk_index}: {e}"
                    )
                    continue

            self.stats["chunks_generated"] += len(paper.text_chunks)
            self.stats["pdfs_processed"] += 1

            # Step 3: Aggregate chunk embeddings into paper-level embedding
            # Strategy (MVP): Average all chunks for paper-level similarity
            if paper.text_chunks:
                paper.title_abstract_embedding = self.aggregate_paper_embedding(paper)

            logger.info(
                f"  ✓ {paper.cite_key}: {len(paper.text_chunks)} chunks embedded"
            )

            return len(paper.text_chunks)

        except Exception as e:
            logger.error(f"✗ Error processing PDF for {paper.cite_key}: {e}")
            self.stats["errors"] += 1
            return 0

    def process_papers(self, papers: List[Paper]) -> int:
        """Process a list of papers.
        
        Args:
            papers: List of Paper objects
            
        Returns:
            Total number of chunks processed
        """
        total_chunks = 0

        for i, paper in enumerate(papers, 1):
            logger.info(f"\n[{i}/{len(papers)}] Processing paper: {paper.cite_key}")
            chunks_processed = self.process_paper_pdf(paper)
            total_chunks += chunks_processed
            logger.debug(f"     → Total chunks so far: {total_chunks}")

        return total_chunks

    def aggregate_paper_embedding(self, paper: Paper) -> Optional[Embedding]:
        """Aggregate chunk embeddings into a single paper-level embedding.
        
        Strategy (MVP): Average all chunk embeddings
        - Respects paper structure via section-aware chunks
        - Simple and fast computation
        - Future: Can upgrade to weighted average (higher weight for abstract, intro, conclusion)
        
        Args:
            paper: Paper with populated text_chunks
            
        Returns:
            Aggregated Embedding (768-dim vector) or None if no chunks
        """
        if not paper.text_chunks:
            logger.debug(f"No text chunks for {paper.cite_key}")
            return None

        # Collect all chunk embeddings
        chunk_vectors = [
            np.array(chunk.embedding.vector, dtype=np.float32)
            for chunk in paper.text_chunks
            if chunk.embedding and chunk.embedding.vector
        ]

        if not chunk_vectors:
            logger.warning(
                f"Paper {paper.cite_key}: text_chunks exist but no valid embeddings"
            )
            return None

        # Simple strategy: Average all chunk embeddings
        mean_vector = np.mean(chunk_vectors, axis=0)
        
        # Ensure it's a list and proper dimensions
        mean_vector_list = mean_vector.tolist()

        return self.create_embedding_object(
            mean_vector_list,
            f"aggregated_{len(chunk_vectors)}_chunks"
        )

    def search_chunks_by_query(
        self, papers: List[Paper], query: str, top_k: int = 5
    ) -> List[tuple]:
        """Search across all paper chunks using semantic similarity.
        
        Demonstrates fine-grained search at chunk level:
        - Each TextChunk has embedding.vector (768-dim)
        - section field indicates (intro, methods, results, etc.)
        - Enables finding specific discussion in papers
        
        Args:
            papers: List of papers with text_chunks populated
            query: Search query text
            top_k: Number of top results to return
            
        Returns:
            List of (paper, chunk, similarity_score) tuples sorted by similarity
        """
        if not self.model:
            raise RuntimeError("Model not loaded")

        # Embed query
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        results = []

        for paper in papers:
            if not paper.text_chunks:
                continue

            for chunk in paper.text_chunks:
                if not chunk.embedding:
                    continue

                chunk_vector = np.array(chunk.embedding.vector, dtype=np.float32)
                chunk_tensor = torch.from_numpy(chunk_vector).unsqueeze(0).to(self.device)

                similarity = util.pytorch_cos_sim(
                    query_embedding, chunk_tensor
                ).item()

                results.append((paper, chunk, similarity))

        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]


def print_results(
    pipeline: PDFEmbeddingPipeline, papers: List[Paper]
) -> None:
    """Print summary of PDF chunking and embedding results.
    
    Args:
        pipeline: PDFEmbeddingPipeline instance
        papers: List of papers processed
    """
    print("\n" + "="*80)
    print("PDF CHUNKING & EMBEDDING PIPELINE RESULTS")
    print("="*80)

    print(f"\nModel: {pipeline.model_name}")
    print(f"Chunk size: {pipeline.chunk_size} tokens")
    print(f"Chunk overlap: {pipeline.chunk_overlap} tokens")

    print(f"\nStatistics:")
    print(f"  Papers processed: {pipeline.stats['papers_processed']}")
    print(f"  PDFs found: {pipeline.stats['pdfs_found']}")
    print(f"  PDFs successfully processed: {pipeline.stats['pdfs_processed']}")
    print(f"  Total chunks generated: {pipeline.stats['chunks_generated']}")
    print(f"  Total embeddings generated: {pipeline.stats['embeddings_generated']}")
    print(f"  Errors: {pipeline.stats['errors']}")

    # Show sample papers with chunks
    papers_with_chunks = [p for p in papers if p.text_chunks]

    if papers_with_chunks:
        print("\n" + "-"*80)
        print("SAMPLE PAPERS WITH CHUNKS:")
        print("-"*80)

        for i, paper in enumerate(papers_with_chunks[:3], 1):
            print(f"\n{i}. {paper.cite_key}")
            print(f"   Title: {paper.title[:70] if paper.title else 'N/A'}...")
            print(f"   Chunks: {len(paper.text_chunks)}")

            # Show chunk breakdown by section
            sections = {}
            for chunk in paper.text_chunks:
                section = chunk.section or "unknown"
                sections[section] = sections.get(section, 0) + 1

            for section, count in sorted(sections.items()):
                print(f"     - {section}: {count} chunks")

            # Show sample chunks
            if paper.text_chunks:
                print(f"   Sample chunks:")
                for j, chunk in enumerate(paper.text_chunks[:2], 1):
                    text_preview = chunk.text[:60].replace("\n", " ") + "..."
                    print(
                        f"     Chunk {j} ({chunk.section}): {text_preview}"
                    )

    # Example chunk search
    print("\n" + "-"*80)
    print("CHUNK SEMANTIC SEARCH EXAMPLE:")
    print("-"*80)

    if papers_with_chunks:
        query = "digital transformation"
        print(f"\nQuery: '{query}'")

        results = pipeline.search_chunks_by_query(papers_with_chunks, query, top_k=5)

        if results:
            print("Top 5 matching chunks:")
            for i, (paper, chunk, similarity) in enumerate(results, 1):
                print(
                    f"{i}. {paper.cite_key} - Chunk {chunk.chunk_index}"
                    f" ({chunk.section}) - Similarity: {similarity:.4f}"
                )
                text_preview = chunk.text[:70].replace("\n", " ") + "..."
                print(f"   {text_preview}")
        else:
            print("No matching chunks found")
    else:
        print("No papers with chunks available for search")

    print("\n" + "="*80)


def main():
    """Run the PDF chunking and embedding pipeline test."""
    parser = argparse.ArgumentParser(
        description="Test PDF chunking and embedding pipeline"
    )
    parser.add_argument(
        "--model",
        default="all-mpnet-base-v2",
        help="Embedding model to use (default: all-mpnet-base-v2)"
    )
    parser.add_argument(
        "--device",
        default=None,  # Will auto-detect
        choices=["cpu", "mps", "cuda"],
        help="Device to use (default: auto-detect—mps for Apple Silicon, cuda for NVIDIA, cpu fallback)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Target tokens per chunk (default: 512)"
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Overlap tokens between chunks (default: 50)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Auto-detect device if not specified
    if args.device is None:
        if torch.backends.mps.is_available():
            args.device = "mps"
        elif torch.cuda.is_available():
            args.device = "cuda"
        else:
            args.device = "cpu"

    logger.info(f"Using device: {args.device}")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Paths
    this_dir = Path(__file__).parent
    jsonl_path = this_dir / "papers_with_pdfs.jsonl"

    if not jsonl_path.exists():
        logger.error(f"JSONL file not found: {jsonl_path}")
        logger.info(f"  Run: uv run python {this_dir}/prepare_papers.py")
        sys.exit(1)

    try:
        # Load papers from pre-prepared JSONL with PDF attachments
        from paper_scanner.core.models import Paper
        
        papers = []
        logger.info(f"Loading papers from JSONL: {jsonl_path}")
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip():
                    paper_dict = json.loads(line)
                    paper = Paper.model_validate(paper_dict)
                    papers.append(paper)
        
        logger.info(f"✓ Loaded {len(papers)} papers with PDF attachments")

        # Initialize pipeline
        pipeline = PDFEmbeddingPipeline(
            model_name=args.model,
            device=args.device,
            chunk_size=args.chunk_size,
            chunk_overlap=args.overlap,
        )

        # Load model and chunker
        pipeline.load_model()

        # Process papers
        logger.info("Starting PDF processing...")
        total_chunks = pipeline.process_papers(papers)

        logger.info(f"Processing complete. Generated {total_chunks} chunk embeddings.")

        # Print results
        print_results(pipeline, papers)

        logger.info("\n✓ PDF chunking & embedding test completed successfully!")

    except Exception as e:
        logger.error(f"✗ Pipeline test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
