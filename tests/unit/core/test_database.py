"""
Tests for PapersDatabase class

Tests CRUD operations, indexing, duplicate handling, and filtering.
"""

import pytest
from datetime import datetime, timezone

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper, Author


@pytest.fixture
def db():
    """Create a fresh database for each test"""
    return PapersDatabase()


@pytest.fixture
def sample_paper():
    """Create a sample paper for testing"""
    return Paper(
        id="paper_1",
        cite_key="smith2020",
        title="Sample Paper Title",
        abstract="This is a sample abstract",
        doi="10.1234/sample.2020",
        year=2020,
        authors=[
            Author(
                given_name="John",
                family_name="Smith",
                full_name="John Smith"
            )
        ],
        journal="Test Journal"
    )


@pytest.fixture
def sample_papers():
    """Create multiple sample papers for testing"""
    return [
        Paper(
            id="paper_1",
            cite_key="smith2020",
            title="First Paper",
            abstract="Abstract 1",
            doi="10.1111/first",
            year=2020,
            journal="Journal A"
        ),
        Paper(
            id="paper_2",
            cite_key="jones2021",
            title="Second Paper",
            abstract="Abstract 2",
            doi="10.2222/second",
            year=2021,
            journal="Journal B"
        ),
        Paper(
            id="paper_3",
            cite_key="brown2022",
            title="Third Paper",
            abstract="Abstract 3",
            doi="10.3333/third",
            year=2022,
            journal="Journal C"
        ),
    ]


class TestCreate:
    """Tests for CREATE operations"""
    
    def test_add_single_paper(self, db, sample_paper):
        """Test adding a single paper"""
        db.add(sample_paper)
        assert len(db.papers) == 1
        assert db.papers[0] is sample_paper
    
    def test_add_multiple_papers_individually(self, db, sample_papers):
        """Test adding multiple papers one by one"""
        for paper in sample_papers:
            db.add(paper)
        assert len(db.papers) == 3
    
    def test_add_many_papers(self, db, sample_papers):
        """Test adding multiple papers at once"""
        db.add_many(sample_papers)
        assert len(db.papers) == 3
    
    def test_add_duplicate_cite_key_raises_error(self, db, sample_paper):
        """Test that adding paper with duplicate cite_key raises error"""
        db.add(sample_paper)
        
        duplicate = Paper(
            id="paper_dup",
            cite_key="smith2020",  # Same cite_key
            title="Different Paper",
            abstract="Different abstract"
        )
        
        with pytest.raises(ValueError, match="cite_key"):
            db.add(duplicate)
    
    def test_add_duplicate_id_raises_error(self, db, sample_paper):
        """Test that adding paper with duplicate ID raises error"""
        db.add(sample_paper)
        
        duplicate = Paper(
            id="paper_1",  # Same ID
            cite_key="different_key",
            title="Different Paper",
            abstract="Different abstract"
        )
        
        with pytest.raises(ValueError, match="id"):
            db.add(duplicate)


