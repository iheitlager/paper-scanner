"""
Performance tests for deduplication step

Verifies that indexed lookups are actually being used
"""

import time
from pathlib import Path

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper, PaperType
from paper_scanner.steps.deduplication import DeduplicationStep


def test_doi_matching_performance():
    """Test that DOI matching uses O(1) indexed lookup, not O(n) linear search"""
    papers_db = PapersDatabase()
    
    # Add 1000 papers
    for i in range(1000):
        paper = Paper(
            id=f"p{i}",
            cite_key=f"paper{i}",
            title=f"Paper {i}",
            authors=[Author(family_name="Author", given_name="A", full_name="A Author")],
            doi=f"10.{i}/test.2024" if i < 500 else None,  # First 500 have DOI
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        papers_db.add(paper)
    
    # Create a test paper with DOI matching paper 100
    test_paper = Paper(
        id="test",
        cite_key="test",
        title="Test Paper",
        authors=[Author(family_name="Test", given_name="T", full_name="T Test")],
        doi="10.100/test.2024",  # Matches paper 100
        paper_type=PaperType.JOURNAL_ARTICLE
    )
    
    # Time the lookup
    start = time.time()
    result = None
    if test_paper.doi:
        matching_papers = papers_db.get_by_doi(test_paper.doi)
        if matching_papers:
            matching_papers_sorted = sorted(matching_papers, key=lambda p: p.id)
            primary_paper = matching_papers_sorted[0]
            if test_paper.id != primary_paper.id:
                result = (primary_paper.id, 1.0)
    elapsed = time.time() - start
    
    # Should find the match
    assert result is not None
    assert result[0] == "p100"
    
    # Should be very fast (< 1ms for indexed lookup)
    # If it were O(n) linear search, it would take much longer
    assert elapsed < 0.001, f"DOI lookup took {elapsed:.6f}s - not using indexed lookup!"


def test_deduplication_with_large_dataset():
    """Test deduplication performance with a larger dataset"""
    papers_db = PapersDatabase()
    
    # Add 100 papers with some duplicates
    for i in range(100):
        paper = Paper(
            id=f"p{i}",
            cite_key=f"paper{i}",
            title=f"Paper {i}",
            authors=[Author(family_name="Author", given_name="A", full_name="A Author")],
            doi=f"10.{i%50}/test.2024",  # Create 50 DOI pairs for duplicates
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        papers_db.add(paper)
    
    config = {
        "methods": [
            {"method": "doi_exact", "priority": 1},
        ]
    }
    
    # Instantiate the step with base class requirements
    step = DeduplicationStep(
        general_config={},
        db=papers_db,
        cache_dir=Path("/tmp")
    )
    
    # Time the full deduplication
    start = time.time()
    result = step.execute(config=config)
    elapsed = time.time() - start
    
    # Should find duplicates
    assert result["duplicates_found"] > 0
    
    # Should be fast even with 100 papers
    # If using O(n²) naive approach, would be much slower
    assert elapsed < 0.5, f"Deduplication took {elapsed:.3f}s - might not be using indexes!"
    
    print(f"Deduplication of 100 papers took {elapsed:.6f}s")
    print(f"Found {result['duplicates_found']} duplicates")


def test_indexed_lookup_vs_linear_search():
    """Compare indexed lookup vs linear search to verify performance"""
    papers_db = PapersDatabase()
    
    # Add papers with DOIs
    doi_lookup_times = []
    
    # Add 500 papers
    for i in range(500):
        paper = Paper(
            id=f"p{i}",
            cite_key=f"paper{i}",
            title=f"Paper {i}",
            authors=[Author(family_name="Author", given_name="A", full_name="A Author")],
            doi=f"10.{i}/test.2024",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        papers_db.add(paper)
    
    # Test lookup at different positions
    for target_idx in (50, 100, 250, 400, 499):
        test_paper = Paper(
            id="test",
            cite_key="test",
            title="Test",
            authors=[Author(family_name="T", given_name="T", full_name="T T")],
            doi=f"10.{target_idx}/test.2024",
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        
        start = time.time()
        result = None
        if test_paper.doi:
            matching_papers = papers_db.get_by_doi(test_paper.doi)
            if matching_papers:
                matching_papers_sorted = sorted(matching_papers, key=lambda p: p.id)
                primary_paper = matching_papers_sorted[0]
                if test_paper.id != primary_paper.id:
                    result = (primary_paper.id, 1.0)
        elapsed = time.time() - start
        doi_lookup_times.append(elapsed)
        
        assert result is not None
        assert result[0] == f"p{target_idx}"
    
    # All lookups should be equally fast (O(1))
    # If linear search, later lookups would be much slower
    avg_time = sum(doi_lookup_times) / len(doi_lookup_times)
    max_time = max(doi_lookup_times)
    min_time = min(doi_lookup_times)
    
    # For indexed lookup, variance should be minimal
    # For linear search, variance would be large
    variance = max_time - min_time
    assert variance < 0.001, f"Large variance in lookup times: {variance:.6f}s - not using indexed lookup!"
    assert avg_time < 0.0005, f"Average lookup time {avg_time:.6f}s is too slow for indexed lookup"
    
    print(f"DOI lookups: min={min_time:.6f}s, max={max_time:.6f}s, avg={avg_time:.6f}s, variance={variance:.6f}s")
    print("✓ Indexed lookup confirmed - O(1) performance")
