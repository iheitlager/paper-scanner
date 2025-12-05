#!/usr/bin/env python3
"""
Comprehensive test for BibTeX loader.

Tests both BibtexReader and PostgreSQLLoader functionality.
"""

import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from load_bibtex import BibtexReader, PostgreSQLLoader, Paper
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_bibtex_reader():
    """Test BibTeX reader on sample file."""
    print("\n" + "="*70)
    print("TEST 1: BibTeX Reader")
    print("="*70)
    
    # Find a test bibtex file
    test_file = Path('/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib')
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    try:
        reader = BibtexReader(str(test_file))
        papers = reader.parse()
        
        print(f"✓ Successfully parsed {len(papers)} papers")
        
        # Verify structure
        assert len(papers) > 0, "No papers parsed"
        
        sample = papers[0]
        assert sample.citekey, "Missing citekey"
        
        print(f"\nSample paper:")
        print(f"  Citekey: {sample.citekey}")
        print(f"  Title: {sample.title[:80] if sample.title else 'N/A'}...")
        print(f"  Year: {sample.year}")
        print(f"  Journal: {sample.journal or 'N/A'}")
        print(f"  Authors: {len(sample.authors) if sample.authors else 0}")
        print(f"  Keywords: {len(sample.keywords) if sample.keywords else 0}")
        print(f"  DOI: {sample.doi or 'N/A'}")
        print(f"  Abstract length: {len(sample.abstract) if sample.abstract else 0} chars")
        
        # Check field mappings
        papers_with_doi = sum(1 for p in papers if p.doi)
        papers_with_abstract = sum(1 for p in papers if p.abstract)
        papers_with_keywords = sum(1 for p in papers if p.keywords)
        papers_with_authors = sum(1 for p in papers if p.authors)
        
        print(f"\nStatistics:")
        print(f"  Papers with DOI: {papers_with_doi}/{len(papers)}")
        print(f"  Papers with Abstract: {papers_with_abstract}/{len(papers)}")
        print(f"  Papers with Keywords: {papers_with_keywords}/{len(papers)}")
        print(f"  Papers with Authors: {papers_with_authors}/{len(papers)}")
        
        print("\n✓ BibtexReader test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ BibtexReader test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_paper_to_dict():
    """Test Paper.to_dict() serialization."""
    print("\n" + "="*70)
    print("TEST 2: Paper Serialization")
    print("="*70)
    
    try:
        # Create a test paper
        paper = Paper(
            citekey="TEST001",
            title="Test Paper",
            authors=[{'last_name': 'Smith', 'first_name': 'John', 'initials': 'J', 'order': 0}],
            year=2024,
            journal="Test Journal",
            doi="10.1234/test",
            keywords=["test", "example"],
        )
        
        # Convert to dict
        data = paper.to_dict()
        
        print(f"✓ Paper serialized successfully")
        print(f"  Fields: {list(data.keys())}")
        print(f"  Data types:")
        for key, value in data.items():
            print(f"    {key}: {type(value).__name__}")
        
        # Check JSON serialization
        json_str = json.dumps(data, indent=2, default=str)
        print(f"\n✓ JSON serialization successful ({len(json_str)} chars)")
        
        print("\n✓ Paper serialization test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Paper serialization test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_field_parsing():
    """Test specific field parsing."""
    print("\n" + "="*70)
    print("TEST 3: Field Parsing")
    print("="*70)
    
    try:
        test_file = Path('/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib')
        reader = BibtexReader(str(test_file))
        papers = reader.parse()
        
        # Find papers with various fields
        paper_with_authors = next((p for p in papers if p.authors and len(p.authors) > 2), None)
        paper_with_keywords = next((p for p in papers if p.keywords and len(p.keywords) > 2), None)
        paper_with_abstract = next((p for p in papers if p.abstract and len(p.abstract) > 100), None)
        
        if paper_with_authors:
            print(f"\n✓ Authors parsing:")
            print(f"  Citekey: {paper_with_authors.citekey}")
            print(f"  Author count: {len(paper_with_authors.authors)}")
            for i, author in enumerate(paper_with_authors.authors[:3]):
                print(f"    {i+1}. {author.get('first_name')} {author.get('last_name')} (order={author.get('order')})")
        
        if paper_with_keywords:
            print(f"\n✓ Keywords parsing:")
            print(f"  Citekey: {paper_with_keywords.citekey}")
            print(f"  Keyword count: {len(paper_with_keywords.keywords)}")
            for kw in paper_with_keywords.keywords[:5]:
                print(f"    - {kw}")
        
        if paper_with_abstract:
            print(f"\n✓ Abstract parsing:")
            print(f"  Citekey: {paper_with_abstract.citekey}")
            print(f"  Abstract length: {len(paper_with_abstract.abstract)} chars")
            print(f"  Preview: {paper_with_abstract.abstract[:100]}...")
        
        print("\n✓ Field parsing test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Field parsing test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test database connection (if database is available)."""
    print("\n" + "="*70)
    print("TEST 4: Database Connection")
    print("="*70)
    
    import os
    
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'
    )
    
    loader = PostgreSQLLoader(connection_string)
    
    try:
        loader.connect()
        print("✓ Connected to PostgreSQL successfully")
        
        # Check if papers table exists
        cursor = loader.connection.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'papers'
            )
        """)
        table_exists = cursor.fetchone()[0]
        cursor.close()
        
        if table_exists:
            print("✓ Papers table exists")
        else:
            print("⚠ Papers table not found")
        
        loader.disconnect()
        print("✓ Database connection test PASSED")
        return True
        
    except Exception as e:
        print(f"⚠ Database not available: {e}")
        print("  (This is OK if PostgreSQL is not running)")
        return None


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("BIBTEX LOADER TEST SUITE")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Bibtex Reader", test_bibtex_reader()))
    results.append(("Paper Serialization", test_paper_to_dict()))
    results.append(("Field Parsing", test_field_parsing()))
    results.append(("Database Connection", test_database_connection()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    for name, result in results:
        if result is True:
            status = "✓ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠ SKIPPED"
        print(f"  {name:<30} {status}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