class TestRead:
    """Tests for READ operations"""
    
    def test_all_returns_all_papers(self, db, sample_papers):
        """Test that all() returns all papers"""
        db.add_many(sample_papers)
        assert db.all() == sample_papers
    
    def test_all_with_primary_only_false_includes_duplicates(self, db, sample_papers):
        """Test that all(primary_only=False) includes duplicates"""
        db.add_many(sample_papers)
        # Mark paper_2 as duplicate of paper_1
        sample_papers[1].duplicate_of = sample_papers[0]
        db.update(sample_papers[1])
        
        result = db.all(primary_only=False)
        assert len(result) == 3
    
    def test_all_with_primary_only_true_excludes_duplicates(self, db, sample_papers):
        """Test that all(primary_only=True) excludes duplicates"""
        db.add_many(sample_papers)
        # Mark paper_2 as duplicate of paper_1
        sample_papers[1].duplicate_of = sample_papers[0]
        db.update(sample_papers[1])
        
        result = db.all(primary_only=True)
        assert len(result) == 2
        assert all(p.duplicate_of is None for p in result)
    
    def test_get_by_id(self, db, sample_paper):
        """Test getting paper by ID"""
        db.add(sample_paper)
        result = db.get_by_id("paper_1")
        assert result is sample_paper
    
    def test_get_by_id_not_found(self, db):
        """Test getting non-existent paper by ID returns None"""
        result = db.get_by_id("nonexistent")
        assert result is None
    
    def test_get_by_cite_key(self, db, sample_paper):
        """Test getting paper by cite_key"""
        db.add(sample_paper)
        result = db.get_by_cite_key("smith2020")
        assert result is sample_paper
    
    def test_get_by_cite_key_not_found(self, db):
        """Test getting non-existent paper by cite_key returns None"""
        result = db.get_by_cite_key("nonexistent")
        assert result is None
    
    def test_get_by_doi_single_paper(self, db, sample_paper):
        """Test getting paper by DOI when only one paper has it"""
        db.add(sample_paper)
        result = db.get_by_doi("10.1234/sample.2020")
        assert len(result) == 1
        assert result[0] is sample_paper
    
    def test_get_by_doi_multiple_papers(self, db):
        """Test getting multiple papers with same DOI"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            doi="10.1234/duplicate"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            doi="10.1234/duplicate"
        )
        db.add_many([paper1, paper2])
        
        result = db.get_by_doi("10.1234/duplicate")
        assert len(result) == 2
        assert paper1 in result
        assert paper2 in result
    
    def test_get_by_doi_case_insensitive(self, db, sample_paper):
        """Test that DOI lookup is case-insensitive"""
        db.add(sample_paper)
        result = db.get_by_doi("10.1234/SAMPLE.2020")
        assert len(result) == 1
        assert result[0] is sample_paper
    
    def test_get_by_doi_primary_only_filter(self, db):
        """Test that get_by_doi respects primary_only filter"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            doi="10.1234/test"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            doi="10.1234/test"
        )
        paper2.duplicate_of = paper1
        db.add_many([paper1, paper2])
        
        all_papers = db.get_by_doi("10.1234/test", primary_only=False)
        assert len(all_papers) == 2
        
        primary_papers = db.get_by_doi("10.1234/test", primary_only=True)
        assert len(primary_papers) == 1
        assert primary_papers[0] is paper1
    
    def test_get_by_doi_not_found(self, db):
        """Test getting papers with non-existent DOI"""
        result = db.get_by_doi("10.9999/nonexistent")
        assert result == []
    
    def test_find_by_predicate(self, db, sample_papers):
        """Test finding papers by predicate function"""
        db.add_many(sample_papers)
        
        # Find papers from 2020
        result = db.find(lambda p: p.year == 2020)
        assert len(result) == 1
        assert result[0].year == 2020
    
    def test_find_by_predicate_multiple_matches(self, db, sample_papers):
        """Test finding multiple papers by predicate"""
        # Add papers from same year
        sample_papers[1].year = 2020
        db.add_many(sample_papers)
        
        result = db.find(lambda p: p.year == 2020)
        assert len(result) == 2
    
    def test_find_by_predicate_primary_only(self, db):
        """Test that find respects primary_only filter"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            year=2020
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            year=2020
        )
        paper2.duplicate_of = paper1
        db.add_many([paper1, paper2])
        
        all_matches = db.find(lambda p: p.year == 2020, primary_only=False)
        assert len(all_matches) == 2
        
        primary_matches = db.find(lambda p: p.year == 2020, primary_only=True)
        assert len(primary_matches) == 1


class TestUpdate:
    """Tests for UPDATE operations"""
    
    def test_update_paper_properties(self, db, sample_paper):
        """Test updating paper properties"""
        db.add(sample_paper)
        
        # Modify paper
        sample_paper.title = "Updated Title"
        db.update(sample_paper)
        
        result = db.get_by_id("paper_1")
        assert result.title == "Updated Title"
    
    def test_update_paper_not_found(self, db):
        """Test updating non-existent paper raises error"""
        paper = Paper(
            id="nonexistent",
            cite_key="key",
            title="Paper"
        )
        
        with pytest.raises(ValueError, match="not found"):
            db.update(paper)
    
    def test_update_doi_updates_index(self, db):
        """Test that updating DOI updates the index"""
        paper = Paper(
            id="paper_1",
            cite_key="smith2020",
            title="Sample Paper Title",
            doi="10.1234/sample.2020"
        )
        db.add(paper)
        
        # Create new paper object with updated DOI
        updated_paper = Paper(
            id="paper_1",
            cite_key="smith2020",
            title="Sample Paper Title",
            doi="10.9999/updated"
        )
        db.update(updated_paper)
        
        # Old DOI should not find paper
        old_result = db.get_by_doi("10.1234/sample.2020")
        assert len(old_result) == 0
        
        # New DOI should find paper
        new_result = db.get_by_doi("10.9999/updated")
        assert len(new_result) == 1
    
    def test_update_cite_key_updates_index(self, db):
        """Test that updating cite_key updates the index"""
        paper = Paper(
            id="paper_1",
            cite_key="smith2020",
            title="Sample Paper Title"
        )
        db.add(paper)
        
        # Create new paper object with updated cite_key
        updated_paper = Paper(
            id="paper_1",
            cite_key="newendkey",
            title="Sample Paper Title"
        )
        db.update(updated_paper)
        
        # Old key should not find paper
        assert db.get_by_cite_key("smith2020") is None
        
        # New key should find paper
        assert db.get_by_cite_key("newendkey") is not None
    
    def test_update_cite_key_conflict_raises_error(self, db, sample_papers):
        """Test that updating cite_key to existing one raises error"""
        db.add_many(sample_papers)
        
        # Try to change paper_1's cite_key to paper_2's (create new object)
        conflicting_paper = Paper(
            id="paper_1",
            cite_key="jones2021",  # Trying to use paper_2's cite_key
            title="Updated Paper 1"
        )
        
        with pytest.raises(ValueError, match="conflicts"):
            db.update(conflicting_paper)
    
    def test_update_many_papers(self, db, sample_papers):
        """Test updating multiple papers at once"""
        db.add_many(sample_papers)
        
        # Modify all papers
        for paper in sample_papers:
            paper.title = f"Updated: {paper.title}"
        
        db.update_many(sample_papers)
        
        # Verify updates
        for paper in sample_papers:
            result = db.get_by_id(paper.id)
            assert result.title.startswith("Updated:")


class TestDelete:
    """Tests for DELETE operations"""
    
    def test_delete_by_id(self, db, sample_paper):
        """Test deleting paper by ID"""
        db.add(sample_paper)
        result = db.delete_by_id("paper_1")
        
        assert result is True
        assert len(db.papers) == 0
        assert db.get_by_id("paper_1") is None
    
    def test_delete_by_id_not_found(self, db):
        """Test deleting non-existent paper returns False"""
        result = db.delete_by_id("nonexistent")
        assert result is False
    
    def test_delete_by_cite_key(self, db, sample_paper):
        """Test deleting paper by cite_key"""
        db.add(sample_paper)
        result = db.delete_by_cite_key("smith2020")
        
        assert result is True
        assert len(db.papers) == 0
    
    def test_delete_by_cite_key_not_found(self, db):
        """Test deleting by non-existent cite_key returns False"""
        result = db.delete_by_cite_key("nonexistent")
        assert result is False
    
    def test_delete_removes_from_indexes(self, db, sample_paper):
        """Test that delete removes paper from all indexes"""
        db.add(sample_paper)
        db.delete_by_id("paper_1")
        
        assert db.get_by_id("paper_1") is None
        assert db.get_by_cite_key("smith2020") is None
        assert db.get_by_doi("10.1234/sample.2020") == []
    
    def test_delete_many_by_id(self, db, sample_papers):
        """Test deleting multiple papers by ID"""
        db.add_many(sample_papers)
        
        count = db.delete_many_by_id(["paper_1", "paper_2"])
        
        assert count == 2
        assert len(db.papers) == 1
        assert db.get_by_id("paper_3") is not None
    
    def test_delete_many_by_id_partial_not_found(self, db, sample_papers):
        """Test deleting with some IDs not found"""
        db.add_many(sample_papers)
        
        count = db.delete_many_by_id(["paper_1", "nonexistent", "paper_2"])
        
        assert count == 2  # Only 2 deleted
        assert len(db.papers) == 1
    
    def test_clear_removes_all_papers(self, db, sample_papers):
        """Test clearing database"""
        db.add_many(sample_papers)
        db.clear()
        
        assert len(db.papers) == 0
        assert len(db._doi_index) == 0
        assert len(db._cite_key_index) == 0
        assert len(db._id_index) == 0


class TestQuery:
    """Tests for QUERY operations"""
    
    def test_count_all_papers(self, db, sample_papers):
        """Test counting all papers"""
        db.add_many(sample_papers)
        assert db.count() == 3
    
    def test_count_primary_only(self, db, sample_papers):
        """Test counting only primary papers"""
        db.add_many(sample_papers)
        sample_papers[1].duplicate_of = sample_papers[0]
        db.update(sample_papers[1])
        
        assert db.count(primary_only=False) == 3
        assert db.count(primary_only=True) == 2
    
    def test_count_duplicates(self, db):
        """Test counting duplicates by DOI"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            doi="10.1234/test"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            doi="10.1234/test"
        )
        db.add_many([paper1, paper2])
        
        assert db.count_duplicates("10.1234/test") == 2
    
    def test_count_duplicates_not_found(self, db):
        """Test counting duplicates for non-existent DOI"""
        assert db.count_duplicates("10.9999/nonexistent") == 0
    
    def test_get_duplicate_groups(self, db):
        """Test getting duplicate groups"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            doi="10.1111/test"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            doi="10.1111/test"
        )
        paper3 = Paper(
            id="p3",
            cite_key="key3",
            title="Paper 3",
            doi="10.2222/unique"
        )
        db.add_many([paper1, paper2, paper3])
        
        groups = db.get_duplicate_groups()
        
        # Should only have one group (the one with 2 papers)
        assert len(groups) == 1
        assert "10.1111/test" in groups
        assert len(groups["10.1111/test"]) == 2
    
    def test_exists_by_id(self, db, sample_paper):
        """Test checking if paper exists by ID"""
        assert db.exists_by_id("paper_1") is False
        
        db.add(sample_paper)
        assert db.exists_by_id("paper_1") is True
    
    def test_exists_by_cite_key(self, db, sample_paper):
        """Test checking if paper exists by cite_key"""
        assert db.exists_by_cite_key("smith2020") is False
        
        db.add(sample_paper)
        assert db.exists_by_cite_key("smith2020") is True
    
    def test_exists_by_doi(self, db, sample_paper):
        """Test checking if paper with DOI exists"""
        assert db.exists_by_doi("10.1234/sample.2020") is False
        
        db.add(sample_paper)
        assert db.exists_by_doi("10.1234/sample.2020") is True


class TestBatchOperations:
    """Tests for batch operations"""
    
    def test_to_list(self, db, sample_papers):
        """Test converting database to list"""
        db.add_many(sample_papers)
        result = db.to_list()
        
        assert len(result) == 3
        assert all(p in result for p in sample_papers)
    
    def test_to_list_primary_only(self, db, sample_papers):
        """Test converting database to list with primary_only filter"""
        db.add_many(sample_papers)
        sample_papers[1].duplicate_of = sample_papers[0]
        db.update(sample_papers[1])
        
        result = db.to_list(primary_only=True)
        assert len(result) == 2
    
    def test_from_list_replaces_database(self, db, sample_papers):
        """Test loading papers from list replaces existing"""
        paper1 = Paper(
            id="initial",
            cite_key="initial_key",
            title="Initial Paper"
        )
        db.add(paper1)
        
        db.from_list(sample_papers)
        
        assert len(db.papers) == 3
        assert db.get_by_id("initial") is None
        assert all(p in db.papers for p in sample_papers)


class TestStatistics:
    """Tests for statistics"""
    
    def test_get_stats_empty_database(self, db):
        """Test getting stats from empty database"""
        stats = db.get_stats()
        
        assert stats["total_papers"] == 0
        assert stats["primary_papers"] == 0
        assert stats["duplicate_papers"] == 0
    
    def test_get_stats_with_papers(self, db):
        """Test getting stats with papers"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1",
            doi="10.1234/test"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2",
            doi="10.1234/test"
        )
        db.add_many([paper1, paper2])
        
        stats = db.get_stats()
        
        assert stats["total_papers"] == 2
        assert stats["primary_papers"] == 2
        assert stats["papers_with_doi"] == 2
        assert stats["unique_dois"] == 1
        assert stats["duplicate_groups"] == 1
    
    def test_get_stats_with_duplicates(self, db):
        """Test stats with duplicate marking"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2"
        )
        paper2.duplicate_of = paper1
        db.add_many([paper1, paper2])
        
        stats = db.get_stats()
        
        assert stats["total_papers"] == 2
        assert stats["primary_papers"] == 1
        assert stats["duplicate_papers"] == 1


class TestSpecialOperations:
    """Tests for special duplicate operations"""
    
    def test_mark_duplicate(self, db, sample_papers):
        """Test marking a paper as duplicate"""
        db.add_many(sample_papers)
        
        db.mark_duplicate("paper_2", "paper_1")
        
        paper2 = db.get_by_id("paper_2")
        assert paper2.duplicate_of is db.get_by_id("paper_1")
    
    def test_mark_duplicate_paper_not_found(self, db, sample_paper):
        """Test marking non-existent paper raises error"""
        db.add(sample_paper)
        
        with pytest.raises(ValueError, match="not found"):
            db.mark_duplicate("nonexistent", "paper_1")
    
    def test_mark_duplicate_primary_not_found(self, db, sample_paper):
        """Test marking as duplicate of non-existent paper raises error"""
        db.add(sample_paper)
        
        with pytest.raises(ValueError, match="not found"):
            db.mark_duplicate("paper_1", "nonexistent")
    
    def test_get_duplicates_of(self, db):
        """Test getting all duplicates of a paper"""
        paper1 = Paper(
            id="p1",
            cite_key="key1",
            title="Paper 1"
        )
        paper2 = Paper(
            id="p2",
            cite_key="key2",
            title="Paper 2"
        )
        paper3 = Paper(
            id="p3",
            cite_key="key3",
            title="Paper 3"
        )
        db.add_many([paper1, paper2, paper3])
        
        # Mark paper2 and paper3 as duplicates of paper1
        db.mark_duplicate("p2", "p1")
        db.mark_duplicate("p3", "p1")
        
        duplicates = db.get_duplicates_of("p1")
        assert len(duplicates) == 2
        assert paper2 in duplicates
        assert paper3 in duplicates
    
    def test_get_duplicates_of_no_duplicates(self, db, sample_paper):
        """Test getting duplicates when none exist"""
        db.add(sample_paper)
        
        duplicates = db.get_duplicates_of("paper_1")
        assert duplicates == []
    
    def test_remove_duplicate_marking(self, db, sample_papers):
        """Test removing duplicate marking"""
        db.add_many(sample_papers)
        db.mark_duplicate("paper_2", "paper_1")
        
        db.remove_duplicate_marking("paper_2")
        
        paper2 = db.get_by_id("paper_2")
        assert paper2.duplicate_of is None
    
    def test_remove_duplicate_marking_not_found(self, db):
        """Test removing duplicate marking from non-existent paper raises error"""
        with pytest.raises(ValueError, match="not found"):
            db.remove_duplicate_marking("nonexistent")


class TestIndexIntegrity:
    """Tests to ensure index integrity is maintained"""
    
    def test_doi_index_consistency_after_add(self, db):
        """Test that DOI index stays consistent after adding"""
        paper = Paper(
            id="p1",
            cite_key="key1",
            title="Paper",
            doi="10.1234/test"
        )
        db.add(paper)
        
        # Verify paper is in index
        assert "10.1234/test" in db._doi_index
        assert paper in db._doi_index["10.1234/test"]
    
    def test_doi_index_case_normalization(self, db):
        """Test that DOI index normalizes case"""
        paper = Paper(
            id="p1",
            cite_key="key1",
            title="Paper",
            doi="10.1234/TEST"
        )
        db.add(paper)
        
        # Lookup should work with different case
        result = db.get_by_doi("10.1234/test")
        assert len(result) == 1
    
    def test_indexes_stay_consistent_after_operations(self, db, sample_papers):
        """Test that all indexes remain consistent after various operations"""
        db.add_many(sample_papers)
        db.update(sample_papers[0])
        db.delete_by_id("paper_2")
        
        # Verify consistency
        assert len(db.papers) == 2
        assert len(db._cite_key_index) == 2
        assert len(db._id_index) == 2
        
        # Verify we can still find papers
        assert db.get_by_id("paper_1") is not None
        assert db.get_by_id("paper_3") is not None
        assert db.get_by_id("paper_2") is None
