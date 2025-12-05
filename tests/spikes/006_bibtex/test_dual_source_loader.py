#!/usr/bin/env python3
"""
Test script for dual-source BibTeX loader (WOS and Scopus).
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, '/Users/iheitlager/wc/paper-scanner/tests/spikes/006_bibtex')

from load_bibtex import BibtexReader, WOSTranslator, ScopusTranslator
from pathlib import Path


def test_wos_loader():
    """Test loading WOS BibTeX file."""
    print("\n" + "="*80)
    print("Testing WOS BibTeX Loader")
    print("="*80)
    
    bib_file = '/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib'
    
    if not Path(bib_file).exists():
        print(f"✗ WOS BibTeX file not found: {bib_file}")
        return False
    
    try:
        reader = BibtexReader(bib_file)
        papers = reader.parse()
        print(f"✓ Successfully parsed {len(papers)} papers from WOS BibTeX file")
        
        # Show sample paper
        if papers:
            p = papers[0]
            print(f"\nSample WOS paper:")
            print(f"  Citekey: {p.citekey}")
            print(f"  Title: {p.title[:80] if p.title else 'N/A'}")
            print(f"  Authors: {len(p.authors) if p.authors else 0} authors")
            print(f"  Keywords: {len(p.keywords) if p.keywords else 0} keywords")
            print(f"  Keywords Extra: {len(p.keywords_extra) if p.keywords_extra else 0} keywords")
            print(f"  Source Details keys: {list(p.source_details.keys()) if p.source_details else []}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to load WOS BibTeX: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scopus_loader():
    """Test loading Scopus BibTeX file."""
    print("\n" + "="*80)
    print("Testing Scopus BibTeX Loader")
    print("="*80)
    
    bib_file = '/Users/iheitlager/wc/scopus_export_Dec 5-2025_4146c5e5-b8ab-42a4-b0a5-e7f5e035fd82.bib'
    
    if not Path(bib_file).exists():
        print(f"✗ Scopus BibTeX file not found: {bib_file}")
        return False
    
    try:
        reader = BibtexReader(bib_file)
        papers = reader.parse()
        print(f"✓ Successfully parsed {len(papers)} papers from Scopus BibTeX file")
        
        # Show sample paper
        if papers:
            p = papers[0]
            print(f"\nSample Scopus paper:")
            print(f"  Citekey: {p.citekey}")
            print(f"  Title: {p.title[:80] if p.title else 'N/A'}")
            print(f"  Authors: {len(p.authors) if p.authors else 0} authors")
            print(f"  Keywords: {len(p.keywords) if p.keywords else 0} keywords")
            print(f"  Keywords Extra: {len(p.keywords_extra) if p.keywords_extra else 0} keywords")
            print(f"  Source Details keys: {list(p.source_details.keys()) if p.source_details else []}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to load Scopus BibTeX: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_source_detection():
    """Test automatic source detection."""
    print("\n" + "="*80)
    print("Testing Source Detection")
    print("="*80)
    
    reader = BibtexReader('/Users/iheitlager/wc/scopus_export_Dec 5-2025_4146c5e5-b8ab-42a4-b0a5-e7f5e035fd82.bib')
    
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
    
    try:
        # This is what happens in the _insert_paper method
        json_data = Json(authors)
        print(f"✓ Successfully serialized authors to JSON: {type(json_data)}")
        return True
    except Exception as e:
        print(f"✗ Failed to serialize authors: {e}")
        return False


if __name__ == '__main__':
    results = []
    
    print("\n" + "="*100)
    print("DUAL-SOURCE BibTeX LOADER TEST SUITE")
    print("="*100)
    
    # Run tests
    results.append(("WOS Loader", test_wos_loader()))
    results.append(("Scopus Loader", test_scopus_loader()))
    results.append(("Source Detection", test_source_detection()))
    results.append(("JSON Serialization", test_json_serialization()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    sys.exit(0 if passed == total else 1)
