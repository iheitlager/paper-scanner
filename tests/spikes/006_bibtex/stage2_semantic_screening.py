#!/usr/bin/env python3
"""
Stage 2: Semantic Filter - Semi-Automated Embedding-Based Screening

This module implements the second stage of paper screening using embeddings.
It evaluates papers based on semantic similarity to the research question,
then updates the paper_screening table with results.

Goal: Use embeddings to find papers semantically similar to your topic
with high precision (~85%) and recall (~90%), filtering down from Stage 1
and identifying borderline cases for manual review.

Thresholds:
- >= 0.65: INCLUDE
- 0.55-0.65: MANUAL REVIEW (borderline)
- < 0.55: EXCLUDE

Usage:
    python stage2_semantic_screening.py [--db-url <url>] [--limit <n>] [--verbose] [--force-redo]

    # Example:
    python stage2_semantic_screening.py \\
        --db-url postgresql://pdfuser:pdfuser@localhost/pdfdb \\
        --limit 100 \\
        --verbose \\
        --force-redo
"""

import argparse
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extras import RealDictCursor
from scipy.spatial.distance import cosine
from sentence_transformers import SentenceTransformer

# Disable tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose output from sentence_transformers and transformers
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


class Stage2SemanticScreener:
    """Stage 2 semantic filtering using embeddings."""

    # Thresholds for classification
    THRESHOLD_INCLUDE = 0.65      # >= this → INCLUDE
    THRESHOLD_MANUAL_REVIEW = 0.55  # 0.55-0.65 → MANUAL REVIEW
    # < 0.55 → EXCLUDE

    # Research question for semantic filtering
    RESEARCH_QUESTION = """
    How do incumbent firms involve suppliers in their digital innovation
    processes? What mechanisms enable or hinder this collaboration?
    """

    def __init__(self, db_url: str, model_name: str = "all-mpnet-base-v2"):
        """Initialize the screener with database connection details.

        Args:
            db_url: PostgreSQL connection URL
            model_name: Sentence transformer model to use
        """
        self.db_url = db_url
        self.model_name = model_name
        self.conn: Optional[PsycopgConnection] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.rq_embedding: Optional[np.ndarray] = None

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            register_vector(self.conn)
            logger.info("Connected to database")
        except psycopg2.Error as e:
            error_msg = str(e)
            if 'Connection refused' in error_msg:
                logger.error("❌ Database connection failed: Server not running")
                logger.error("   Start PostgreSQL with: docker-compose up pdf-browser-db")
            elif 'password authentication failed' in error_msg:
                logger.error("❌ Database connection failed: Invalid credentials")
                logger.error("   Check your --db-url parameter")
            else:
                logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def load_embedding_model(self) -> SentenceTransformer:
        """Lazy load embedding model."""
        if self.embedding_model is None:
            logger.info(f"Loading embedding model: {self.model_name}...")
            self.embedding_model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded. Dimension: {self.embedding_model.get_sentence_embedding_dimension()}")
        return self.embedding_model

    def compute_research_question_embedding(self) -> np.ndarray:
        """Compute embedding for the research question."""
        if self.rq_embedding is None:
            model = self.load_embedding_model()
            logger.info("Computing research question embedding...")
            self.rq_embedding = model.encode(self.RESEARCH_QUESTION, convert_to_numpy=True, show_progress_bar=False)
            logger.info("Research question embedding computed")
        return self.rq_embedding

    def normalize_text(self, text: Optional[str]) -> str:
        """Normalize text for embedding.

        Args:
            text: Text to normalize

        Returns:
            Cleaned text
        """
        if not text:
            return ""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        return text.strip()

    def compute_paper_embedding(self, title: Optional[str], abstract: Optional[str]) -> np.ndarray:
        """Compute embedding for paper combining title and abstract.

        Args:
            title: Paper title
            abstract: Paper abstract

        Returns:
            Embedding vector
        """
        model = self.load_embedding_model()

        # Combine title and abstract
        title_text = self.normalize_text(title) if title else ""
        abstract_text = self.normalize_text(abstract) if abstract else ""

        combined_text = f"{title_text} {abstract_text}".strip()

        if not combined_text:
            logger.warning("Empty text for embedding, using placeholder")
            combined_text = "No title or abstract available"

        return model.encode(combined_text, convert_to_numpy=True, show_progress_bar=False)

    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1, where 1 is identical)
        """
        # Convert to 1D if needed
        if embedding1.ndim > 1:
            embedding1 = embedding1.flatten()
        if embedding2.ndim > 1:
            embedding2 = embedding2.flatten()

        # Cosine similarity = 1 - cosine_distance
        distance = cosine(embedding1, embedding2)
        similarity = 1 - distance

        # Clamp to [0, 1]
        return float(max(0, min(1, similarity)))

    def stage2_refined_filter(self, paper: Dict, base_similarity: float) -> Dict:
        """Stage 2: Refine with keywords as BOOST, not filter.

        MEDIUM PRECISION - narrow down candidates using semantic similarity
        with optional keyword boost for alignment enhancement.

        Args:
            paper: Paper record from database
            base_similarity: Base semantic similarity score from embeddings

        Returns:
            Dictionary with filtering results including:
            - passed: Boolean indicating if paper passes screening
            - method: Description of filtering method used
            - boosted_similarity: Final similarity score after boost
            - keyword_boost: Amount of boost applied
            - flag_for_llm: Boolean indicating if paper should be flagged for LLM review
        """
        # Check for strong keyword signals (if available)
        keyword_boost = 0.0
        boost_applied = False

        if paper.get('keywords'):
            required_terms = [
                'digital', 'innovation', 'transformation',
                'supplier', 'vendor', 'partner',
                'incumbent', 'firm', 'organization'
            ]

            keyword_text = ' '.join(paper['keywords']).lower()
            matches = sum(1 for term in required_terms if term in keyword_text)

            # Boost score if keywords align (max +0.10)
            keyword_boost = min(0.10, matches * 0.02)
            if keyword_boost > 0:
                boost_applied = True

        adjusted_similarity = base_similarity + keyword_boost

        # Decision thresholds
        if adjusted_similarity >= 0.60:
            return {
                'passed': True,
                'method': 'high_similarity',
                'boosted_similarity': round(adjusted_similarity, 4),
                'keyword_boost': round(keyword_boost, 4),
                'flag_for_llm': False
            }
        elif adjusted_similarity >= 0.50:
            return {
                'passed': True,
                'method': 'moderate_similarity_with_boost' if boost_applied else 'moderate_similarity',
                'boosted_similarity': round(adjusted_similarity, 4),
                'keyword_boost': round(keyword_boost, 4),
                'flag_for_llm': True
            }
        else:
            return {
                'passed': False,
                'method': 'insufficient_similarity',
                'boosted_similarity': round(adjusted_similarity, 4),
                'keyword_boost': round(keyword_boost, 4),
                'flag_for_llm': False
            }

    def classify_paper(self, similarity: float) -> Tuple[str, str, Optional[str]]:
        """Classify paper based on similarity score.

        Args:
            similarity: Similarity score (0-1)

        Returns:
            Tuple of (screening_stage, decision, exclusion_reason)
            - screening_stage: 'stage2_pass', 'stage2_review', 'stage2_fail'
            - decision: 'include', 'manual_review', 'exclude'
            - exclusion_reason: Reason if excluded, else None
        """
        if similarity >= self.THRESHOLD_INCLUDE:
            return 'stage2_pass', 'include', None
        elif similarity >= self.THRESHOLD_MANUAL_REVIEW:
            return 'stage2_review', 'manual_review', \
                   f'Borderline similarity ({similarity:.4f}): manual review required'
        else:
            return 'stage2_fail', 'exclude', \
                   f'Low semantic similarity ({similarity:.4f}) to research question'

    def screen_paper(self, paper: Dict) -> Dict:
        """Perform Stage 2 screening on a single paper.

        Args:
            paper: Paper record from database

        Returns:
            Dictionary with screening results
        """
        paper_id = paper['id']
        title = paper.get('title')
        abstract = paper.get('abstract')

        # Compute embeddings
        rq_embedding = self.compute_research_question_embedding()
        paper_embedding = self.compute_paper_embedding(title, abstract)

        # Calculate similarity
        similarity = self.compute_similarity(rq_embedding, paper_embedding)

        # Classify
        screening_stage, decision, exclusion_reason = self.classify_paper(similarity)

        # Determine manual review flags
        needs_manual_review = (decision == 'manual_review')
        manual_review_reason = exclusion_reason if needs_manual_review else None

        return {
            'paper_id': paper_id,
            'screening_stage': screening_stage,
            'stage2_processed_at': datetime.now(),
            'semantic_similarity': round(float(similarity), 4),
            'semantic_embedding': paper_embedding.tolist(),  # Store for reuse
            'stage2_exclusion_reason': exclusion_reason,
            'needs_manual_review': needs_manual_review,
            'manual_review_reason': manual_review_reason,
            'decision': decision
        }

    def get_stage1_passed_papers(self, limit: Optional[int] = None, force_redo: bool = False) -> List[Dict]:
        """Fetch papers that passed Stage 1 and need Stage 2 screening.

        Args:
            limit: Maximum number of papers to fetch
            force_redo: If True, reprocess papers even if Stage 2 already done

        Returns:
            List of paper records
        """
        if force_redo:
            # Get all papers that passed Stage 1
            query = """
            SELECT
                p.id,
                p.title,
                p.abstract,
                p.citekey,
                p.year,
                ps.screening_stage,
                ps.semantic_similarity
            FROM papers p
            LEFT JOIN paper_screening ps ON p.id = ps.paper_id
            WHERE ps.screening_stage IN ('stage1_pass', 'unscreened')
               OR ps.screening_stage LIKE 'stage2_%'
            ORDER BY p.id
            """
        else:
            # Get only papers that haven't been screened with Stage 2 yet
            query = """
            SELECT
                p.id,
                p.title,
                p.abstract,
                p.citekey,
                p.year,
                ps.screening_stage,
                ps.semantic_similarity
            FROM papers p
            LEFT JOIN paper_screening ps ON p.id = ps.paper_id
            WHERE ps.screening_stage IS NULL
               OR ps.screening_stage = 'stage1_pass'
            ORDER BY p.id
            """

        if limit:
            query += f" LIMIT {limit}"

        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
        except psycopg2.Error as e:
            logger.error(f"Failed to fetch Stage 1 passed papers: {e}")
            raise

    def update_screening_results(self, results: List[Dict]) -> None:
        """Update paper_screening table with Stage 2 results.

        Args:
            results: List of screening results
        """
        cursor = self.conn.cursor()
        try:
            for result in results:
                paper_id = result['paper_id']
                semantic_similarity = result['semantic_similarity']
                screening_stage = result['screening_stage']
                stage2_exclusion_reason = result['stage2_exclusion_reason']
                needs_manual_review = result['needs_manual_review']
                manual_review_reason = result['manual_review_reason']
                stage2_processed_at = result['stage2_processed_at']
                semantic_embedding = result['semantic_embedding']

                # Use upsert (INSERT ... ON CONFLICT ... DO UPDATE)
                upsert_query = """
                INSERT INTO paper_screening (
                    paper_id,
                    screening_stage,
                    screening_stage_updated_at,
                    stage2_processed_at,
                    semantic_similarity,
                    stage2_exclusion_reason,
                    semantic_embedding,
                    needs_manual_review,
                    manual_review_reason,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id)
                DO UPDATE SET
                    screening_stage = EXCLUDED.screening_stage,
                    screening_stage_updated_at = EXCLUDED.screening_stage_updated_at,
                    stage2_processed_at = EXCLUDED.stage2_processed_at,
                    semantic_similarity = EXCLUDED.semantic_similarity,
                    stage2_exclusion_reason = EXCLUDED.stage2_exclusion_reason,
                    semantic_embedding = EXCLUDED.semantic_embedding,
                    needs_manual_review = EXCLUDED.needs_manual_review,
                    manual_review_reason = EXCLUDED.manual_review_reason,
                    updated_at = EXCLUDED.updated_at
                """

                try:
                    # Convert embedding to string format for pgvector
                    embedding_str = '[' + ','.join(map(str, semantic_embedding)) + ']'

                    cursor.execute(upsert_query, (
                        paper_id,
                        screening_stage,
                        datetime.now(),
                        stage2_processed_at,
                        semantic_similarity,
                        stage2_exclusion_reason,
                        embedding_str,
                        needs_manual_review,
                        manual_review_reason,
                        datetime.now()
                    ))

                except psycopg2.Error as e:
                    logger.error(f"Failed to update paper {paper_id}: {e}")
                    self.conn.rollback()
                    raise

            self.conn.commit()
            logger.info(f"Successfully updated {len(results)} screening records")

        except psycopg2.Error as e:
            logger.error(f"Failed to update screening results: {e}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def get_screening_summary(self) -> Dict:
        """Get summary statistics of screening results.

        Returns:
            Dictionary with summary statistics
        """
        query = """
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN screening_stage = 'stage2_pass' THEN 1 END) as included,
            COUNT(CASE WHEN screening_stage = 'stage2_fail' THEN 1 END) as excluded,
            COUNT(CASE WHEN screening_stage = 'stage2_review' THEN 1 END) as manual_review,
            ROUND(AVG(CASE WHEN semantic_similarity IS NOT NULL THEN semantic_similarity END)::numeric, 4) as avg_similarity,
            MIN(CASE WHEN semantic_similarity IS NOT NULL THEN semantic_similarity END) as min_similarity,
            MAX(CASE WHEN semantic_similarity IS NOT NULL THEN semantic_similarity END) as max_similarity,
            COUNT(CASE WHEN stage2_processed_at IS NOT NULL THEN 1 END) as stage2_processed
        FROM paper_screening
        WHERE stage2_processed_at IS NOT NULL
        """

        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            return result if result else {}
        except psycopg2.Error as e:
            logger.error(f"Failed to get screening summary: {e}")
            return {}

    def run(self, limit: Optional[int] = None, force_redo: bool = False, verbose: bool = False) -> None:
        """Run Stage 2 screening on papers.

        Args:
            limit: Maximum number of papers to screen
            force_redo: If True, reprocess papers even if Stage 2 already done
            verbose: If True, print detailed progress
        """
        try:
            self.connect()

            # Fetch papers to screen
            logger.info("Fetching papers for Stage 2 screening...")
            papers = self.get_stage1_passed_papers(limit=limit, force_redo=force_redo)

            if not papers:
                logger.info("No papers to screen")
                return

            logger.info(f"Found {len(papers)} papers to screen")

            # Screen papers
            results = []
            for i, paper in enumerate(papers, 1):
                if verbose:
                    logger.info(f"[{i}/{len(papers)}] Screening: {paper['citekey']} ({paper['year']})")

                try:
                    result = self.screen_paper(paper)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error screening paper {paper['id']}: {e}")
                    continue

            # Update database
            logger.info(f"Updating database with {len(results)} results...")
            self.update_screening_results(results)

            # Print summary
            summary = self.get_screening_summary()
            logger.info("=== Stage 2 Screening Summary ===")
            logger.info(f"Total papers processed: {summary.get('total', 0)}")
            logger.info(f"Included (>= 0.65): {summary.get('included', 0)}")
            logger.info(f"Manual review (0.55-0.65): {summary.get('manual_review', 0)}")
            logger.info(f"Excluded (< 0.55): {summary.get('excluded', 0)}")
            logger.info(f"Average similarity: {summary.get('avg_similarity', 0):.4f}")
            logger.info(f"Similarity range: {summary.get('min_similarity', 0):.4f} - {summary.get('max_similarity', 0):.4f}")

        finally:
            self.disconnect()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Stage 2: Semantic Filter - Embedding-based paper screening"
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"),
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--model",
        default="all-mpnet-base-v2",
        help="Sentence transformer model to use (default: all-mpnet-base-v2)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of papers to process"
    )
    parser.add_argument(
        "--force-redo",
        action="store_true",
        help="Reprocess papers even if Stage 2 already done"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Run screening
    screener = Stage2SemanticScreener(args.db_url, model_name=args.model)
    screener.run(limit=args.limit, force_redo=args.force_redo, verbose=args.verbose)


if __name__ == "__main__":
    main()
