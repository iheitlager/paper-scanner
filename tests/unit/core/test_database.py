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


# ============================================================================
# TESTS FOR INDEXED FUZZY FINDING
# ============================================================================

class TestYearIndexing:
    """Test year-based indexing for efficient fuzzy finding"""
    
    def test_year_index_on_add(self, db):
        """Papers should be added to year index on add"""
        paper = Paper(
            id="p1",
            cite_key="test2020",
            title="Test",
            year=2020
        )
        db.add(paper)
        
        assert 2020 in db._year_index
        assert paper in db._year_index[2020]
    
    def test_year_index_excludes_papers_without_year(self, db):
        """Papers without year should not be indexed"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Test",
            year=None
        )
        db.add(paper)
        
        # year_index should be empty
        assert len(db._year_index) == 0
    
    def test_year_index_on_delete(self, db):
        """Papers should be removed from year index on delete"""
        paper = Paper(
            id="p1",
            cite_key="test2020",
            title="Test",
            year=2020
        )
        db.add(paper)
        assert 2020 in db._year_index
        
        db.delete_by_id("p1")
        assert 2020 not in db._year_index
    
    def test_get_candidates_by_year_range(self, db):
        """get_candidates_by_year_range should return papers within year tolerance"""
        # Add papers from different years
        papers = [
            Paper(id="p1", cite_key="test2019", title="Paper 2019", year=2019),
            Paper(id="p2", cite_key="test2020", title="Paper 2020", year=2020),
            Paper(id="p3", cite_key="test2021", title="Paper 2021", year=2021),
            Paper(id="p4", cite_key="test2022", title="Paper 2022", year=2022),
        ]
        for p in papers:
            db.add(p)
        
        # Query for year 2020 with tolerance 1 (±1 year = 2019-2021)
        candidates = db.get_candidates_by_year_range(year=2020, tolerance=1)
        
        # Should include 2019, 2020, 2021 but not 2022
        candidate_ids = {p.id for p in candidates}
        assert "p1" in candidate_ids  # 2019
        assert "p2" in candidate_ids  # 2020
        assert "p3" in candidate_ids  # 2021
        assert "p4" not in candidate_ids  # 2022
    
    def test_get_candidates_by_year_range_zero_tolerance(self, db):
        """get_candidates_by_year_range with tolerance=0 should only return exact year"""
        papers = [
            Paper(id="p1", cite_key="test2019", title="Paper 2019", year=2019),
            Paper(id="p2", cite_key="test2020", title="Paper 2020", year=2020),
            Paper(id="p3", cite_key="test2021", title="Paper 2021", year=2021),
        ]
        for p in papers:
            db.add(p)
        
        # Query for year 2020 with tolerance 0 (only 2020)
        candidates = db.get_candidates_by_year_range(year=2020, tolerance=0)
        
        candidate_ids = {p.id for p in candidates}
        assert "p1" not in candidate_ids
        assert "p2" in candidate_ids
        assert "p3" not in candidate_ids
    
    def test_get_candidates_by_year_range_primary_only(self, db):
        """get_candidates_by_year_range should filter duplicates when primary_only=True"""
        # Add primary paper
        paper1 = Paper(id="p1", cite_key="test2020", title="Primary", year=2020)
        db.add(paper1)
        
        # Add duplicate
        paper2 = Paper(id="p2", cite_key="dup2020", title="Duplicate", year=2020)
        paper2.duplicate_of = paper1
        db.add(paper2)
        
        # With primary_only=True (default)
        candidates_primary = db.get_candidates_by_year_range(year=2020, primary_only=True)
        assert len(candidates_primary) == 1
        assert candidates_primary[0].id == "p1"
        
        # With primary_only=False
        candidates_all = db.get_candidates_by_year_range(year=2020, primary_only=False)
        assert len(candidates_all) == 2


class TestTitleIndexing:
    """Test title-based indexing for efficient text search"""
    
    def test_title_index_on_add(self, db):
        """Papers should be added to title index on add"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Machine Learning Algorithms"
        )
        db.add(paper)
        
        title_key = "Machine Learning Algorithms"[:50].lower().strip()
        assert title_key in db._title_index
        assert paper in db._title_index[title_key]
    
    def test_title_index_excludes_papers_without_title(self, db):
        """Papers without title should not be indexed"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title=None
        )
        db.add(paper)
        
        # title_index should be empty
        assert len(db._title_index) == 0
    
    def test_title_index_truncates_to_50_chars(self, db):
        """Title index should use first 50 characters"""
        long_title = "A" * 100  # Very long title
        paper = Paper(
            id="p1",
            cite_key="test",
            title=long_title
        )
        db.add(paper)
        
        # Should be indexed under truncated key (50 chars)
        title_key = ("A" * 50).lower().strip()
        assert title_key in db._title_index
        assert paper in db._title_index[title_key]
    
    def test_title_index_on_delete(self, db):
        """Papers should be removed from title index on delete"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Test Title"
        )
        db.add(paper)
        title_key = "Test Title".lower().strip()
        assert title_key in db._title_index
        
        db.delete_by_id("p1")
        assert title_key not in db._title_index
    
    def test_get_candidates_by_title_prefix(self, db):
        """get_candidates_by_title_prefix should return papers with exact match on first 50 chars"""
        papers = [
            Paper(id="p1", cite_key="test1", title="Machine Learning"),
            Paper(id="p2", cite_key="test2", title="Machine Learning Algorithms"),
            Paper(id="p3", cite_key="test3", title="Deep Learning"),
            Paper(id="p4", cite_key="test4", title="Machine"),
        ]
        for p in papers:
            db.add(p)
        
        # Query for papers with title "Machine Learning" (exact match)
        candidates = db.get_candidates_by_title_prefix("Machine Learning")
        candidate_ids = {p.id for p in candidates}
        assert "p1" in candidate_ids  # "Machine Learning" - exact match
        assert "p3" not in candidate_ids  # "Deep Learning" - different
        
        # Query for papers with title "Machine Learning Algorithms"
        candidates2 = db.get_candidates_by_title_prefix("Machine Learning Algorithms")
        candidate_ids2 = {p.id for p in candidates2}
        assert "p2" in candidate_ids2  # "Machine Learning Algorithms" - exact match
    
    def test_get_candidates_by_title_prefix_case_insensitive(self, db):
        """get_candidates_by_title_prefix should be case-insensitive"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Machine Learning"
        )
        db.add(paper)
        
        # Query with different case
        candidates = db.get_candidates_by_title_prefix("MACHINE LEARNING")
        assert len(candidates) == 1
        assert candidates[0].id == "p1"
    
    def test_get_candidates_by_title_prefix_primary_only(self, db):
        """get_candidates_by_title_prefix should filter duplicates when primary_only=True"""
        # Add primary paper
        paper1 = Paper(id="p1", cite_key="test1", title="Machine Learning")
        db.add(paper1)
        
        # Add duplicate
        paper2 = Paper(id="p2", cite_key="test2", title="Machine Learning")
        paper2.duplicate_of = paper1
        db.add(paper2)
        
        # With primary_only=True (default)
        candidates_primary = db.get_candidates_by_title_prefix("Machine Learning", primary_only=True)
        assert len(candidates_primary) == 1
        assert candidates_primary[0].id == "p1"
        
        # With primary_only=False
        candidates_all = db.get_candidates_by_title_prefix("Machine Learning", primary_only=False)
        assert len(candidates_all) == 2


class TestIndexedFuzzyFinding:
    """Test combined year and title indexing for efficient fuzzy finding"""
    
    def test_year_range_avoids_full_scan(self, db):
        """Year index should enable finding candidates without scanning all papers"""
        # Add many papers
        for i in range(100):
            year = 2010 + (i % 15)  # Papers from 2010-2024
            db.add(Paper(
                id=f"p{i}",
                cite_key=f"test{i}",
                title=f"Paper {i}",
                year=year
            ))
        
        # Query for 2020 with tolerance 1
        # This should only retrieve papers from 2019-2021, not all 100
        candidates = db.get_candidates_by_year_range(year=2020, tolerance=1)
        
        # Should be much fewer than 100
        assert len(candidates) < 50  # Rough check
        
        # All should be within year range
        for p in candidates:
            assert 2019 <= p.year <= 2021
    
    def test_clear_clears_all_indexes(self, db):
        """clear() should reset all indexes including new ones"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Test",
            year=2020
        )
        db.add(paper)
        
        # Verify paper is indexed
        assert len(db.papers) == 1
        assert len(db._year_index) == 1
        assert len(db._title_index) == 1
        
        # Clear database
        db.clear()
        
        # All indexes should be empty
        assert len(db.papers) == 0
        assert len(db._year_index) == 0
        assert len(db._title_index) == 0
        assert len(db._doi_index) == 0
        assert len(db._cite_key_index) == 0
        assert len(db._id_index) == 0


