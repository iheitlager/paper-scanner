#!/usr/bin/env python3
"""
Stage 1: Coarse Filter - Automated Keyword-Based Screening

This module implements the first stage of paper screening using keyword matching.
It evaluates papers based on hard exclusions and required keywords, then updates
the paper_screening table with results.

Goal: Remove obviously irrelevant papers with high recall (~95%) and acceptable
precision (~70%), allowing false positives to be filtered in later stages.

Usage:
    python stage1_keyword_screening.py [--db-url <url>] [--limit <n>] [--verbose]

    # Example:
    python stage1_keyword_screening.py \\
        --db-url postgresql://pdfuser:pdfuser@localhost/pdfdb \\
        --limit 100 \\
        --verbose
"""

import argparse
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extensions import connection as PsycopgConnection
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Stage1KeywordScreener:
    """Stage 1 keyword-based paper screening."""

    # Hard exclusion keywords (if ANY match -> EXCLUDE)
    HARD_EXCLUSIONS = [
        # Completely different domains
        'cancer', 'tumor', 'disease', 'patient', 'clinical',
        'quantum', 'physics', 'chemistry', 'biology',
        'agriculture', 'farming', 'crop',

        # Irrelevant contexts
        'school', 'student', 'education', 'teaching',
        'military', 'weapon', 'defense',

        # Wrong level of analysis - be more specific to avoid false positives
        'consumer behavior', 'household', 'personal use', 'consumer purchase'
    ]

    # Required keywords (need at least 2 of these to INCLUDE)
    REQUIRED_KEYWORDS = [
        # Innovation types
        'innovation', 'digital transformation', 'digitalization', 'technology adoption',
        'digital service innovation', 'service innovation', 'business model innovation',
        'radical innovation', 'business innovation', 'strategic innovation',

        # Organizational context
        'firm', 'company', 'organization', 'enterprise', 'incumbent',
        'organizational', 'business', 'corporate',

        # Supplier/partnership
        'supplier', 'vendor', 'partner', 'ecosystem', 'collaboration',

        # Methodology and analysis
        'qualitative comparative analysis', 'comparative analysis', 'configuration',
        'ambidexterity', 'ambidextrous', 'performance'
    ]

    def __init__(self, db_url: str):
        """Initialize the screener with database connection details.

        Args:
            db_url: PostgreSQL connection URL
        """
        self.db_url = db_url
        self.conn: Optional[PsycopgConnection] = None

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(self.db_url)
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

    def normalize_text(self, text: Optional[str]) -> str:
        """Normalize text for keyword matching.

        Args:
            text: Text to normalize

        Returns:
            Lowercase, whitespace-trimmed text
        """
        if not text:
            return ""
        return text.lower().strip()

    def check_keyword_match(self, text: str, keywords: List[str]) -> Tuple[List[str], int]:
        """Check which keywords match in text.

        Args:
            text: Text to search in (should be normalized)
            keywords: List of keywords to check

        Returns:
            Tuple of (matched_keywords, match_count)
        """
        matched = []
        for keyword in keywords:
            # Use word boundary matching to avoid partial matches
            # e.g., "supply" shouldn't match "supplier"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                matched.append(keyword)
        return matched, len(matched)

    def screen_paper(self, paper: Dict) -> Dict:
        """Perform Stage 1 screening on a single paper.

        Args:
            paper: Paper record from database

        Returns:
            Dictionary with screening results
        """
        paper_id = paper['id']
        title = self.normalize_text(paper.get('title'))
        abstract = self.normalize_text(paper.get('abstract', ''))

        # Combine title and abstract for evaluation
        combined_text = f"{title} {abstract}"

        # Check hard exclusions
        excluded_kw, excluded_count = self.check_keyword_match(
            combined_text, self.HARD_EXCLUSIONS
        )

        if excluded_count > 0:
            return {
                'paper_id': paper_id,
                'screening_stage': 'stage1_fail',
                'stage1_processed_at': datetime.now(),
                'stage1_score': 0,
                'stage1_exclusion_reason': f'Hard exclusion keywords detected: {", ".join(excluded_kw)}',
                'stage1_matched_keywords': [],
                'stage1_excluded_keywords': excluded_kw,
                'decision': 'exclude'
            }

        # Check required keywords
        required_kw, required_count = self.check_keyword_match(
            combined_text, self.REQUIRED_KEYWORDS
        )

        # Decision logic
        if required_count >= 2:
            decision = 'include'
            stage = 'stage1_pass'
            exclusion_reason = None
        else:
            decision = 'ambiguous'
            stage = 'stage1_pass'  # Pass to next stage if ambiguous
            exclusion_reason = f'Found {required_count}/2 required keywords: {", ".join(required_kw)}' if required_kw else 'No required keywords found'

        return {
            'paper_id': paper_id,
            'screening_stage': stage,
            'stage1_processed_at': datetime.now(),
            'stage1_score': required_count,
            'stage1_exclusion_reason': exclusion_reason,
            'stage1_matched_keywords': required_kw,
            'stage1_excluded_keywords': excluded_kw,
            'decision': decision
        }

    def get_unscreened_papers(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch papers that haven't been screened yet.

        Args:
            limit: Maximum number of papers to fetch

        Returns:
            List of paper records
        """
        query = """
        SELECT
            p.id,
            p.title,
            p.abstract,
            p.citekey,
            p.year,
            COALESCE(ps.screening_stage, 'unscreened') as current_stage
        FROM papers p
        LEFT JOIN paper_screening ps ON p.id = ps.paper_id
        WHERE ps.screening_stage IS NULL
           OR ps.screening_stage IN ('unscreened', 'stage0_pass', 'stage1_pass', 'stage1_fail')
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
            logger.error(f"Failed to fetch unscreened papers: {e}")
            raise

    def update_screening_results(self, results: List[Dict]) -> None:
        """Update paper_screening table with Stage 1 results.

        Args:
            results: List of screening results
        """
        cursor = self.conn.cursor()
        try:
            for result in results:
                paper_id = result['paper_id']

                # Use upsert (INSERT ... ON CONFLICT ... DO UPDATE)
                # to handle both new and existing records
                upsert_query = """
                INSERT INTO paper_screening (
                    paper_id,
                    screening_stage,
                    screening_stage_updated_at,
                    stage1_processed_at,
                    stage1_score,
                    stage1_exclusion_reason,
                    stage1_matched_keywords,
                    stage1_excluded_keywords,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (paper_id) DO UPDATE SET
                    screening_stage = EXCLUDED.screening_stage,
                    screening_stage_updated_at = EXCLUDED.screening_stage_updated_at,
                    stage1_processed_at = EXCLUDED.stage1_processed_at,
                    stage1_score = EXCLUDED.stage1_score,
                    stage1_exclusion_reason = EXCLUDED.stage1_exclusion_reason,
                    stage1_matched_keywords = EXCLUDED.stage1_matched_keywords,
                    stage1_excluded_keywords = EXCLUDED.stage1_excluded_keywords,
                    updated_at = CURRENT_TIMESTAMP
                WHERE EXCLUDED.stage1_processed_at > paper_screening.stage1_processed_at
                   OR paper_screening.stage1_processed_at IS NULL
                """

                cursor.execute(upsert_query, (
                    paper_id,
                    result['screening_stage'],
                    datetime.now(),
                    result['stage1_processed_at'],
                    result['stage1_score'],
                    result['stage1_exclusion_reason'],
                    result['stage1_matched_keywords'],
                    result['stage1_excluded_keywords'],
                    datetime.now(),
                    datetime.now()
                ))

            self.conn.commit()
            logger.info(f"Updated {len(results)} screening records")
        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to update screening results: {e}")
            raise

    def process_papers(self, limit: Optional[int] = None, verbose: bool = False) -> Dict:
        """Process all unscreened papers through Stage 1.

        Args:
            limit: Maximum number of papers to process
            verbose: Enable verbose logging

        Returns:
            Dictionary with processing statistics
        """
        logger.info("Starting Stage 1 keyword screening...")

        # Fetch unscreened papers
        papers = self.get_unscreened_papers(limit)
        logger.info(f"Found {len(papers)} papers to screen")

        if not papers:
            logger.info("No papers to screen")
            return {
                'total_processed': 0,
                'included': 0,
                'excluded': 0,
                'ambiguous': 0,
                'processing_time_seconds': 0
            }

        # Screen each paper
        results = []
        included_count = 0
        excluded_count = 0
        ambiguous_count = 0

        for idx, paper in enumerate(papers, 1):
            screening_result = self.screen_paper(paper)
            results.append(screening_result)

            decision = screening_result['decision']
            if decision == 'include':
                included_count += 1
            elif decision == 'exclude':
                excluded_count += 1
            else:
                ambiguous_count += 1

            if verbose:
                logger.info(
                    f"[{idx}/{len(papers)}] Paper {paper['citekey']}: "
                    f"{decision.upper()} (score: {screening_result['stage1_score']})"
                )

        # Update database
        self.update_screening_results(results)

        stats = {
            'total_processed': len(papers),
            'included': included_count,
            'excluded': excluded_count,
            'ambiguous': ambiguous_count,
        }

        logger.info(f"Screening complete: {included_count} included, {excluded_count} excluded, {ambiguous_count} ambiguous")

        return stats

    def print_sample_results(self, limit: int = 10) -> None:
        """Print sample screening results for review.

        Args:
            limit: Number of results to display
        """
        query = """
        SELECT
            p.citekey,
            p.title,
            ps.screening_stage,
            ps.stage1_score,
            ps.stage1_matched_keywords,
            ps.stage1_excluded_keywords,
            ps.stage1_exclusion_reason
        FROM papers p
        JOIN paper_screening ps ON p.id = ps.paper_id
        WHERE ps.stage1_processed_at IS NOT NULL
        ORDER BY ps.stage1_processed_at DESC
        LIMIT %s
        """

        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()

            print("\n" + "="*100)
            print("STAGE 1 SCREENING RESULTS (Recent)")
            print("="*100)

            for result in results:
                stage = result['screening_stage']
                citekey = result['citekey'] or "N/A"
                title = (result['title'] or "N/A")[:60]
                score = result['stage1_score']
                matched = result['stage1_matched_keywords'] or []
                excluded = result['stage1_excluded_keywords'] or []

                print(f"\n[{stage.upper()}] {citekey}")
                print(f"  Title: {title}...")
                print(f"  Score: {score}/3")
                if matched:
                    print(f"  Matched keywords: {', '.join(matched)}")
                if excluded:
                    print(f"  Excluded keywords: {', '.join(excluded)}")
                if result['stage1_exclusion_reason']:
                    print(f"  Reason: {result['stage1_exclusion_reason']}")

            print("\n" + "="*100 + "\n")

        except psycopg2.Error as e:
            logger.error(f"Failed to fetch sample results: {e}")


def main():
    """Command-line interface for Stage 1 screening."""
    parser = argparse.ArgumentParser(
        description='Stage 1: Coarse Filter - Automated Keyword-Based Screening',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process all unscreened papers
  python stage1_keyword_screening.py \\
    --db-url postgresql://pdfuser:pdfuser@localhost/pdfdb

  # Process limited sample with verbose output
  python stage1_keyword_screening.py \\
    --db-url postgresql://pdfuser:pdfuser@localhost/pdfdb \\
    --limit 50 \\
    --verbose

  # Show sample results from database
  python stage1_keyword_screening.py \\
    --db-url postgresql://pdfuser:pdfuser@localhost/pdfdb \\
    --show-results 20
        '''
    )

    parser.add_argument(
        '--db-url',
        default='postgresql://pdfuser:pdfpass@localhost:5432/pdfdb',
        help='PostgreSQL connection URL (default: localhost/pdfdb)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of papers to process (default: all)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--show-results',
        type=int,
        default=None,
        help='Show sample screening results (number to display)'
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    # Create screener
    screener = Stage1KeywordScreener(args.db_url)

    try:
        screener.connect()

        # Show results if requested
        if args.show_results:
            screener.print_sample_results(args.show_results)
            return

        # Process papers
        stats = screener.process_papers(limit=args.limit, verbose=args.verbose)

        # Print summary
        print("\n" + "="*60)
        print("STAGE 1 SCREENING SUMMARY")
        print("="*60)
        print(f"Total processed:  {stats['total_processed']}")
        print(f"Included:         {stats['included']} ({stats['included']*100//max(1, stats['total_processed'])}%)")
        print(f"Excluded:         {stats['excluded']} ({stats['excluded']*100//max(1, stats['total_processed'])}%)")
        print(f"Ambiguous:        {stats['ambiguous']} ({stats['ambiguous']*100//max(1, stats['total_processed'])}%)")
        print("="*60 + "\n")

        # Show sample results
        screener.print_sample_results(10)

    except Exception as e:
        logger.error(f"Failed: {e}")
        return 1
    finally:
        screener.disconnect()

    return 0


if __name__ == '__main__':
    exit(main())
