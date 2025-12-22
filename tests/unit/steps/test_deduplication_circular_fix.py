"""
Test to verify deduplication fix for circular duplicate issue.

This test reproduces the reported issue: loading the same papers twice
creates exact DOI duplicates that should be correctly identified without
marking all papers as cancelled.

See: https://github.com/iheitlager/paper-scanner/issues/XXX
"""

from pathlib import Path

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper, PaperType
from paper_scanner.steps.deduplication import DeduplicationStep


class TestDeduplicationCircularFix:
    """Test suite for deduplication circular dependency fix."""
    
    def test_load_same_papers_twice_creates_correct_duplicates(self):
        """
        Test that loading the same 5 papers twice (creating 10 records with 5 unique DOIs)
        correctly identifies 5 duplicates without creating circular dependencies.
        
        This was the reported issue: all 10 papers were being marked as cancelled.
        """
        papers_db = PapersDatabase()
        
        # Load first batch: 5 unique papers
        for i in range(1, 6):
            paper = Paper(
                id=f"paper-{i}",
                cite_key=f"author{i}2024",
                title=f"Paper {i}: Research Topic {i}",
                authors=[Author(family_name=f"Author{i}", given_name="A", full_name=f"A Author{i}")],
                doi=f"10.1234/paper.2024.{i:03d}",
                paper_type=PaperType.JOURNAL_ARTICLE
            )
            papers_db.add(paper)
        
        # Load second batch: same 5 papers (duplicate DOIs, different IDs)
        for i in range(1, 6):
            paper = Paper(
                id=f"paper-{5+i}",  # Different IDs
                cite_key=f"author{i}2024b",
                title=f"Paper {i}: Research Topic {i}",
                authors=[Author(family_name=f"Author{i}", given_name="A", full_name=f"A Author{i}")],
                doi=f"10.1234/paper.2024.{i:03d}",  # SAME DOIs
                paper_type=PaperType.JOURNAL_ARTICLE
            )
            papers_db.add(paper)
        
        # Run deduplication
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        step = DeduplicationStep(general_config={}, db=papers_db, cache_dir=Path("/tmp"))
        result = step.execute(config=config)
        
        # Verify: should find exactly 5 duplicates (one per unique DOI)
        assert result['duplicates_found'] == 5, \
            f"Expected 5 duplicates, got {result['duplicates_found']}"
        
        # Verify: should have 5 primary and 5 duplicates
        primary_count = papers_db.count(primary_only=True)
        duplicate_count = sum(1 for p in papers_db.to_list(primary_only=False) if p.duplicate_of is not None)
        
        assert primary_count == 5, f"Expected 5 primary papers, got {primary_count}"
        assert duplicate_count == 5, f"Expected 5 duplicates, got {duplicate_count}"
    
    def test_deterministic_primary_selection_by_id(self):
        """
        Test that when multiple papers share a DOI, the paper with the
        lexicographically smallest ID is selected as primary.
        """
        papers_db = PapersDatabase()
        
        # Add papers in order of addition with same DOI
        papers_db.add(Paper(
            id="z-paper", cite_key="z", title="Test Paper",
            authors=[Author(family_name="Test", given_name="T", full_name="T Test")],
            doi="10.1111/test", paper_type=PaperType.JOURNAL_ARTICLE
        ))
        papers_db.add(Paper(
            id="a-paper", cite_key="a", title="Test Paper",
            authors=[Author(family_name="Test", given_name="T", full_name="T Test")],
            doi="10.1111/test", paper_type=PaperType.JOURNAL_ARTICLE
        ))
        papers_db.add(Paper(
            id="m-paper", cite_key="m", title="Test Paper",
            authors=[Author(family_name="Test", given_name="T", full_name="T Test")],
            doi="10.1111/test", paper_type=PaperType.JOURNAL_ARTICLE
        ))
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        step = DeduplicationStep(general_config={}, db=papers_db, cache_dir=Path("/tmp"))
        step.execute(config=config)
        
        # z-paper should be primary (first added)
        z_paper = papers_db.get_by_id("z-paper")
        assert z_paper.duplicate_of is None, \
            f"Expected z-paper to be primary, but it's marked as duplicate of {z_paper.duplicate_of}"
        
        # z-paper and m-paper should both be duplicates of a-paper
        a_paper = papers_db.get_by_id("a-paper")
        m_paper = papers_db.get_by_id("m-paper")
        
        assert a_paper.duplicate_of is not None, "Expected a-paper to be marked as duplicate"
        assert a_paper.duplicate_of.id == "z-paper", \
            f"Expected a-paper to be duplicate of z-paper, got {a_paper.duplicate_of.id}"
        
        assert m_paper.duplicate_of is not None, "Expected m-paper to be marked as duplicate"
        assert m_paper.duplicate_of.id == "z-paper", \
            f"Expected m-paper to be duplicate of z-paper, got {m_paper.duplicate_of.id}"
    
    def test_no_circular_dependencies_in_duplicates(self):
        """
        Test that no circular dependencies are created where paper A is marked
        as duplicate of B and B is marked as duplicate of A.
        """
        papers_db = PapersDatabase()
        
        # Add two papers with same DOI
        papers_db.add(Paper(
            id="paper-1", cite_key="p1", title="Paper One",
            authors=[Author(family_name="Smith", given_name="J", full_name="J Smith")],
            doi="10.9999/dup", paper_type=PaperType.JOURNAL_ARTICLE
        ))
        papers_db.add(Paper(
            id="paper-2", cite_key="p2", title="Paper One",
            authors=[Author(family_name="Smith", given_name="J", full_name="J Smith")],
            doi="10.9999/dup", paper_type=PaperType.JOURNAL_ARTICLE
        ))
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        step = DeduplicationStep(general_config={}, db=papers_db, cache_dir=Path("/tmp"))
        step.execute(config=config)
        
        p1 = papers_db.get_by_id("paper-1")
        p2 = papers_db.get_by_id("paper-2")
        
        # Exactly one should be primary, one should be duplicate
        is_p1_primary = p1.duplicate_of is None
        is_p2_primary = p2.duplicate_of is None
        
        assert is_p1_primary or is_p2_primary, \
            "At least one paper must be primary (not marked as duplicate)"
        
        assert not (is_p1_primary and is_p2_primary), \
            "Both papers cannot be primary - one must be marked as duplicate"
        
        # If p2 is duplicate, it should point to p1
        if not is_p2_primary:
            assert p2.duplicate_of.id == "paper-1", \
                "Duplicate should point to primary paper"
    
    def test_large_batch_with_many_duplicates(self):
        """
        Test deduplication with a larger dataset containing multiple duplicate groups.
        """
        papers_db = PapersDatabase()
        
        # Create 3 groups of papers with duplicates
        # Group 1: 3 papers with same DOI
        for i in range(1, 4):
            papers_db.add(Paper(
                id=f"group1-{i}", cite_key=f"g1p{i}", title="Group 1 Paper",
                authors=[Author(family_name="Author1", given_name="A", full_name="A Author1")],
                doi="10.1111/group1", paper_type=PaperType.JOURNAL_ARTICLE
            ))
        
        # Group 2: 2 papers with same DOI
        for i in range(1, 3):
            papers_db.add(Paper(
                id=f"group2-{i}", cite_key=f"g2p{i}", title="Group 2 Paper",
                authors=[Author(family_name="Author2", given_name="A", full_name="A Author2")],
                doi="10.2222/group2", paper_type=PaperType.JOURNAL_ARTICLE
            ))
        
        # Group 3: 4 papers with same DOI
        for i in range(1, 5):
            papers_db.add(Paper(
                id=f"group3-{i}", cite_key=f"g3p{i}", title="Group 3 Paper",
                authors=[Author(family_name="Author3", given_name="A", full_name="A Author3")],
                doi="10.3333/group3", paper_type=PaperType.JOURNAL_ARTICLE
            ))
        
        config = {
            "methods": [
                {"method": "doi_exact", "priority": 1},
            ]
        }
        step = DeduplicationStep(general_config={}, db=papers_db, cache_dir=Path("/tmp"))
        result = step.execute(config=config)
        
        # Should find 2 + 1 + 3 = 6 duplicates (one less per group)
        assert result['duplicates_found'] == 6, \
            f"Expected 6 duplicates (3-1 + 2-1 + 4-1), got {result['duplicates_found']}"
        
        # Should have 3 primary papers (one per group)
        primary_count = papers_db.count(primary_only=True)
        assert primary_count == 3, f"Expected 3 primary papers (one per group), got {primary_count}"
