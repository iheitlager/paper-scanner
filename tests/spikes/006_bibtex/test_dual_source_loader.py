#!/usr/bin/env python3
"""
Test script for dual-source BibTeX loader (WOS and Scopus).
"""

import sys

# Add parent directory to path
sys.path.insert(0, '/Users/iheitlager/wc/paper-scanner/tests/spikes/006_bibtex')

from pathlib import Path

from load_bibtex import BibtexReader


def test_wos_loader():
    """Test loading WOS BibTeX file."""
    print("\n" + "="*80)
    print("Testing WOS BibTeX Loader")
    print("="*80)

        # Use test data file from tests/data directory
    bib_file = Path(__file__).parent.parent.parent / 'data' / 'wos_sample_20.bib'

    assert Path(bib_file).exists(), f"WOS BibTeX file not found: {bib_file}"

    reader = BibtexReader(bib_file)
    papers = reader.parse()
    print(f"✓ Successfully parsed {len(papers)} papers from WOS BibTeX file")

    # Show sample paper
    if papers:
        p = papers[0]
        print("\nSample WOS paper:")
        print(f"  Citekey: {p.citekey}")
        print(f"  Title: {p.title[:80] if p.title else 'N/A'}")
        print(f"  Authors: {len(p.authors) if p.authors else 0} authors")
        print(f"  Keywords: {len(p.keywords) if p.keywords else 0} keywords")
        print(f"  Keywords Extra: {len(p.keywords_extra) if p.keywords_extra else 0} keywords")
        print(f"  Source Details keys: {list(p.source_details.keys()) if p.source_details else []}")


def test_scopus_loader():
    """Test loading Scopus BibTeX file."""
    print("\n" + "="*80)
    print("Testing Scopus BibTeX Loader")
    print("="*80)

    # Use test data file from tests/data directory
    bib_file = Path(__file__).parent.parent.parent / 'data' / 'scopus_sample_20.bib'

    assert bib_file.exists(), f"Scopus BibTeX file not found: {bib_file}"

    reader = BibtexReader(str(bib_file))
    papers = reader.parse()
    print(f"✓ Successfully parsed {len(papers)} papers from Scopus BibTeX file")

    # Show sample paper
    if papers:
        p = papers[0]
        print("\nSample Scopus paper:")
        print(f"  Citekey: {p.citekey}")
        print(f"  Title: {p.title[:80] if p.title else 'N/A'}")
        print(f"  Authors: {len(p.authors) if p.authors else 0} authors")
        print(f"  Keywords: {len(p.keywords) if p.keywords else 0} keywords")
        print(f"  Keywords Extra: {len(p.keywords_extra) if p.keywords_extra else 0} keywords")
        print(f"  Source Details keys: {list(p.source_details.keys()) if p.source_details else []}")


def test_source_detection():
    """Test automatic source detection."""
    print("\n" + "="*80)
    print("Testing Source Detection")
    print("="*80)

    # Use test data file from tests/data directory
    bib_file = Path(__file__).parent.parent.parent / 'data' / 'scopus_sample_20.bib'
    reader = BibtexReader(str(bib_file))

    # Test WOS detection
    wos_fields = {
        'title': 'Test',
        'web-of-science-categories': 'Test Category',
        'web-of-science-index': 'SCCI'
    }
    wos_source = reader._detect_source(wos_fields, 'WOS:000123456789')
    print(f"WOS detection (from fields): {wos_source} {'✓' if wos_source == 'wos' else '✗'}")

    # Test Scopus detection
    scopus_fields = {
        'title': 'Test',
        'source': 'Scopus',
        'author_keywords': 'keyword1; keyword2'
    }
    scopus_source = reader._detect_source(scopus_fields, 'Liu2026')
    print(f"Scopus detection (from fields): {scopus_source} {'✓' if scopus_source == 'scopus' else '✗'}")

    # Test citekey-based WOS detection
    wos_citekey_source = reader._detect_source({}, 'WOS:000123456789')
    print(f"WOS detection (from citekey): {wos_citekey_source} {'✓' if wos_citekey_source == 'wos' else '✗'}")


def test_json_serialization():
    """Test that author data can be properly serialized to JSON."""
    print("\n" + "="*80)
    print("Testing JSON Serialization")
    print("="*80)

    from psycopg2.extras import Json

    # Create sample author data
    authors = [
        {'first_name': 'John', 'last_name': 'Doe', 'initials': 'J'},
        {'first_name': 'Jane', 'last_name': 'Smith', 'initials': 'J'},
    ]

    # This is what happens in the _insert_paper method
    json_data = Json(authors)
    print(f"✓ Successfully serialized authors to JSON: {type(json_data)}")


if __name__ == '__main__':
    print("\n" + "="*100)
    print("DUAL-SOURCE BibTeX LOADER TEST SUITE")
    print("="*100)

    # Run tests
    test_wos_loader()
    test_scopus_loader()
    test_source_detection()
    test_json_serialization()

    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)
