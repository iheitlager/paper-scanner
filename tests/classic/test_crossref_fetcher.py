#!/usr/bin/env python3
"""
Test script for Crossref reference fetching

This script demonstrates and tests the Crossref reference fetching functionality
with a small sample to verify it works correctly before running on full dataset.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add spike directory to path to import the main module
sys.path.insert(0, str(Path(__file__).parent.parent / "spikes" / "006_bibtex"))

from fetch_crossref_references import CrossrefReferenceFetcher, CrossrefReferenceLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_crossref_api():
    """Test Crossref API connectivity and basic functionality"""
    logger.info("="*70)
    logger.info("TEST 1: Crossref API Connectivity")
    logger.info("="*70)

    fetcher = CrossrefReferenceFetcher()

    # Test with a well-known paper (COVID-19 paper)
    test_doi = "10.1038/s41586-020-2012-7"
    logger.info(f"Testing with DOI: {test_doi}")

    result = fetcher.fetch_references_for_doi(test_doi)

    if result:
        logger.info(f"✓ Successfully fetched data")
        logger.info(f"  Title: {result.get('title')[:60]}...")
        logger.info(f"  Year: {result.get('year')}")
        logger.info(f"  References: {result.get('reference_count')}")

        if result.get('references'):
            logger.info(f"\nFirst 3 references:")
            for i, ref in enumerate(result['references'][:3], 1):
                logger.info(f"  {i}. {ref.get('title', 'N/A')[:50]}...")

        return True
    else:
        logger.error("✗ Failed to fetch references")
        return False


def test_reference_parsing():
    """Test reference parsing"""
    logger.info("")
    logger.info("="*70)
    logger.info("TEST 2: Reference Parsing")
    logger.info("="*70)

    fetcher = CrossrefReferenceFetcher()

    # Sample reference from Crossref
    sample_ref = {
        "key": "ref1",
        "type": "journal-article",
        "title": "A test paper on machine learning",
        "year": 2020,
        "author": [
            {"family": "Smith", "given": "John"},
            {"family": "Doe", "given": "Jane"}
        ],
        "DOI": "10.1234/test.2020.1234",
        "journal-title": "Test Journal",
        "volume": "42",
        "issue": "3",
        "first-page": "123",
        "last-page": "135",
        "URL": "https://example.com/paper.pdf"
    }

    parsed = fetcher.parse_reference(sample_ref, source_paper_id=1)

    logger.info("Parsed reference:")
    logger.info(f"  Title: {parsed.get('title')}")
    logger.info(f"  Year: {parsed.get('year')}")
    logger.info(f"  Authors: {json.loads(parsed.get('authors_json', '[]'))}")
    logger.info(f"  DOI: {parsed.get('doi')}")
    logger.info(f"  Journal: {parsed.get('journal')}")
    logger.info(f"  Pages: {parsed.get('pages_range')}")

    return True


def test_database_connection(db_url: str):
    """Test database connection"""
    logger.info("")
    logger.info("="*70)
    logger.info("TEST 3: Database Connection")
    logger.info("="*70)

    try:
        loader = CrossrefReferenceLoader(db_url)
        papers = loader.get_papers_for_processing()

        logger.info(f"✓ Database connection successful")
        logger.info(f"  Found {len(papers)} papers with DOIs in screening stages")

        if papers:
            logger.info("\nFirst 3 papers:")
            for i, paper in enumerate(papers[:3], 1):
                logger.info(f"  {i}. {paper['citekey']} ({paper['year']})")
                logger.info(f"     Title: {paper['title'][:50]}...")
                logger.info(f"     DOI: {paper['doi']}")
                logger.info(f"     Similarity: {paper['semantic_similarity']:.2f}")

        return True, len(papers)

    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False, 0


def test_full_pipeline(db_url: str, max_papers: int = 1):
    """Test the full pipeline with a limited number of papers"""
    logger.info("")
    logger.info("="*70)
    logger.info(f"TEST 4: Full Pipeline (max {max_papers} paper(s))")
    logger.info("="*70)

    try:
        loader = CrossrefReferenceLoader(db_url)
        stats = loader.run(max_papers=max_papers)

        logger.info("")
        logger.info("Results:")
        logger.info(f"  Papers processed: {stats['papers_processed']}")
        logger.info(f"  References found: {stats['total_references_found']}")
        logger.info(f"  New papers created: {stats['new_papers_created']}")
        logger.info(f"  Citation edges: {stats['citation_edges_created']}")

        return True

    except Exception as e:
        logger.error(f"✗ Pipeline test failed: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("")
    logger.info("╔" + "="*68 + "╗")
    logger.info("║" + " "*15 + "CROSSREF REFERENCE FETCHER - TEST SUITE" + " "*14 + "║")
    logger.info("╚" + "="*68 + "╝")
    logger.info("")

    results = {}

    # Test 1: API Connectivity
    results['api'] = test_crossref_api()

    # Test 2: Reference Parsing
    results['parsing'] = test_reference_parsing()

    # Test 3: Database Connection
    db_url = os.getenv('DATABASE_URL', 'postgresql://pdfuser:pdfpass@localhost:5432/pdfdb')
    db_ok, paper_count = test_database_connection(db_url)
    results['database'] = db_ok

    # Test 4: Full Pipeline (only if database has papers and DB is OK)
    if db_ok and paper_count > 0:
        results['pipeline'] = test_full_pipeline(db_url, max_papers=1)
    else:
        logger.warning("⊘ Skipping pipeline test (no papers or DB error)")
        results['pipeline'] = None

    # Summary
    logger.info("")
    logger.info("="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)

    test_names = {
        'api': 'Crossref API Connectivity',
        'parsing': 'Reference Parsing',
        'database': 'Database Connection',
        'pipeline': 'Full Pipeline'
    }

    for test_key, test_name in test_names.items():
        status = results[test_key]
        if status is None:
            symbol = "⊘"
            text = "SKIPPED"
        elif status:
            symbol = "✓"
            text = "PASSED"
        else:
            symbol = "✗"
            text = "FAILED"

        logger.info(f"{symbol} {test_name:<40} {text}")

    logger.info("")

    # Overall result
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)

    if failed == 0:
        logger.info("✓ All tests passed!")
        logger.info("")
        logger.info("You can now run the full fetch with:")
        logger.info("  python -m paper_scanner.cli.fetch_crossref_references")
        return 0
    else:
        logger.error(f"✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
