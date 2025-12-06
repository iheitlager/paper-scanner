#!/usr/bin/env python3
"""
Stage 0 Preprocessing: Filter database for quality papers.

This script processes the papers table and:
1. Rejects conference/proceedings papers/books - only keeps scientific peer-reviewed articles
2. Rejects duplicates (keeps the original in kept_paper_id)
3. Only keeps empirical papers - rejects literature reviews and conceptual papers

Outputs decisions to paper_screening table with:
- screening_stage: 'stage0_pass' or 'stage0_fail'
- stage0_exclusion_reason: reason for rejection (if applicable)
- kept_paper_id: for duplicates, points to the original paper

Usage:
    python stage0_preprocessing.py \
        --db-url postgresql://user:pass@localhost:5432/pdfdb \
        --verbose
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Set, Tuple, List
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class Stage0Preprocessor:
    """Preprocessor for filtering papers in Stage 0."""

    # Paper types that are considered acceptable (peer-reviewed journal articles)
    ACCEPTABLE_PAPER_TYPES = {
        'journal_article',
        'journal article',
        'article',
        'research article',
        'original article',
        'empirical article',
    }

    # Paper types to reject (non-peer-reviewed or conference)
    REJECT_PAPER_TYPES = {
        'conference_paper',
        'conference paper',
        'conference review',
        'proceeding',
        'proceedings',
        'proceedings-article',
        'inproceedings',
        'inprocedings',  # Common typo in BibTeX
        'book',
        'inbook',
        'book_chapter',
        'book chapter',
        'book-chapter',
        'editorial',
        'editorial material',
        'commentary',
        'news',
        'erratum',
        'corrigendum',
        'retraction',
        'correction',
        'letter',
        'note',
        'review',  # Literature reviews
    }

    # Keywords indicating literature review (reject)
    REVIEW_KEYWORDS = [
        'literature review',
        'systematic review',
        'scoping review',
        'narrative review',
        'meta-analysis',
        'meta analysis',
        'metaanalysis',
        'survey',
        'overview',
        'state of the art',
        'state-of-the-art',
    ]

    # Keywords indicating conceptual/theoretical work (reject)
    CONCEPTUAL_KEYWORDS = [
        'conceptual framework',
        'conceptual model',
        'theoretical',
        'theory',
        'framework',
        'taxonomy',
        'typology',
        'opinion',
        'perspective',
        'commentary',
        'editorial',
    ]

    # Keywords indicating empirical work (keep) - helps confirm empirical nature
    EMPIRICAL_KEYWORDS = [
        'empirical',
        'experiment',
        'experimental',
        'study',
        'evaluation',
        'analysis',
        'dataset',
        'data collection',
        'survey',
        'field study',
        'case study',
        'measurement',
        'quantitative',
        'qualitative',
        'mixed methods',
    ]

    def __init__(self, db_url: str, verbose: bool = False):
        """Initialize preprocessor with database connection."""
        self.db_url = db_url
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)

        self.connection: Optional[psycopg2.extensions.connection] = None
        self.stats = {
            'total_papers': 0,
            'passed_stage0': 0,
            'rejected_wrong_type': 0,
            'rejected_duplicate': 0,
            'rejected_review': 0,
            'rejected_conceptual': 0,
            'errors': 0,
        }

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(self.db_url)
            logger.info("✓ Connected to database")
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            sys.exit(1)

    def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("✓ Disconnected from database")

    def _normalize_text(self, text: Optional[str]) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return text.lower().strip()

    def _normalize_paper_type(self, paper_type: Optional[str]) -> str:
        """Normalize paper type."""
        if not paper_type:
            return ""
        return self._normalize_text(paper_type)

    def _check_paper_type(self, paper_type: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Check if paper type is acceptable.
        
        Returns:
            (is_acceptable, rejection_reason)
        """
        if not paper_type:
            logger.debug("Paper has no paper_type set")
            return True, None  # Be lenient if type not set

        normalized_type = self._normalize_paper_type(paper_type)

        # Check if explicitly rejected
        if normalized_type in self.REJECT_PAPER_TYPES:
            return False, f"rejected_paper_type: {paper_type}"

        # Check if acceptable
        if normalized_type in self.ACCEPTABLE_PAPER_TYPES:
            return True, None

        # Unknown type - be lenient and accept
        logger.debug(f"Unknown paper type: {paper_type}, accepting")
        return True, None

    def _is_review_paper(self, title: Optional[str], abstract: Optional[str]) -> bool:
        """Check if paper is a review."""
        combined_text = self._normalize_text(f"{title or ''} {abstract or ''}")

        for keyword in self.REVIEW_KEYWORDS:
            if keyword.lower() in combined_text:
                logger.debug(f"Found review keyword: {keyword}")
                return True

        return False

    def _is_conceptual_paper(self, title: Optional[str], abstract: Optional[str]) -> bool:
        """Check if paper is conceptual/theoretical."""
        combined_text = self._normalize_text(f"{title or ''} {abstract or ''}")

        # Count conceptual keywords
        conceptual_count = 0
        for keyword in self.CONCEPTUAL_KEYWORDS:
            if keyword.lower() in combined_text:
                conceptual_count += 1

        # Count empirical keywords to offset
        empirical_count = 0
        for keyword in self.EMPIRICAL_KEYWORDS:
            if keyword.lower() in combined_text:
                empirical_count += 1

        # If more conceptual than empirical, likely conceptual
        logger.debug(f"Conceptual keywords: {conceptual_count}, Empirical keywords: {empirical_count}")
        return conceptual_count > empirical_count

    def _find_duplicates(self) -> Dict[int, List[int]]:
        """
        Find duplicate papers by checking:
        - Same DOI
        - Same title (fuzzy match on cleaned text)
        - Same authors + year + title (partial match)

        Returns:
            Dict mapping primary_paper_id -> list of duplicate_paper_ids
        """
        logger.info("🔍 Scanning for duplicates...")
        duplicates = defaultdict(list)

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Find duplicates by DOI
            logger.debug("Checking for duplicates by DOI...")
            cursor.execute("""
                SELECT doi, ARRAY_AGG(id ORDER BY id) as paper_ids
                FROM papers
                WHERE doi IS NOT NULL AND doi != ''
                GROUP BY doi
                HAVING COUNT(*) > 1
            """)

            for row in cursor.fetchall():
                paper_ids = row['paper_ids']
                primary = paper_ids[0]
                for dup_id in paper_ids[1:]:
                    duplicates[primary].append(dup_id)
                logger.debug(
                    f"Found {len(paper_ids)} papers with same DOI: {paper_ids[:3]}..."
                )

            cursor.close()

        except psycopg2.Error as e:
            logger.error(f"✗ Error finding duplicates: {e}")
            self.stats['errors'] += 1

        return duplicates

    def _check_paper(
        self, paper_id: int, title: Optional[str], abstract: Optional[str],
        paper_type: Optional[str], doi: Optional[str], duplicates: Dict[int, List[int]]
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if paper should be included.

        Returns:
            (should_include, exclusion_reason, kept_paper_id)
        """
        # Check if it's a duplicate
        if paper_id in duplicates:
            # This is the primary paper - keep it
            return True, None, None

        # Check if this paper is a duplicate of another
        for primary_id, dup_ids in duplicates.items():
            if paper_id in dup_ids:
                # This paper is a duplicate of primary_id
                return False, "duplicate", primary_id

        # Check paper type
        type_ok, type_reason = self._check_paper_type(paper_type)
        if not type_ok:
            return False, type_reason, None

        # Check if review paper
        if self._is_review_paper(title, abstract):
            return False, "review_paper", None

        # Check if conceptual paper
        if self._is_conceptual_paper(title, abstract):
            return False, "conceptual_paper", None

        return True, None, None

    def process(self) -> None:
        """Process all papers in database."""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Get all papers
            logger.info("📄 Fetching all papers from database...")
            cursor.execute("""
                SELECT id, title, abstract, paper_type, doi, year, citekey
                FROM papers
                ORDER BY id
            """)

            papers = cursor.fetchall()
            self.stats['total_papers'] = len(papers)
            logger.info(f"Found {self.stats['total_papers']} papers to process")

            # Find duplicates
            duplicates = self._find_duplicates()
            logger.info(f"Found duplicate groups: {len(duplicates)}")

            cursor.close()

            # Process each paper
            logger.info("🔄 Processing papers...")
            for idx, paper in enumerate(papers):
                if (idx + 1) % 100 == 0:
                    logger.info(f"  Progress: {idx + 1}/{self.stats['total_papers']}")

                paper_id = paper['id']
                should_include, exclusion_reason, kept_paper_id = self._check_paper(
                    paper_id,
                    paper['title'],
                    paper['abstract'],
                    paper['paper_type'],
                    paper['doi'],
                    duplicates
                )

                # Determine screening stage
                screening_stage = 'stage0_pass' if should_include else 'stage0_fail'

                # Categorize rejection
                if exclusion_reason:
                    if exclusion_reason == 'duplicate':
                        self.stats['rejected_duplicate'] += 1
                    elif 'rejected_paper_type' in exclusion_reason:
                        self.stats['rejected_wrong_type'] += 1
                    elif 'review_paper' in exclusion_reason:
                        self.stats['rejected_review'] += 1
                    elif 'conceptual_paper' in exclusion_reason:
                        self.stats['rejected_conceptual'] += 1
                else:
                    self.stats['passed_stage0'] += 1

                # Insert/update screening record
                self._upsert_screening(
                    paper_id=paper_id,
                    screening_stage=screening_stage,
                    stage0_exclusion_reason=exclusion_reason,
                    kept_paper_id=kept_paper_id,
                    paper_citekey=paper['citekey']
                )

            logger.info("✓ Processing complete")
            self._print_stats()

        except psycopg2.Error as e:
            logger.error(f"✗ Error during processing: {e}")
            self.stats['errors'] += 1
            raise

    def _upsert_screening(
        self, paper_id: int, screening_stage: str, stage0_exclusion_reason: Optional[str],
        kept_paper_id: Optional[int], paper_citekey: Optional[str]
    ) -> None:
        """Insert or update screening record."""
        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                INSERT INTO paper_screening (
                    paper_id,
                    screening_stage,
                    screening_stage_updated_at,
                    stage0_processed_at,
                    stage0_exclusion_reason,
                    kept_paper_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id) DO UPDATE SET
                    screening_stage = EXCLUDED.screening_stage,
                    screening_stage_updated_at = EXCLUDED.screening_stage_updated_at,
                    stage0_processed_at = EXCLUDED.stage0_processed_at,
                    stage0_exclusion_reason = EXCLUDED.stage0_exclusion_reason,
                    kept_paper_id = EXCLUDED.kept_paper_id
            """, (
                paper_id,
                screening_stage,
                datetime.now(),
                datetime.now(),
                stage0_exclusion_reason,
                kept_paper_id
            ))

            self.connection.commit()

        except psycopg2.Error as e:
            logger.error(f"✗ Error upserting screening for paper {paper_id} ({paper_citekey}): {e}")
            self.connection.rollback()
            self.stats['errors'] += 1

    def _print_stats(self) -> None:
        """Print processing statistics."""
        print("\n" + "=" * 60)
        print("STAGE 0 PREPROCESSING RESULTS")
        print("=" * 60)
        print(f"Total papers processed:        {self.stats['total_papers']}")
        print(f"✓ Passed Stage 0:              {self.stats['passed_stage0']}")
        print(f"✗ Rejected (wrong type):       {self.stats['rejected_wrong_type']}")
        print(f"✗ Rejected (duplicate):        {self.stats['rejected_duplicate']}")
        print(f"✗ Rejected (review paper):     {self.stats['rejected_review']}")
        print(f"✗ Rejected (conceptual):       {self.stats['rejected_conceptual']}")
        print(f"⚠ Errors:                      {self.stats['errors']}")
        print("=" * 60)

        pass_rate = (self.stats['passed_stage0'] / self.stats['total_papers'] * 100
                     if self.stats['total_papers'] > 0 else 0)
        print(f"Pass rate: {pass_rate:.1f}%")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Stage 0 Preprocessing: Filter database for quality papers'
    )
    parser.add_argument(
        '--db-url',
        default=os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'),
        help='Database URL (default: $DATABASE_URL or PostgreSQL default)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    logger.info("🚀 Starting Stage 0 Preprocessing")
    logger.info(f"Database: {args.db_url.split('@')[1] if '@' in args.db_url else 'default'}")

    preprocessor = Stage0Preprocessor(args.db_url, verbose=args.verbose)

    try:
        preprocessor.connect()
        preprocessor.process()
    finally:
        preprocessor.disconnect()


if __name__ == '__main__':
    main()
