"""
Test 01: RIS Parser Integration - Parse ProQuest Example with Production Library
Validates RIS file parsing using src/paper_scanner/io/ris.py library
"""

from pathlib import Path
from paper_scanner.io.ris import ris_file_to_papers
from paper_scanner.core.enum import DiscoveryMethod


if __name__ == '__main__':
    test_file = Path(__file__).parent / 'ProQuestDocuments-2025-12-31.ris'
    
    print(f"Parsing: {test_file}")
    
    # Load RIS file using production library
    papers = ris_file_to_papers(
        str(test_file),
        source_database="ProQuest"
    )
    
    print(f"✓ Successfully loaded {len(papers)} papers\n")
    
    # Display first 2 papers
    for i, paper in enumerate(papers[:2]):
        print(f"Paper {i+1}:")
        print(f"  Title: {paper.title}")
        print(f"  Source Key: {paper.source_key}")
        print(f"  Cite Key: {paper.cite_key}")
        print(f"  Authors: {len(paper.authors)} authors")
        if paper.authors:
            print(f"    - {paper.authors[0].full_name}")
        print(f"  Journal: {paper.journal}")
        print(f"  Year: {paper.year}")
        print(f"  Keywords: {len(paper.keywords)} keywords")
        if paper.keywords:
            print(f"    - {paper.keywords[0]}")
        print(f"  DOI: {paper.doi}")
        print(f"  Paper Type: {paper.paper_type}")
        print(f"  Discovery Method: {paper.discovery.method}")
        print(f"  Source Database: {paper.discovery.source_database}")
        print(f"  Abstract length: {len(paper.abstract) if paper.abstract else 0} chars")
        print()
    
    # Statistics
    print("File Statistics:")
    print(f"  Total papers: {len(papers)}")
    print(f"\n  Papers with DOI: {sum(1 for p in papers if p.doi)}")
    print(f"  Papers with abstract: {sum(1 for p in papers if p.abstract)}")
    print(f"  Average keywords: {sum(len(p.keywords) for p in papers) / len(papers):.1f}")
    print(f"  Year range: {min(p.year for p in papers if p.year)} - {max(p.year for p in papers if p.year)}")
    
    # Cite key analysis
    cite_key_types = {}
    for paper in papers:
        if paper.source_key.startswith('ris_an_'):
            cite_key_types['accession_number'] = cite_key_types.get('accession_number', 0) + 1
        elif paper.source_key.startswith('ris_doi_'):
            cite_key_types['doi'] = cite_key_types.get('doi', 0) + 1
        elif paper.source_key.startswith('ris_auto_'):
            cite_key_types['auto_generated'] = cite_key_types.get('auto_generated', 0) + 1
    
    print(f"\n  Cite Key Sources:")
    for key_type, count in sorted(cite_key_types.items()):
        print(f"    - {key_type}: {count}")
    
    print("\n✓ Test completed successfully")
