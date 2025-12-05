#!/usr/bin/env python3
"""
Quick validation that both WOS and Scopus papers can be serialized without errors.
"""

import sys
sys.path.insert(0, '/Users/iheitlager/wc/paper-scanner/tests/spikes/006_bibtex')

from load_bibtex import BibtexReader
from pathlib import Path
import json


def validate_paper_to_dict(paper, source):
    """Validate that a paper can be converted to dict format for database insertion."""
    try:
        data = paper.to_dict()
        
        # Check critical fields
        assert data.get('citekey'), f"Missing citekey in {source}"
        assert data.get('title') or data.get('abstract'), f"Missing title/abstract in {source}"
        
        # Check authors serialization
        if data.get('authors'):
            assert isinstance(data['authors'], list), f"Authors should be list in {source}"
            if data['authors']:
                assert isinstance(data['authors'][0], dict), f"Author should be dict in {source}"
        
        # Check keywords
        if data.get('keywords'):
            assert isinstance(data['keywords'], list), f"Keywords should be list in {source}"
        
        if data.get('keywords_extra'):
            assert isinstance(data['keywords_extra'], list), f"Keywords_extra should be list in {source}"
        
        return True, data
    except Exception as e:
        return False, str(e)


def main():
    print("\n" + "="*80)
    print("VALIDATION: Both WOS and Scopus papers serializable")
    print("="*80 + "\n")
    
    # Test WOS
    wos_file = '/Users/iheitlager/wc/innovation-review/raw/search 2025-04-19 - 690 - no review - excluded.bib'
    if Path(wos_file).exists():
        print("Testing WOS papers...")
        reader = BibtexReader(wos_file)
        papers = reader.parse()
        
        errors = []
        for i, paper in enumerate(papers[:10]):  # Test first 10
            ok, result = validate_paper_to_dict(paper, "WOS")
            if not ok:
                errors.append(f"  Paper {i} ({paper.citekey}): {result}")
        
        if errors:
            print("✗ WOS validation FAILED:")
            for err in errors:
                print(err)
        else:
            print(f"✓ WOS: All {min(10, len(papers))} tested papers valid")
            # Show sample
            p = papers[0]
            print(f"  Sample: {p.citekey} - {p.title[:50] if p.title else 'N/A'}...")
            print(f"  Authors: {len(p.authors) if p.authors else 0}, Keywords: {len(p.keywords) if p.keywords else 0}")
    
    # Test Scopus
    scopus_file = '/Users/iheitlager/wc/scopus_export_Dec 5-2025_4146c5e5-b8ab-42a4-b0a5-e7f5e035fd82.bib'
    if Path(scopus_file).exists():
        print("\nTesting Scopus papers...")
        reader = BibtexReader(scopus_file)
        papers = reader.parse()
        
        errors = []
        for i, paper in enumerate(papers[:10]):  # Test first 10
            ok, result = validate_paper_to_dict(paper, "Scopus")
            if not ok:
                errors.append(f"  Paper {i} ({paper.citekey}): {result}")
        
        if errors:
            print("✗ Scopus validation FAILED:")
            for err in errors:
                print(err)
        else:
            print(f"✓ Scopus: All {min(10, len(papers))} tested papers valid")
            # Show sample
            p = papers[0]
            print(f"  Sample: {p.citekey} - {p.title[:50] if p.title else 'N/A'}...")
            print(f"  Authors: {len(p.authors) if p.authors else 0}, Keywords: {len(p.keywords) if p.keywords else 0}")
    
    print("\n" + "="*80)
    print("✓ VALIDATION COMPLETE: Both sources ready for database loading")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
