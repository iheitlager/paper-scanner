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
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests
from psycopg2.extras import Json, RealDictCursor
from rich.console import Console
from rich.logging import RichHandler

# Configure rich console with colored output
console = Console()

# Configure rich logging with colors and better formatting
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)


# Crossref API configuration for fair use / polite pool
CROSSREF_EMAIL = "i.heitlager@tue.nl"
CROSSREF_APP_NAME = "PhD-LiteratureReview"
CROSSREF_API_BASE = "https://api.crossref.org/works"


class PoliteCrossrefClient:
    """
    Crossref client that follows etiquette guidelines and uses the polite pool.
    
    The polite pool provides significantly higher rate limits (50 req/sec vs 1 req/sec)
    when you include your email in the User-Agent header.
    
    See: https://github.com/CrossRef/rest-api-doc#etiquette
    """
    
    def __init__(self, email: str, app_name: str = "PaperScanner"):
        """
        Initialize polite Crossref client.
        
        Args:
            email: Your email for polite pool access
            app_name: Your application name for User-Agent header
        """
        self.session = requests.Session()
        
        # POLITE POOL: Include contact info in User-Agent
        # This gives us higher rate limits and better service
        self.session.headers.update({
            'User-Agent': f'{app_name}/1.0 (mailto:{email})'
        })
        
        self.email = email
        self.base_url = CROSSREF_API_BASE
    
    def get_work(self, doi: str) -> Dict[str, Any]:
        """
        Get work metadata from Crossref.
        
        Args:
            doi: Digital Object Identifier (without https://doi.org/ prefix)
            
        Returns:
            JSON response from Crossref API
        """
        url = f'{self.base_url}/{doi}'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


class CrossrefReferenceFetcher:
    """Fetch references from Crossref API"""

    def __init__(self, email: str = "i.heitlager@eindhoven.nl", rate_limit_delay: float = 0.1):
        """
        Initialize Crossref fetcher

        Args:
            email: Email for Crossref API user-agent
            rate_limit_delay: Delay in seconds between API calls
        """
        self.email = email
        self.rate_limit_delay = rate_limit_delay
        self.api_base = "https://api.crossref.org/works"

        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': f'PaperScanner/1.0 (mailto:{email})'
            })
        except ImportError:
            logger.error("requests library not found. Install with: pip install requests")
            raise

    def fetch_references_for_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetch references for a given DOI from Crossref

        Args:
            doi: Digital Object Identifier

        Returns:
            Dict with 'references' list, or None if fetch fails
        """
        try:
            # Clean DOI
            doi = doi.strip().lower()
            if doi.startswith('doi:'):
                doi = doi[4:]
            if doi.startswith('https://doi.org/'):
                doi = doi[16:]

            # Query Crossref
            url = f"{self.api_base}/{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code != 200:
                logger.debug(f"Crossref returned {response.status_code} for DOI {doi}")
                return None

            data = response.json()

            if 'message' not in data:
                logger.debug(f"No message in Crossref response for {doi}")
                return None

            message = data['message']
            references = message.get('reference', [])

            return {
                'doi': doi,
                'title': message.get('title', [''])[0] if isinstance(message.get('title'), list) else message.get('title', ''),
                'year': self._extract_year(message),
                'references': references,
                'reference_count': len(references),
                'fetched_at': time.time()
            }

        except Exception as e:
            logger.warning(f"Error fetching references for DOI {doi}: {e}")
            return None

    def _extract_year(self, work: Dict[str, Any]) -> Optional[int]:
        """Extract publication year from Crossref work"""
        try:
            if 'published-print' in work:
                date_parts = work['published-print'].get('date-parts', [[]])[0]
                if date_parts:
                    return int(date_parts[0])
            elif 'published-online' in work:
                date_parts = work['published-online'].get('date-parts', [[]])[0]
                if date_parts:
                    return int(date_parts[0])
        except (ValueError, IndexError, TypeError):
            pass
        return None

    def parse_reference(self, ref: Dict[str, Any], source_paper_id: int) -> Dict[str, Any]:
        """
        Parse a Crossref reference into a structured format

        Args:
            ref: Reference from Crossref API
            source_paper_id: ID of the paper this reference comes from

        Returns:
            Dict with parsed reference data
        """
        # Handle case where ref is not a dictionary
        if not isinstance(ref, dict):
            logger.warning(f"Reference is not a dict, got {type(ref)}: {ref}")
            return {}
        
        # Log the first reference for debugging
        if source_paper_id > 0:  # Just log once per paper
            logger.debug(f"Sample reference keys: {list(ref.keys())}")
        
        # Extract authors
        authors = []
        for author in ref.get('author', []):
            if isinstance(author, dict):
                author_obj = {
                    'last_name': author.get('family', ''),
                    'first_name': author.get('given', ''),
                    'initials': self._extract_initials(author.get('given', ''))
                }
                if author_obj['last_name']:
                    authors.append(author_obj)

        # Parse year
        year = None
        if 'year' in ref:
            try:
                year = int(ref['year'])
            except (ValueError, TypeError):
                pass

        # Extract pages
        pages_range = None
        if 'first-page' in ref and 'last-page' in ref:
            pages_range = f"{ref['first-page']}-{ref['last-page']}"
        elif 'article-number' in ref:
            pages_range = ref['article-number']

        return {
            'source_paper_id': source_paper_id,
            'title': ref.get('title') or ref.get('article-title') or ref.get('volume-title') or ref.get('unstructured', ''),
            'year': year,
            'authors': authors,
            'authors_json': json.dumps(authors) if authors else None,
            'citekey': ref.get('key', ''),
            'reference_type': ref.get('type', 'unknown'),
            'doi': ref.get('DOI', '').lower() if ref.get('DOI') else None,
            'url': ref.get('URL'),
            'volume': ref.get('volume'),
            'issue': ref.get('issue'),
            'pages_range': pages_range,
            'journal': ref.get('journal-title'),
            'publisher': ref.get('publisher'),
            'arxiv_id': self._extract_arxiv(ref.get('URL', '')),
            'raw_citation': json.dumps(ref),
        }

    def _extract_initials(self, given_name: str) -> str:
        """Extract initials from given name"""
        if not given_name:
            return ''
        return ''.join(c for c in given_name if c.isupper())

    def _extract_arxiv(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL if present"""
        if not url:
            return None
        match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', url, re.IGNORECASE)
        return match.group(1) if match else None


