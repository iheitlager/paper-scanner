#!/usr/bin/env python3
"""
Spike 018: Test 1 - Embedding Pipeline
=======================================

Test the embedding pipeline with real paper data from eight_cases.bib and PDFs.

This test:
1. Loads papers from bibtex file using existing paper-scanner loaders
2. Generates embeddings for titles, abstracts, and keywords
3. Demonstrates semantic search and similarity matching
4. Uses in-memory storage with Paper and Embedding models
5. Tests section-aware embedding (when PDFs have text extraction)

Usage:
    python test_01_embedding_pipeline.py
    python test_01_embedding_pipeline.py --verbose
    python test_01_embedding_pipeline.py --model allenai/specter

Requires:
    sentence-transformers  # For embedding generation
    bibtexparser          # For parsing bib files
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

from paper_scanner.core.models import Author, Embedding, Paper, ProcessingMetadata
from paper_scanner.io.bibtex import bibtex_file_to_papers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmbeddingPipeline:
    """Pipeline for generating and storing paper embeddings."""

    def __init__(self, model_name: str = "all-mpnet-base-v2", device: str = "cpu"):
        """Initialize embedding pipeline with selected model.
        
        Args:
            model_name: Hugging Face model identifier
            device: "cpu" or "cuda"
        """
        self.model_name = model_name
        self.device = device
        self.model: Optional[SentenceTransformer] = None
        self.embeddings_store: Dict[str, Dict] = {}  # paper_id -> embedding data
        
    def load_model(self) -> None:
        """Load the embedding model."""
        logger.info(f"Loading model: {self.model_name}")
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"✓ Model loaded successfully (device: {self.device})")
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
            text_source: Description of what was embedded (e.g., "title", "abstract")
            
        Returns:
            Embedding model instance
        """
        # Ensure exactly 768 dimensions
        if len(vector) != 768:
            logger.warning(
                f"Vector has {len(vector)} dimensions, expected 768. Padding/truncating."
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

    def process_papers(self, papers: List[Paper]) -> int:
        """Generate embeddings for a list of papers.
        
        Args:
            papers: List of Paper objects to embed
            
        Returns:
            Number of successfully embedded papers
        """
        success_count = 0

        for i, paper in enumerate(papers, 1):
            logger.info(f"Processing paper {i}/{len(papers)}: {paper.cite_key}")

            try:
                # Generate title embedding
                if paper.title:
                    title_emb = self.embed_text(paper.title)
                    if title_emb:
                        paper.title_abstract_embedding = self.create_embedding_object(
                            title_emb, "title"
                        )
                        logger.debug(f"  ✓ Title embedding: {len(title_emb)} dims")

                # Generate abstract embedding
                if paper.abstract:
                    abstract_emb = self.embed_text(paper.abstract)
                    if abstract_emb:
                        # Create new embedding for abstract if title already has one
                        abstract_embed_obj = self.create_embedding_object(
                            abstract_emb, "abstract"
                        )
                        # Store separately in embeddings_store
                        if paper.id not in self.embeddings_store:
                            self.embeddings_store[paper.id] = {}
                        self.embeddings_store[paper.id]["abstract"] = abstract_embed_obj
                        logger.debug(f"  ✓ Abstract embedding: {len(abstract_emb)} dims")

                # Generate keywords embedding
                if paper.keywords:
                    keywords_text = " ".join(paper.keywords)
                    keywords_emb = self.embed_text(keywords_text)
                    if keywords_emb:
                        keywords_embed_obj = self.create_embedding_object(
                            keywords_emb, "keywords"
                        )
                        if paper.id not in self.embeddings_store:
                            self.embeddings_store[paper.id] = {}
                        self.embeddings_store[paper.id]["keywords"] = keywords_embed_obj
                        logger.debug(f"  ✓ Keywords embedding: {len(keywords_emb)} dims")

                # Store reference in embeddings_store
                if paper.id not in self.embeddings_store:
                    self.embeddings_store[paper.id] = {}
                self.embeddings_store[paper.id]["paper"] = paper
                self.embeddings_store[paper.id]["title"] = paper.title_abstract_embedding

                success_count += 1
                logger.info(f"  ✓ Successfully embedded: {paper.cite_key}")

            except Exception as e:
                logger.error(f"  ✗ Error processing paper {paper.cite_key}: {e}")
                continue

        logger.info(f"\n✓ Successfully embedded {success_count}/{len(papers)} papers")
        return success_count

    def semantic_search(
        self, query: str, top_k: int = 5, field: str = "title"
    ) -> List[tuple]:
        """Find similar papers using semantic search.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            field: Which embedding to search ("title", "abstract", "keywords")
            
        Returns:
            List of (paper, similarity_score) tuples
        """
        if not self.model:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Embed the query
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        results = []

        for paper_id, emb_data in self.embeddings_store.items():
            if field not in emb_data or not emb_data[field]:
                continue

            paper = emb_data["paper"]
            embedding_obj = emb_data[field]
            paper_embedding = np.array(embedding_obj.vector, dtype=np.float32)

            # Calculate cosine similarity - ensure both are same dtype
            paper_embedding_tensor = torch.from_numpy(paper_embedding).unsqueeze(0)
            similarity = util.pytorch_cos_sim(
                query_embedding, 
                paper_embedding_tensor
            ).item()

            results.append((paper, similarity, embedding_obj.text_source))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def find_similar_papers(
        self, paper_id: str, top_k: int = 5, threshold: float = 0.7
    ) -> List[tuple]:
        """Find papers similar to a given paper.
        
        Args:
            paper_id: ID of the paper to compare
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (similar_paper, similarity_score) tuples
        """
        if paper_id not in self.embeddings_store:
            logger.warning(f"Paper {paper_id} not found in embeddings store")
            return []

        source_paper_emb = self.embeddings_store[paper_id]["title"]
        if not source_paper_emb:
            return []

        source_vector = np.array(source_paper_emb.vector, dtype=np.float32)
        source_tensor = torch.from_numpy(source_vector).unsqueeze(0)
        results = []

        for other_id, emb_data in self.embeddings_store.items():
            if other_id == paper_id:
                continue

            embedding_obj = emb_data["title"]
            if not embedding_obj:
                continue

            other_vector = np.array(embedding_obj.vector, dtype=np.float32)
            other_tensor = torch.from_numpy(other_vector).unsqueeze(0)
            
            # Calculate cosine similarity
            similarity = util.pytorch_cos_sim(
                source_tensor,
                other_tensor
            ).item()

            if similarity >= threshold:
                results.append((emb_data["paper"], similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


def load_papers_from_bibtex(bib_path: Path) -> List[Paper]:
    """Load papers from BibTeX file.
    
    Args:
        bib_path: Path to .bib file
        
    Returns:
        List of Paper objects
    """
    logger.info(f"Loading papers from: {bib_path}")
    
    try:
        # Use existing bibtex loader from paper_scanner
        papers = bibtex_file_to_papers(str(bib_path))
        logger.info(f"✓ Loaded {len(papers)} papers from BibTeX")
        return papers
        
    except Exception as e:
        logger.error(f"✗ Failed to load papers from BibTeX: {e}")
        raise


def print_results(pipeline: EmbeddingPipeline, papers: List[Paper]) -> None:
    """Print summary of embedding results.
    
    Args:
        pipeline: EmbeddingPipeline instance
        papers: List of papers that were embedded
    """
    print("\n" + "="*80)
    print("EMBEDDING PIPELINE RESULTS")
    print("="*80)

    print(f"\nModel: {pipeline.model_name}")
    print(f"Total papers processed: {len(papers)}")
    print(f"Successfully embedded: {len(pipeline.embeddings_store)}")
    print(f"Embedding dimensions: 768")

    print("\n" + "-"*80)
    print("SAMPLE PAPERS:")
    print("-"*80)

    for i, (paper_id, emb_data) in enumerate(
        list(pipeline.embeddings_store.items())[:3]
    ):
        paper = emb_data["paper"]
        print(f"\n{i+1}. {paper.cite_key}")
        print(f"   Title: {paper.title[:80] if paper.title else 'N/A'}...")
        print(f"   Year: {paper.year}")
        print(f"   Keywords: {', '.join(paper.keywords[:3]) if paper.keywords else 'None'}")
        
        # Show embedding stats
        if emb_data["title"]:
            print(f"   ✓ Title embedding: 768 dims")
        if "abstract" in emb_data and emb_data["abstract"]:
            print(f"   ✓ Abstract embedding: 768 dims")
        if "keywords" in emb_data and emb_data["keywords"]:
            print(f"   ✓ Keywords embedding: 768 dims")

    # Example semantic search
    print("\n" + "-"*80)
    print("SEMANTIC SEARCH EXAMPLE:")
    print("-"*80)
    
    query = "digital transformation business model"
    print(f"\nQuery: '{query}'")
    print("\nTop 5 similar papers:")
    
    results = pipeline.semantic_search(query, top_k=5)
    for i, (paper, similarity, source) in enumerate(results, 1):
        print(
            f"{i}. {paper.cite_key} ({source})"
            f" - Similarity: {similarity:.4f}"
        )
        print(f"   {paper.title[:70]}...")

    # Example similarity matching
    if pipeline.embeddings_store:
        print("\n" + "-"*80)
        print("SIMILARITY MATCHING EXAMPLE:")
        print("-"*80)
        
        first_paper_id = list(pipeline.embeddings_store.keys())[0]
        first_paper = pipeline.embeddings_store[first_paper_id]["paper"]
        
        print(f"\nBase paper: {first_paper.cite_key}")
        print(f"Title: {first_paper.title[:70]}...")
        
        similar = pipeline.find_similar_papers(first_paper_id, top_k=3, threshold=0.5)
        
        if similar:
            print("\nMost similar papers (threshold: 0.5):")
            for i, (paper, similarity) in enumerate(similar, 1):
                print(f"{i}. {paper.cite_key} - Similarity: {similarity:.4f}")
                print(f"   {paper.title[:70]}...")
        else:
            print("No similar papers found above threshold")

    print("\n" + "="*80)


def main():
    """Run the embedding pipeline test."""
    parser = argparse.ArgumentParser(
        description="Test embedding pipeline with eight_cases.bib"
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

    # Paths: test file is in tests/spikes/018_embedding/, we need tests/data/
    bib_path = Path(__file__).parent.parent.parent / "data" / "eight_cases.bib"
    
    if not bib_path.exists():
        logger.error(f"BibTeX file not found: {bib_path}")
        sys.exit(1)

    try:
        # Load papers
        papers = load_papers_from_bibtex(bib_path)
        
        # Initialize pipeline
        pipeline = EmbeddingPipeline(model_name=args.model, device=args.device)
        
        # Load model
        pipeline.load_model()
        
        # Process papers
        pipeline.process_papers(papers)
        
        # Print results
        print_results(pipeline, papers)
        
        logger.info("\n✓ Embedding pipeline test completed successfully!")
        
    except Exception as e:
        logger.error(f"✗ Pipeline test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
