#!/usr/bin/env python3
"""
Fetch references from Crossref for papers in screening stages.

This script:
1. Finds papers with DOIs in screening stages 'stage2_pass' or 'stage2_review'
2. Fetches their references using the Crossref API
3. Loads referenced papers as new records with source_type='crossref'
4. Creates citation edges linking the original papers to the new references
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from paper_scanner.tools.cache import JSONFileCache
from psycopg2.extras import RealDictCursor
from rich.console import Console
from rich.logging import RichHandler

from paper_scanner import __version__
from paper_scanner.tools.fetchers import CROSSREF_EMAIL, CrossrefReferenceFetcher

# Configure rich console with colored output
console = Console()

# Configure cache directory (will be set by main or use default)
_cache_instance = JSONFileCache()

# Configure rich logging with colors and better formatting
import logging


# Create custom RichHandler that shows path only in verbose mode
class VerboseRichHandler(RichHandler):
    def __init__(self, *args, show_path=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_path = show_path

    def emit(self, record):
        # Hide level name and path by default
        if not self.show_path:
            record.levelname = ""
        super().emit(record)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[VerboseRichHandler(console=console, rich_tracebacks=True, show_time=False, show_path=False)]
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# Store handler reference to update later
_log_handler = logging.getLogger(__name__).handlers[0] if logging.getLogger(__name__).handlers else None


# Crossref API configuration for fair use / polite pool
# (See paper_scanner.tools.fetchers.crossref_fetcher for implementations)


class VerboseRichHandler(RichHandler):
    def __init__(self, *args, show_path=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_path = show_path

    def emit(self, record):
        # Hide level name and path by default
        if not self.show_path:
            record.levelname = ""
        super().emit(record)


logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[VerboseRichHandler(console=console, rich_tracebacks=True, show_time=False, show_path=False)]
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# Store handler reference to update later
_log_handler = logging.getLogger(__name__).handlers[0] if logging.getLogger(__name__).handlers else None


# Crossref fetchers are now in paper_scanner.tools.fetchers.crossref_fetcher
class CrossrefReferenceLoader:
    """Load Crossref references into the database"""

    def __init__(self, db_url: str, try_mode: bool = False, cache_dir: Optional[Path] = None):
        """
        Initialize database loader

        Args:
            db_url: PostgreSQL connection URL
            try_mode: If True, scan without uploading to database
            cache_dir: Directory for caching API responses (optional)
        """
        self.db_url = db_url
        self.fetcher = CrossrefReferenceFetcher(cache_dir=cache_dir)
        self.verbose = False
        self.try_mode = try_mode
        self.export_errors_path = None
        self.not_found_records = []  # Track papers with missing/failed references
        self.stats = {
            'papers_processed': 0,
            'papers_with_references': 0,
            'total_references_found': 0,
            'new_papers_created': 0,
            'citation_edges_created': 0,
            'papers_skipped': 0,
            'errors': 0
        }

    def format_apa(self, reference: Dict[str, Any]) -> str:
        """Format a reference in APA style"""
        authors = []
        if reference.get('authors_json'):
            try:
                authors_list = json.loads(reference['authors_json'])
                for author in authors_list:
                    last_name = author.get('last_name', '')
                    initials = author.get('initials', '')
                    if last_name:
                        if initials:
                            authors.append(f"{last_name}, {initials}.")
                        else:
                            authors.append(last_name)
            except (json.JSONDecodeError, TypeError):
                pass

        # Build APA citation
        apa_parts = []

        # Authors
        if authors:
            if len(authors) == 1:
                apa_parts.append(authors[0])
            elif len(authors) == 2:
                apa_parts.append(f"{authors[0]}, & {authors[1]}")
            else:
                apa_parts.append(f"{authors[0]}, et al.")

        # Year
        year = reference.get('year')
        if year:
            apa_parts.append(f"({year})")

        # Title
        title = reference.get('title')
        if title:
            apa_parts.append(f"{title}.")

        # Journal/Publisher
        journal = reference.get('journal')
        if journal:
            apa_parts.append(f"*{journal}*")

        # Volume and issue
        volume = reference.get('volume')
        issue = reference.get('issue')
        if volume:
            if issue:
                apa_parts.append(f"{volume}({issue})")
            else:
                apa_parts.append(f"{volume}")

        # DOI
        doi = reference.get('doi')
        if doi:
            apa_parts.append(f"https://doi.org/{doi}")

        return " ".join(apa_parts)

    def connect(self) -> psycopg2.extensions.connection:
        """Get database connection"""
        try:
            return psycopg2.connect(self.db_url)
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def get_papers_for_processing(self) -> List[Dict[str, Any]]:
        """
        Get papers with DOIs in stages 'stage2_pass' or 'stage2_review'

        Returns:
            List of paper records
        """
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # First, get count of eligible papers
            eligible_query = """
                SELECT COUNT(*) as count
                FROM papers p
                JOIN paper_screening ps ON p.id = ps.paper_id
                WHERE ps.screening_stage IN ('stage2_pass', 'stage2_review')
            """
            cursor.execute(eligible_query)
            eligible_count = cursor.fetchone()['count']

            # Then get papers with DOIs
            query = """
                SELECT
                    p.id,
                    p.citekey,
                    p.title,
                    p.doi,
                    p.year,
                    p.authors,
                    ps.screening_stage,
                    ps.semantic_similarity
                FROM papers p
                JOIN paper_screening ps ON p.id = ps.paper_id
                WHERE p.doi IS NOT NULL
                  AND ps.screening_stage IN ('stage2_pass', 'stage2_review')
                ORDER BY ps.semantic_similarity DESC, p.year DESC
            """

            cursor.execute(query)
            papers = cursor.fetchall()

            console.print(f"Base paper set: {eligible_count} eligible papers")
            console.print(f"Papers with DOIs: {len(papers)} papers ready for processing")
            return papers

        finally:
            cursor.close()
            conn.close()

    def insert_referenced_paper(self, conn: psycopg2.extensions.connection, reference: Dict[str, Any],
                                source_paper_id: int) -> Optional[int]:
        """
        Insert a referenced paper as a new paper record

        Args:
            conn: Database connection
            reference: Parsed reference data
            source_paper_id: ID of the source paper

        Returns:
            ID of the inserted paper, or None if insert fails
        """
        if self.try_mode:
            # In try_mode, just return a dummy ID for testing
            self.stats['new_papers_created'] += 1
            return 999999

        cursor = conn.cursor()

        try:
            # Create citekey if not present
            citekey = reference.get('citekey')
            if not citekey:
                # Generate from author + year
                first_author = None
                if reference.get('authors_json'):
                    authors = json.loads(reference['authors_json'])
                    if authors and authors[0].get('last_name'):
                        first_author = authors[0]['last_name']

                if first_author and reference.get('year'):
                    citekey = f"{first_author}_{reference['year']}"
                else:
                    citekey = f"ref_{source_paper_id}_{int(time.time())}"

            # Check if paper already exists by DOI
            if reference.get('doi'):
                cursor.execute(
                    "SELECT id FROM papers WHERE doi = %s AND source_type = 'crossref'",
                    (reference['doi'],)
                )
                existing = cursor.fetchone()
                if existing:
                    return existing[0]

            # Insert new paper record
            cursor.execute(
                """
                INSERT INTO papers (
                    citekey, title, year, authors, doi, abstract, paper_type,
                    source_type, processing_status,
                    metadata_extracted_at, indexed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (
                    citekey,
                    reference.get('title'),
                    reference.get('year'),
                    reference.get('authors_json'),
                    reference.get('doi'),
                    reference.get('abstract'),
                    reference.get('paper_type'),
                    'crossref',
                    'metadata_extracted'
                )
            )

            result = cursor.fetchone()
            if result:
                paper_id = result[0]
                if self.verbose:
                    logger.debug(f"Inserted referenced paper: {citekey} (ID: {paper_id})")
                self.stats['new_papers_created'] += 1
                return paper_id
            else:
                return None

        except Exception as e:
            logger.warning(f"Error inserting referenced paper: {e}")
            self.stats['errors'] += 1
            # Rollback the transaction to clear the error state
            try:
                conn.rollback()
            except:
                pass
            return None
        finally:
            cursor.close()

    def create_citation_edge(self, conn: psycopg2.extensions.connection,
                            source_paper_id: int, cited_paper_id: int) -> bool:
        """
        Create a citation edge linking source to cited paper

        Args:
            conn: Database connection
            source_paper_id: ID of citing paper
            cited_paper_id: ID of cited paper

        Returns:
            True if successful
        """
        if self.try_mode:
            # In try_mode, skip actual insertion
            self.stats['citation_edges_created'] += 1
            return True

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO citation_edges (citing_paper_id, cited_paper_id)
                VALUES (%s, %s)
                ON CONFLICT (citing_paper_id, cited_paper_id) DO NOTHING
                """,
                (source_paper_id, cited_paper_id)
            )

            if cursor.rowcount > 0:
                self.stats['citation_edges_created'] += 1
                return True
            return False

        except Exception as e:
            logger.warning(f"Error creating citation edge: {e}")
            return False
        finally:
            cursor.close()

    def _format_paper_apa(self, paper: Dict[str, Any]) -> str:
        """
        Format a paper record in APA style

        Args:
            paper: Paper record from database

        Returns:
            APA formatted citation string
        """
        authors = []
        if paper.get('authors'):
            try:
                authors_list = json.loads(paper['authors'])
                for author in authors_list:
                    last_name = author.get('last_name', '')
                    initials = author.get('initials', '')
                    if last_name:
                        if initials:
                            authors.append(f"{last_name}, {initials}.")
                        else:
                            authors.append(last_name)
            except (json.JSONDecodeError, TypeError):
                pass

        apa_parts = []

        # Authors
        if authors:
            if len(authors) == 1:
                apa_parts.append(authors[0])
            elif len(authors) == 2:
                apa_parts.append(f"{authors[0]}, & {authors[1]}")
            else:
                apa_parts.append(f"{authors[0]}, et al.")

        # Year
        year = paper.get('year')
        if year:
            apa_parts.append(f"({year})")

        # Title
        title = paper.get('title')
        if title:
            apa_parts.append(f"{title}.")

        return " ".join(apa_parts)

    def resolve_references_hierarchical(self, references: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hierarchically resolve references:
        1. Those without DOI: use parsed data directly
        2. Those with DOI: fetch full metadata from Crossref

        This function does NOT process references, only resolves and categorizes them.

        Args:
            references: List of references from Crossref

        Returns:
            Dict with 'direct' and 'crossref' reference lists
        """
        direct_refs = []  # References without DOI - use as-is
        crossref_refs = []  # References with DOI - fetch full metadata

        for i, ref in enumerate(references, 1):
            if not isinstance(ref, dict):
                logger.debug(f"Ref {i}: Skipping - not a dict")
                continue

            # Check if reference has a DOI
            ref_doi = ref.get('DOI', '').strip().lower() if ref.get('DOI') else None

            if ref_doi:
                # Has DOI - need to fetch full metadata from Crossref
                crossref_refs.append({
                    'index': i,
                    'doi': ref_doi,
                    'raw': ref
                })
                if self.verbose:
                    console.print(f"         Ref {i}: DOI found - will fetch full metadata: {ref_doi}")
            else:
                # No DOI - use parsed data directly
                direct_refs.append({
                    'index': i,
                    'raw': ref
                })
                if self.verbose:
                    console.print(f"         Ref {i}: No DOI - using direct data")

        return {
            'direct': direct_refs,
            'crossref': crossref_refs
        }

    def process_paper(self, paper: Dict[str, Any], conn: psycopg2.extensions.connection) -> int:
        """
        Process a single paper: fetch references and load into database

        Args:
            paper: Paper record
            conn: Database connection

        Returns:
            Number of references processed
        """
        paper_id = paper['id']
        citekey = paper['citekey']
        doi = paper['doi']

        # Print source paper in APA format
        source_apa = self._format_paper_apa(paper)
        console.print(f"[{self.stats['papers_processed'] + 1}] Processing {citekey}")
        console.print(f"  Source: {source_apa}")
        console.print(f"  DOI: {doi}")

        # Fetch references from Crossref
        crossref_data = self.fetcher.fetch_references_for_doi(doi)

        if not crossref_data:
            console.print("[yellow]  No references found in Crossref[/yellow]")
            self.not_found_records.append({
                "citing_doi": doi,
                "citing_title": citekey,
                "reason": "no_crossref_data"
            })
            self.stats['papers_skipped'] += 1
            time.sleep(self.fetcher.rate_limit_delay)
            return 0

        references = crossref_data.get('references', [])
        console.print(f"  Found {len(references)} references")

        if len(references) == 0:
            self.not_found_records.append({
                "citing_doi": doi,
                "citing_title": citekey,
                "reason": "no_references_found"
            })
            self.stats['papers_skipped'] += 1
            time.sleep(self.fetcher.rate_limit_delay)
            return 0

        self.stats['papers_with_references'] += 1

        # Hierarchically resolve references
        resolved = self.resolve_references_hierarchical(references)
        direct_count = len(resolved['direct'])
        crossref_count = len(resolved['crossref'])

        if direct_count > 0 or crossref_count > 0:
            console.print(f"  Breakdown: [cyan]{direct_count}[/cyan] direct + [cyan]{crossref_count}[/cyan] need lookup")

        # Process each reference
        references_added = 0

        # First process direct references (no DOI, use parsed data)
        for ref_item in resolved['direct']:
            try:
                i = ref_item['index']
                ref = ref_item['raw']

                # Parse reference
                parsed_ref = self.fetcher.parse_reference(ref, paper_id)

                if not parsed_ref:
                    continue

                # Insert as new paper
                cited_paper_id = self.insert_referenced_paper(conn, parsed_ref, paper_id)

                if cited_paper_id:
                    # Create citation edge (count as added regardless of whether it's new)
                    self.create_citation_edge(conn, paper_id, cited_paper_id)
                    references_added += 1
                    if self.verbose:
                        apa_citation = self.format_apa(parsed_ref)
                        console.print(f"    Ref {i}: ✓ {apa_citation}")

            except Exception as e:
                logger.warning(f"    Ref {i}: Error processing direct reference: {e}")
                self.stats['errors'] += 1

        # Then process Crossref references (have DOI, fetch full metadata)
        crossref_lookup_count = 0
        for ref_item in resolved['crossref']:
            try:
                i = ref_item['index']
                doi = ref_item['doi']
                crossref_lookup_count += 1

                # Show progress for Crossref lookups
                if not self.verbose:
                    # In normal mode, show every 10th lookup
                    if crossref_lookup_count % 10 == 1 and crossref_lookup_count > 1:
                        console.print(f"  Fetching metadata from Crossref... [cyan]{crossref_lookup_count-10}[/cyan]/{len(resolved['crossref'])}")

                # Fetch full metadata from Crossref
                crossref_work = self.fetcher.get_crossref_work_for_doi(doi)

                if not crossref_work:
                    if self.verbose:
                        logger.debug(f"    Ref {i}: Failed to fetch metadata from Crossref for {doi}")
                    continue

                # Parse the Crossref data
                parsed_ref = self.fetcher.parse_crossref_work(crossref_work, paper_id)

                if not parsed_ref:
                    if self.verbose:
                        logger.debug(f"    Ref {i}: Failed to parse Crossref data for {doi}")
                    continue

                # Insert as new paper
                cited_paper_id = self.insert_referenced_paper(conn, parsed_ref, paper_id)

                if cited_paper_id:
                    # Create citation edge (count as added regardless of whether it's new)
                    self.create_citation_edge(conn, paper_id, cited_paper_id)
                    references_added += 1
                    if self.verbose:
                        apa_citation = self.format_apa(parsed_ref)
                        console.print(f"    Ref {i}: ✓ {apa_citation}")
                else:
                    if self.verbose:
                        logger.debug(f"    Ref {i}: Failed to insert referenced paper for {doi}")

            except Exception as e:
                logger.warning(f"    Ref {i}: Error processing Crossref reference {doi}: {e}")
                self.stats['errors'] += 1

        # Commit transaction
        try:
            conn.commit()
        except Exception as e:
            logger.error(f"Error committing transaction: {e}")
            conn.rollback()
            self.stats['errors'] += 1

        self.stats['total_references_found'] += len(references)
        time.sleep(self.fetcher.rate_limit_delay)

        console.print(f"  Added {references_added}/{len(references)} references")
        return references_added

    def run(self, max_papers: Optional[int] = None) -> Dict[str, int]:
        """
        Main processing loop

        Args:
            max_papers: Maximum number of papers to process (None = all)

        Returns:
            Statistics dictionary
        """
        console.print("=" * 70)
        console.print("CROSSREF REFERENCE FETCHER")
        console.print("=" * 70)
        console.print("[green]✓ Polite Mode Enabled[/green]")
        console.print(f"  Email: {self.fetcher.email}")
        console.print(f"  User-Agent: {self.fetcher.session.headers.get('User-Agent')}")
        console.print(f"  Rate Limit: {self.fetcher.rate_limit} requests/sec")
        console.print(f"  Delay: {self.fetcher.delay_between_requests*1000:.1f}ms between requests")
        console.print(f"[cyan]📦 Cache Location:[/cyan] {self.fetcher.cache.cache_dir}")
        console.print("")

        try:
            # Get papers to process
            papers = self.get_papers_for_processing()

            if not papers:
                console.print("[yellow]No papers found to process[/yellow]")
                return self.stats

            if max_papers is not None:
                papers = papers[:max_papers]

            console.print(f"Processing {len(papers)} papers...")
            console.print("")

            # Process each paper
            for paper in papers:
                conn = self.connect()
                try:
                    self.process_paper(paper, conn)
                    self.stats['papers_processed'] += 1
                except Exception as e:
                    logger.error(f"Error processing paper {paper['citekey']}: {e}")
                    self.stats['errors'] += 1
                finally:
                    conn.close()

            # Print summary
            self._print_summary()

            # Export errors if requested
            if self.export_errors_path and self.not_found_records:
                self._export_errors()

            return self.stats

        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

    def _export_errors(self) -> None:
        """Export not found records to JSON file"""
        try:
            export_path = Path(self.export_errors_path)
            with open(export_path, 'w') as f:
                json.dump(self.not_found_records, f, indent=2)
            console.print(f"[green]✓ Exported {len(self.not_found_records)} not found records to {export_path}[/green]")
        except Exception as e:
            logger.error(f"Failed to export errors to {self.export_errors_path}: {e}")

    def _print_summary(self):
        """Print processing summary"""
        console.print("")
        console.print("=" * 70)
        console.print("SUMMARY")
        console.print("=" * 70)
        console.print(f"Papers processed:         {self.stats['papers_processed']}")
        console.print(f"Papers with references:   {self.stats['papers_with_references']}")
        console.print(f"Total references found:   {self.stats['total_references_found']}")
        console.print(f"New papers created:       {self.stats['new_papers_created']}")
        console.print(f"Citation edges created:   {self.stats['citation_edges_created']}")
        console.print(f"Papers skipped:           {self.stats['papers_skipped']}")
        console.print(f"Errors:                   {self.stats['errors']}")
        console.print("")

        if self.stats['papers_processed'] > 0:
            success_rate = (self.stats['papers_with_references'] / self.stats['papers_processed']) * 100
            console.print(f"Success rate: {success_rate:.1f}%")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch references from Crossref for papers in screening stages'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        '--db-url',
        default=os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'),
        help='PostgreSQL connection URL'
    )
    parser.add_argument(
        '-n', '--limit',
        type=int,
        default=None,
        dest='max_papers',
        help='Limit to first n papers from the eligible set'
    )
    parser.add_argument(
        '--email',
        default=CROSSREF_EMAIL,
        help='Email for Crossref API user-agent'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show papers to be added in APA format'
    )
    parser.add_argument(
        '-t', '--try',
        action='store_true',
        dest='try_mode',
        help='Scan references without uploading to database (dry-run)'
    )
    parser.add_argument(
        '--cache',
        default=str(Path.home() / ".crossref"),
        help='Cache directory for Crossref API responses (default: ~/.crossref/)'
    )
    parser.add_argument(
        '-r', '--rate',
        type=float,
        default=50.0,
        help='Request rate limit in requests per second (default: 50)'
    )
    parser.add_argument(
        '-e', '--error',
        nargs='?',
        const='error.log',
        default=None,
        help='Export not found records to JSON file (default: error.log)'
    )

    args = parser.parse_args()

    try:
        # Enable file path display in logs only in verbose mode
        if args.verbose and _log_handler:
            _log_handler.show_path = True

        loader = CrossrefReferenceLoader(args.db_url, try_mode=args.try_mode,
                                        cache_dir=args.cache)
        loader.verbose = args.verbose
        loader.export_errors_path = args.error
        loader.fetcher.verbose = args.verbose
        if args.try_mode:
            console.print("[yellow]🔍 DRY-RUN MODE: Scanning references without uploading[/yellow]")
        if args.email:
            loader.fetcher.email = args.email
            loader.fetcher.session.headers.update({
                'User-Agent': f'PaperScanner/1.0 (mailto:{args.email})'
            })

        # Set rate limit
        if args.rate:
            loader.fetcher.rate_limit = args.rate
            loader.fetcher.delay_between_requests = 1.0 / args.rate

        stats = loader.run(max_papers=args.max_papers)

        # Exit with error if there were too many errors
        if stats['errors'] > stats['papers_processed'] * 0.5:
            exit(1)

    except Exception as e:
        logger.error(f"Failed to run: {e}")
        exit(1)


if __name__ == "__main__":
    main()
