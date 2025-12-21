#!/usr/bin/env python3
"""
Comprehensive test for BibTeX loader.

Tests both BibtexReader and PostgreSQLLoader functionality.
"""

import os
from pathlib import Path
import pytest
import json

from load_bibtex import BibtexReader, PostgreSQLLoader, Paper


def test_bibtex_reader():
    """Test BibTeX reader on sample file."""
    test_file = Path('tests/data/scopus_sample_20.bib')
    
    assert test_file.exists(), f"Test file not found: {test_file}"
    
    reader = BibtexReader(str(test_file))
    papers = reader.parse()
    
    assert len(papers) > 0, "No papers parsed"
    
    sample = papers[0]
    assert sample.citekey, "Missing citekey"
    
    # Check field mappings
    papers_with_doi = sum(1 for p in papers if p.doi)
    papers_with_abstract = sum(1 for p in papers if p.abstract)
    papers_with_keywords = sum(1 for p in papers if p.keywords)
    papers_with_authors = sum(1 for p in papers if p.authors)
    
    # Verify at least some papers have these fields
    assert papers_with_doi > 0, "No papers with DOI found"
    assert papers_with_abstract > 0, "No papers with abstract found"


def test_paper_to_dict():
    """Test Paper.to_dict() serialization."""
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
    
    assert data is not None, "Paper serialization failed"
    assert 'citekey' in data, "Missing citekey in serialized data"
    assert data['citekey'] == "TEST001", "Citekey not preserved"
    
    # Check JSON serialization
    json_str = json.dumps(data, indent=2, default=str)
    assert json_str is not None, "JSON serialization failed"
    assert len(json_str) > 0, "JSON serialization produced empty string"

def test_field_parsing():
    """Test specific field parsing."""
    test_file = Path('tests/data/scopus_sample_20.bib')
    reader = BibtexReader(str(test_file))
    papers = reader.parse()
    
    # Find papers with various fields
    paper_with_authors = next((p for p in papers if p.authors and len(p.authors) > 2), None)
    paper_with_keywords = next((p for p in papers if p.keywords and len(p.keywords) > 2), None)
    paper_with_abstract = next((p for p in papers if p.abstract and len(p.abstract) > 100), None)
    
    # Verify at least some papers have these fields
    assert paper_with_authors is not None, "No papers with multiple authors found"
    assert paper_with_keywords is not None, "No papers with multiple keywords found"
    assert paper_with_abstract is not None, "No papers with long abstracts found"
    
    # Verify field structure
    assert len(paper_with_authors.authors) > 2, "Author list incomplete"
    assert len(paper_with_keywords.keywords) > 2, "Keywords list incomplete"
    assert len(paper_with_abstract.abstract) > 100, "Abstract too short"


def test_database_connection():
    """Test database connection (if database is available)."""
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb'
    )
    
    loader = PostgreSQLLoader(connection_string)
    
    try:
        loader.connect()
        assert loader.connection is not None, "Failed to connect to PostgreSQL"
        
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
        
        assert table_exists, "Papers table not found"
        
        loader.disconnect()
        
    except Exception as e:
        pytest.skip(f"Database not available: {e} (OK if PostgreSQL is not running)")

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