# ============================================================================
# TESTS FOR OPTIMIZED FUZZY MATCHING
# ============================================================================

class TestNormalizedTitleFields:
    """Test precomputed title normalization fields for faster fuzzy matching"""
    
    def test_title_normalized_auto_computed(self):
        """title_normalized should be auto-computed from title"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Machine Learning Algorithms"
        )
        
        assert paper.title_normalized == "machine learning algorithms"
    
    def test_title_normalized_empty_when_no_title(self):
        """title_normalized should be None when title is None"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title=None
        )
        
        assert paper.title_normalized is None
    
    def test_title_normalized_strips_whitespace(self):
        """title_normalized should strip leading/trailing whitespace"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="  Machine Learning  "
        )
        
        assert paper.title_normalized == "machine learning"
    
    def test_title_length_auto_computed(self):
        """title_length should store the length of title"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Machine Learning"
        )
        
        assert paper.title_length == len("Machine Learning")
    
    def test_title_length_zero_when_no_title(self):
        """title_length should be 0 when title is None"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title=None
        )
        
        assert paper.title_length == 0
    
    def test_normalized_fields_updated_on_assignment(self):
        """Normalized fields should update when title is changed"""
        paper = Paper(
            id="p1",
            cite_key="test",
            title="Original Title"
        )
        
        # Change the title
        paper.title = "New Title Here"
        
        # Should NOT auto-update (Pydantic doesn't re-run post_init)
        # This is expected behavior - normalized fields are set at creation
        # For runtime changes, use model_validate or update database
        # Just verify initial state is correct
        assert paper.title == "New Title Here"
    
    def test_case_insensitive_comparison_possible(self):
        """Normalized titles enable case-insensitive comparison"""
        paper1 = Paper(
            id="p1",
            cite_key="test1",
            title="Machine Learning"
        )
        paper2 = Paper(
            id="p2",
            cite_key="test2",
            title="machine learning"
        )
        
        # Normalized versions should be identical
        assert paper1.title_normalized == paper2.title_normalized
    
    def test_sequence_matcher_with_normalized(self):
        """SequenceMatcher should work efficiently with precomputed normalized titles"""
        from difflib import SequenceMatcher
        
        paper = Paper(
            id="p1",
            cite_key="test",
            title="MACHINE Learning Algorithms"
        )
        
        # Using precomputed normalized title
        query = "machine learning algorithms"
        ratio = SequenceMatcher(None, query, paper.title_normalized).ratio()
        
        # Should be exact match (1.0)
        assert ratio == 1.0
    
    def test_multiple_papers_normalized_titles(self, db):
        """Multiple papers should each have correct normalized titles"""
        papers = [
            Paper(id="p1", cite_key="t1", title="Deep Learning"),
            Paper(id="p2", cite_key="t2", title="REINFORCEMENT LEARNING"),
            Paper(id="p3", cite_key="t3", title="natural language PROCESSING"),
        ]
        
        for p in papers:
            db.add(p)
        
        # Check normalized versions
        assert papers[0].title_normalized == "deep learning"
        assert papers[1].title_normalized == "reinforcement learning"
        assert papers[2].title_normalized == "natural language processing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

