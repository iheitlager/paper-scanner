#!/usr/bin/env python3
"""
Command-line tool for loading BibTeX files into PostgreSQL.

Usage:
    python load_bibtex_cli.py <bibtex_file> [--sample N] [--db DATABASE_URL] [--list]

Examples:
    # Read and show first 5 papers
    python load_bibtex_cli.py papers.bib --list

    # Load first 10 papers
    python load_bibtex_cli.py papers.bib --sample 10

    # Load all papers
    python load_bibtex_cli.py papers.bib

    # Use custom database
    python load_bibtex_cli.py papers.bib --db postgresql://user:pass@host/db
"""

import sys
import os
import argparse
from pathlib import Path
from typing import Optional
import logging

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from load_bibtex import BibtexReader, PostgreSQLLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_parser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='Load BibTeX files into PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'bibtex_file',
        help='Path to BibTeX file'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List papers without loading to database'
    )
    
    parser.add_argument(
        '--sample',
        type=int,
        default=None,
        help='Load only first N papers'
    )
    
    parser.add_argument(
        '--db',
        default=None,
        help='Database connection string (default: env var DATABASE_URL)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    return parser


def list_papers(papers, limit: Optional[int] = None):
    """Display papers in a table format."""
    print("\n" + "="*100)
    print("PAPERS")
    print("="*100 + "\n")
    
    papers_to_show = papers[:limit] if limit else papers
    
    for i, paper in enumerate(papers_to_show, 1):
        print(f"{i}. Citekey: {paper.citekey}")
        if paper.title:
            print(f"   Title: {paper.title[:80]}")
        if paper.authors:
            author_names = ', '.join([
                f"{a.get('first_name', '')} {a.get('last_name', '')}"
                for a in paper.authors[:3]
            ])
            if len(paper.authors) > 3:
                author_names += f" (+{len(paper.authors)-3} more)"
            print(f"   Authors: {author_names}")
        if paper.year:
            print(f"   Year: {paper.year}")
        if paper.journal:
            print(f"   Journal: {paper.journal}")
        if paper.doi:
            print(f"   DOI: {paper.doi}")
        print()
    
    if limit and len(papers) > limit:
        print(f"... and {len(papers) - limit} more papers\n")


def main():
    """Main entry point."""
    parser = setup_parser()
    args = parser.parse_args()
    
    # Validate bibtex file
    bibtex_file = Path(args.bibtex_file)
    if not bibtex_file.exists():
        print(f"❌ Error: File not found: {bibtex_file}")
        sys.exit(1)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
    
    # Read BibTeX file
    print(f"Reading BibTeX file: {bibtex_file}")
    try:
        reader = BibtexReader(str(bibtex_file))
        papers = reader.parse()
        print(f"✓ Read {len(papers)} papers\n")
    except Exception as e:
        print(f"❌ Error reading BibTeX: {e}")
        sys.exit(1)
    
    # If --list, just display papers
    if args.list:
        list_papers(papers, limit=args.sample or 5)
        return
    
    # Otherwise, load into database
    if args.sample:
        papers = papers[:args.sample]
        print(f"Loading first {len(papers)} papers into database...")
    else:
        print(f"Loading {len(papers)} papers into database...")
    
    # Get database connection string
    db_url = args.db or os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb')
    
    loader = PostgreSQLLoader(db_url)
    
    try:
        loader.connect()
        count = loader.load_papers(papers)
        print(f"\n✓ Successfully loaded {count} papers!")
    except Exception as e:
        print(f"❌ Error loading papers: {e}")
        sys.exit(1)
    finally:
        loader.disconnect()


if __name__ == '__main__':
    main()
