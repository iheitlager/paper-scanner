#!/usr/bin/env python3
"""
Integration test: Load BibTeX papers into PostgreSQL.

This script loads a sample of papers from a BibTeX file into the database.
"""

import sys
from pathlib import Path
import logging
import os

sys.path.insert(0, str(Path(__file__).parent))

from load_bibtex import BibtexReader, PostgreSQLLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_sample_bibtex():
    """Load a sample of papers from BibTeX into the database."""
    
    print("\n" + "="*70)
    print("BIBTEX LOADER - DATABASE INTEGRATION TEST")
    print("="*70)
    
    # Configuration
    bibtex_file = '/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib'
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'
    )
    sample_size = int(os.getenv('SAMPLE_SIZE', '10'))  # Load only 10 by default
    
    print(f"\nConfiguration:")
    print(f"  BibTeX file: {bibtex_file}")
    print(f"  Database: {connection_string.split('@')[1] if '@' in connection_string else 'unknown'}")
    print(f"  Sample size: {sample_size}")
    
    # Step 1: Read BibTeX
    print(f"\n[1/3] Reading BibTeX file...")
    try:
        reader = BibtexReader(bibtex_file)
        all_papers = reader.parse()
        print(f"  ✓ Read {len(all_papers)} papers from BibTeX")
    except Exception as e:
        print(f"  ❌ Failed to read BibTeX: {e}")
        return False
    
    # Step 2: Select sample
    papers_to_load = all_papers[:sample_size]
    print(f"\n[2/3] Preparing sample...")
    print(f"  ✓ Selected {len(papers_to_load)} papers for loading")
    
    # Show sample details
    print(f"\n  Sample papers:")
    for i, paper in enumerate(papers_to_load[:3], 1):
        print(f"    {i}. {paper.citekey}")
        print(f"       {paper.title[:60] if paper.title else 'N/A'}...")
    if len(papers_to_load) > 3:
        print(f"    ... and {len(papers_to_load) - 3} more")
    
    # Step 3: Load into database
    print(f"\n[3/3] Loading into PostgreSQL...")
    loader = PostgreSQLLoader(connection_string)
    
    try:
        loader.connect()
        count = loader.load_papers(papers_to_load)
        print(f"  ✓ Successfully loaded {count} papers")
        
        # Query what we just loaded
        cursor = loader.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total, 
                   COUNT(CASE WHEN doi IS NOT NULL THEN 1 END) as with_doi,
                   COUNT(CASE WHEN abstract IS NOT NULL THEN 1 END) as with_abstract,
                   COUNT(CASE WHEN authors IS NOT NULL THEN 1 END) as with_authors
            FROM papers 
            WHERE citekey = ANY(%s)
        """, ([p.citekey for p in papers_to_load],))
        
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            total, with_doi, with_abstract, with_authors = result
            print(f"\n  Loaded papers statistics:")
            print(f"    Total papers: {total}")
            print(f"    With DOI: {with_doi}")
            print(f"    With abstract: {with_abstract}")
            print(f"    With authors: {with_authors}")
    
    except Exception as e:
        print(f"  ❌ Failed to load papers: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        loader.disconnect()
    
    print("\n✓ Integration test PASSED")
    print("="*70 + "\n")
    return True


if __name__ == '__main__':
    success = load_sample_bibtex()
    sys.exit(0 if success else 1)