class CrossrefReferenceLoader:
    """Load Crossref references into the database"""

    def __init__(self, db_url: str):
        """
        Initialize database loader

        Args:
            db_url: PostgreSQL connection URL
        """
        self.db_url = db_url
        self.fetcher = CrossrefReferenceFetcher()
        self.verbose = False
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

            logger.info(f"Found {len(papers)} papers with DOIs in stages 'stage2_pass' or 'stage2_review'")
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
                    citekey, title, year, authors, doi, 
                    source_type, processing_status,
                    metadata_extracted_at, indexed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (citekey) DO NOTHING
                RETURNING id
                """,
                (
                    citekey,
                    reference.get('title'),
                    reference.get('year'),
                    reference.get('authors_json'),
                    reference.get('doi'),
                    'crossref',
                    'metadata_extracted'
                )
            )

            result = cursor.fetchone()
            if result:
                paper_id = result[0]
                logger.debug(f"Inserted referenced paper: {citekey} (ID: {paper_id})")
                self.stats['new_papers_created'] += 1
                return paper_id
            else:
                return None

        except Exception as e:
            logger.warning(f"Error inserting referenced paper: {e}")
            self.stats['errors'] += 1
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

        logger.info(f"[{self.stats['papers_processed'] + 1}] Processing {citekey}")
        logger.debug(f"  DOI: {doi}")

        # Fetch references from Crossref
        crossref_data = self.fetcher.fetch_references_for_doi(doi)

        if not crossref_data:
            logger.warning(f"  No references found in Crossref")
            self.stats['papers_skipped'] += 1
            time.sleep(self.fetcher.rate_limit_delay)
            return 0

        references = crossref_data.get('references', [])
        logger.info(f"  Found {len(references)} references")

        if len(references) == 0:
            self.stats['papers_skipped'] += 1
            time.sleep(self.fetcher.rate_limit_delay)
            return 0

        self.stats['papers_with_references'] += 1

        # Process each reference
        references_added = 0
        for i, ref in enumerate(references, 1):
            try:
                # Parse reference
                parsed_ref = self.fetcher.parse_reference(ref, paper_id)

                # Skip if parsing failed
                if not parsed_ref:
                    if not parsed_ref:
                        logger.debug(f"    Ref {i}: Skipping - invalid reference structure")
                    continue

                # Skip only if we have no useful identifying information at all
                has_title = bool(parsed_ref.get('title'))
                has_doi = bool(parsed_ref.get('doi'))
                has_authors_or_year = bool(parsed_ref.get('authors_json')) or bool(parsed_ref.get('year'))
                
                if not (has_title or (has_doi and (has_authors_or_year or parsed_ref.get('journal')))):
                    logger.debug(f"    Ref {i}: Skipping - insufficient identifying information")
                    continue

                # Insert as new paper
                cited_paper_id = self.insert_referenced_paper(conn, parsed_ref, paper_id)

                if cited_paper_id:
                    # Create citation edge
                    if self.create_citation_edge(conn, paper_id, cited_paper_id):
                        references_added += 1
                        if self.verbose:
                            apa_citation = self.format_apa(parsed_ref)
                            logger.info(f"    Ref {i}: ✓ {apa_citation}")
                        else:
                            logger.debug(f"    Ref {i}: ✓ {parsed_ref.get('title')[:50]}...")

            except Exception as e:
                logger.warning(f"    Ref {i}: Error processing reference: {e}")
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

        logger.info(f"  Added {references_added}/{len(references)} references")
        return references_added

    def run(self, max_papers: Optional[int] = None) -> Dict[str, int]:
        """
        Main processing loop

        Args:
            max_papers: Maximum number of papers to process (None = all)

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 70)
        logger.info("CROSSREF REFERENCE FETCHER")
        logger.info("=" * 70)

        try:
            # Get papers to process
            papers = self.get_papers_for_processing()

            if not papers:
                logger.warning("No papers found to process")
                return self.stats

            if max_papers:
                papers = papers[:max_papers]

            logger.info(f"Processing {len(papers)} papers...")
            logger.info("")

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

            return self.stats

        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

    def _print_summary(self):
        """Print processing summary"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Papers processed:         {self.stats['papers_processed']}")
        logger.info(f"Papers with references:   {self.stats['papers_with_references']}")
        logger.info(f"Total references found:   {self.stats['total_references_found']}")
        logger.info(f"New papers created:       {self.stats['new_papers_created']}")
        logger.info(f"Citation edges created:   {self.stats['citation_edges_created']}")
        logger.info(f"Papers skipped:           {self.stats['papers_skipped']}")
        logger.info(f"Errors:                   {self.stats['errors']}")
        logger.info("")

        if self.stats['papers_processed'] > 0:
            success_rate = (self.stats['papers_with_references'] / self.stats['papers_processed']) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch references from Crossref for papers in screening stages'
    )
    parser.add_argument(
        '--db-url',
        default=os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'),
        help='PostgreSQL connection URL'
    )
    parser.add_argument(
        '--max-papers',
        type=int,
        default=None,
        help='Maximum number of papers to process'
    )
    parser.add_argument(
        '--email',
        default='i.heitlager@eindhoven.nl',
        help='Email for Crossref API user-agent'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show papers to be added in APA format'
    )

    args = parser.parse_args()

    try:
        loader = CrossrefReferenceLoader(args.db_url)
        loader.verbose = args.verbose
        if args.email:
            loader.fetcher.email = args.email
            loader.fetcher.session.headers.update({
                'User-Agent': f'PaperScanner/1.0 (mailto:{args.email})'
            })

        stats = loader.run(max_papers=args.max_papers)

        # Exit with error if there were too many errors
        if stats['errors'] > stats['papers_processed'] * 0.5:
            exit(1)

    except Exception as e:
        logger.error(f"Failed to run: {e}")
        exit(1)


if __name__ == "__main__":
    main()
