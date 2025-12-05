#!/usr/bin/env python3
"""
Example script demonstrating BibTeX loading.

This shows how to use the BibtexReader and PostgreSQLLoader classes.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import the loader
sys.path.insert(0, str(Path(__file__).parent))

from load_bibtex import BibtexReader, PostgreSQLLoader
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def example_read_only():
    """Example: Read BibTeX without loading to database."""
    print("=" * 60)
    print("EXAMPLE 1: Read BibTeX file (no database)")
    print("=" * 60)
    
    bibtex_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not bibtex_file:
        print("Usage: python example_load_bibtex.py <bibtex_file>")
        return
    
    reader = BibtexReader(bibtex_file)
    papers = reader.parse()
    
    print(f"\nTotal papers read: {len(papers)}\n")
    
    # Show first 3 papers
    for paper in papers[:3]:
        print(f"Citekey: {paper.citekey}")
        print(f"Title: {paper.title}")
        print(f"Authors: {paper.authors}")
        print(f"Year: {paper.year}")
        print(f"Journal: {paper.journal}")
        print(f"DOI: {paper.doi}")
        print()
    
    return papers


def example_with_database():
    """Example: Load BibTeX into database."""
    print("=" * 60)
    print("EXAMPLE 2: Load BibTeX into PostgreSQL")
    print("=" * 60)
    
    bibtex_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not bibtex_file:
        print("Usage: python example_load_bibtex.py <bibtex_file>")
        return
    
    # Read papers
    reader = BibtexReader(bibtex_file)
    papers = reader.parse()
    print(f"Read {len(papers)} papers from BibTeX")
    
    # Connect to database
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'
    )
    
    loader = PostgreSQLLoader(connection_string)
    
    try:
        loader.connect()
        count = loader.load_papers(papers)
        print(f"\nSuccessfully loaded {count} papers into database")
    except Exception as e:
        print(f"Error loading papers: {e}")
    finally:
        loader.disconnect()


if __name__ == '__main__':
    # By default, just read the file
    example_read_only()
    
    # Uncomment to also load into database
    # example_with_database()
