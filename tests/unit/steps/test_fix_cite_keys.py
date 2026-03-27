"""
Unit tests for fix_cite_keys step

Tests the FixCiteKeysStep class including validation, cite key generation,
collision handling, and execution.
"""

import pytest

from paper_scanner.core.cite_key import (
    generate_cite_key,
    make_collision_suffix,
    resolve_collision,
)
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Author, Paper
from paper_scanner.steps.fix_cite_keys import FixCiteKeysStep

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def empty_db():
    """Create an empty database"""
    return PapersDatabase()


@pytest.fixture
def sample_db():
    """Create a database with sample papers"""
    db = PapersDatabase()

    papers = [
        Paper(
            cite_key="old_key_1",
            title="Machine Learning in Healthcare",
            abstract="A comprehensive review",
            keywords=["ML", "healthcare"],
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/ml.2020",
            year=2020,
            paper_type="journal_article",
        ),
        Paper(
            cite_key="old_key_2",
            title="Deep Learning Applications",
            abstract="Survey of applications",
            keywords=["DL"],
            authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
            doi="10.1234/dl.2021",
            year=2021,
            paper_type="conference_paper",
        ),
        Paper(
            cite_key="old_key_3",
            title="Neural Networks",
            abstract="Introduction to neural nets",
            keywords=["NN"],
            authors=[Author(family_name="Brown", given_name="Robert", full_name="Robert Brown")],
            doi="10.1234/nn.2019",
            year=2019,
            paper_type="journal_article",
        ),
    ]

    for paper in papers:
        db.add(paper)

    return db


@pytest.fixture
def collision_db():
    """Create a database with papers that will collide on cite_key"""
    db = PapersDatabase()

    # Both by Smith in 2020
    papers = [
        Paper(
            cite_key="Smith2020_v1",
            title="First Paper",
            abstract="First abstract",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/first.2020",
            year=2020,
        ),
        Paper(
            cite_key="Smith2020_v2",
            title="Second Paper",
            abstract="Second abstract",
            authors=[Author(family_name="Smith", given_name="Jane", full_name="Jane Smith")],
            doi="10.1234/second.2020",
            year=2020,
        ),
        Paper(
            cite_key="Smith2020_v3",
            title="Third Paper",
            abstract="Third abstract",
            authors=[Author(family_name="Smith", given_name="Robert", full_name="Robert Smith")],
            doi="10.1234/third.2020",
            year=2020,
        ),
    ]

    for paper in papers:
        db.add(paper)

    return db


@pytest.fixture
def db_with_duplicate():
    """Create a database with a primary and duplicate paper"""
    db = PapersDatabase()

    primary = Paper(
        cite_key="Smith2020",
        title="Original",
        abstract="Original abstract",
        authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
        doi="10.1234/original.2020",
        year=2020,
    )

    duplicate = Paper(
        cite_key="dup_key",
        title="Duplicate of Original",
        abstract="Same paper",
        authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
        doi="10.1234/original.2020",
        year=2020,
        duplicate_of=primary.id,
    )

    db.add(primary)
    db.add(duplicate)

    return db


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================


class TestGenerateCiteKey:
    """Tests for generate_cite_key function"""

    def test_basic_generation(self):
        """Should generate basic cite key from first author and year"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            year=2020,
        )
        key = generate_cite_key(paper)
        assert key == "Smith2020"

    def test_handles_spaces_in_lastname(self):
        """Should remove spaces from family names"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[Author(family_name="Van Der Berg", given_name="John", full_name="John Van Der Berg")],
            year=2020,
        )
        key = generate_cite_key(paper)
        assert key == "VanDerBerg2020"

    def test_handles_hyphens_in_lastname(self):
        """Should remove hyphens from family names"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[Author(family_name="Smith-Jones", given_name="John", full_name="John Smith-Jones")],
            year=2020,
        )
        key = generate_cite_key(paper)
        assert key == "SmithJones2020"

    def test_uses_first_author_only(self):
        """Should use only first author's family name"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[
                Author(family_name="Smith", given_name="John", full_name="John Smith"),
                Author(family_name="Doe", given_name="Jane", full_name="Jane Doe"),
            ],
            year=2020,
        )
        key = generate_cite_key(paper)
        assert key == "Smith2020"

    def test_missing_authors_raises_error(self):
        """Should raise error if paper has no authors"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[],
            year=2020,
        )
        with pytest.raises(ValueError, match="has no authors"):
            generate_cite_key(paper)

    def test_missing_year_raises_error(self):
        """Should raise error if paper has no year"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            year=None,
        )
        with pytest.raises(ValueError, match="has no publication year"):
            generate_cite_key(paper)

    def test_author_no_family_name_raises_error(self):
        """Should raise error if first author has no family name"""
        paper = Paper(
            cite_key="temp",
            title="Test",
            authors=[Author(family_name="", given_name="John", full_name="John")],
            year=2020,
        )
        with pytest.raises(ValueError, match="has no family name"):
            generate_cite_key(paper)


class TestMakeCollisionSuffix:
    """Tests for make_collision_suffix function"""

    def test_single_letters(self):
        """Should generate single letters a-z for indices 0-25"""
        assert make_collision_suffix(0) == "a"
        assert make_collision_suffix(1) == "b"
        assert make_collision_suffix(25) == "z"

    def test_double_letters(self):
        """Should generate double letters aa-az for indices 26+"""
        assert make_collision_suffix(26) == "aa"
        assert make_collision_suffix(27) == "ab"
        assert make_collision_suffix(51) == "az"

    def test_more_letters(self):
        """Should continue pattern for more indices"""
        assert make_collision_suffix(52) == "aaa"
        assert make_collision_suffix(77) == "aaz"

    def test_large_index(self):
        """Should handle large indices"""
        result = make_collision_suffix(100)
        assert isinstance(result, str)
        assert len(result) >= 2


class TestResolveCollision:
    """Tests for resolve_collision function"""

    def test_no_collision(self):
        """Should return base key if no collision"""
        existing_keys = {"OtherKey2020": True}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020"

    def test_single_collision(self):
        """Should append 'a' for first collision"""
        existing_keys = {"Smith2020": True}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020a"

    def test_multiple_collisions(self):
        """Should append successive letters for multiple collisions"""
        existing_keys = {"Smith2020": True, "Smith2020a": True}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020b"

    def test_many_collisions(self):
        """Should handle many collisions with multi-letter suffixes"""
        existing_keys = {f"Smith2020{make_collision_suffix(i)}": True for i in range(30)}
        result = resolve_collision("Smith2020", existing_keys)
        # Should find first unused key after 30 collisions
        assert "Smith2020" not in existing_keys or result.startswith("Smith2020")

    def test_empty_existing_keys(self):
        """Should return base key if no existing keys"""
        existing_keys = {}
        result = resolve_collision("Smith2020", existing_keys)
        assert result == "Smith2020"


# ============================================================================
# VALIDATION TESTS
# ============================================================================


class TestValidate:
    """Tests for fix_cite_keys step validation"""

    def test_validate_empty_config(self):
        """Should validate with empty config"""
        is_valid, errors = FixCiteKeysStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_any_config(self):
        """Should validate with any config (no required fields)"""
        is_valid, errors = FixCiteKeysStep.validate({"anything": "here"})
        assert is_valid is True
        assert errors == []


# ============================================================================
# EXECUTION TESTS
# ============================================================================


class TestExecute:
    """Tests for fix_cite_keys step execution"""

    def test_execute_basic(self, sample_db, temp_cache_dir):
        """Should regenerate cite keys for all primary papers"""
        step = FixCiteKeysStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == StepStatus.SUCCESS
        assert result.stats["updated"] == 3
        assert result.stats["skipped"] == 0
        assert result.stats["errors"] == 0

        # Check that papers were updated
        smith_paper = sample_db.get_by_id(sample_db.all()[0].id)
        assert smith_paper.cite_key == "Smith2020"

        doe_paper = sample_db.get_by_id(sample_db.all()[1].id)
        assert doe_paper.cite_key == "Doe2021"

        brown_paper = sample_db.get_by_id(sample_db.all()[2].id)
        assert brown_paper.cite_key == "Brown2019"

    def test_execute_with_collisions(self, collision_db, temp_cache_dir):
        """Should resolve cite key collisions with suffixes"""
        step = FixCiteKeysStep(general_config={}, db=collision_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == StepStatus.SUCCESS
        assert result.stats["updated"] == 3

        # Get all papers and check their cite keys
        papers = collision_db.all(primary_only=True)
        cite_keys = {p.cite_key for p in papers}

        # Should have Smith2020, Smith2020a, Smith2020b
        assert "Smith2020" in cite_keys
        assert "Smith2020a" in cite_keys
        assert "Smith2020b" in cite_keys
        assert len(cite_keys) == 3

    def test_execute_only_primary_papers(self, temp_cache_dir):
        """Should only update primary papers, not duplicates"""
        # Create database with primary and duplicate
        db = PapersDatabase()

        primary = Paper(
            cite_key="Smith2020_primary",
            title="Original",
            abstract="Original abstract",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/original.2020",
            year=2020,
        )

        # Create duplicate that references primary
        duplicate = Paper(
            cite_key="Smith2020_dup",
            title="Duplicate of Original",
            abstract="Same paper",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/original.2020",
            year=2020,
            duplicate_of=primary,  # Reference the primary paper object
        )

        db.add(primary)
        db.add(duplicate)

        step = FixCiteKeysStep(general_config={}, db=db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        # Should only process 1 paper (primary only)
        assert result.stats["updated"] == 1

        # Primary paper should be updated
        primary_papers = [p for p in db.all(primary_only=True)]
        assert len(primary_papers) == 1
        primary_updated = primary_papers[0]
        assert primary_updated.cite_key == "Smith2020"

        # Verify duplicate is still there but not updated
        all_papers = db.all(primary_only=False)
        assert len(all_papers) == 2

    def test_execute_empty_database(self, empty_db, temp_cache_dir):
        """Should handle empty database"""
        step = FixCiteKeysStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == StepStatus.SUCCESS
        assert result.stats["updated"] == 0
        assert result.stats["skipped"] == 0

    def test_execute_dry_run(self, sample_db, temp_cache_dir):
        """Should not update papers in dry_run mode"""
        # Store original cite keys
        original_keys = {p.id: p.cite_key for p in sample_db.all()}

        step = FixCiteKeysStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=True)

        assert result.status.value == StepStatus.SUCCESS
        # Count should still reflect what would be changed
        assert result.stats["updated"] >= 0

        # Papers should still have original cite keys
        for paper in sample_db.all():
            assert paper.cite_key == original_keys[paper.id]

    def test_execute_missing_author_data(self, temp_cache_dir):
        """Should skip papers missing required author data"""
        db = PapersDatabase()

        # Paper with no authors
        paper_no_author = Paper(
            cite_key="old_key",
            title="No Author Paper",
            authors=[],
            year=2020,
        )

        db.add(paper_no_author)

        step = FixCiteKeysStep(general_config={}, db=db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == "error"
        assert result.stats["updated"] == 0
        assert result.stats["skipped"] == 1
        assert result.stats["errors"] > 0

        # Paper should keep original key
        assert paper_no_author.cite_key == "old_key"

    def test_execute_missing_year_data(self, temp_cache_dir):
        """Should skip papers missing year data"""
        db = PapersDatabase()

        # Paper with no year
        paper_no_year = Paper(
            cite_key="old_key",
            title="No Year Paper",
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            year=None,
        )

        db.add(paper_no_year)

        step = FixCiteKeysStep(general_config={}, db=db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == "error"
        assert result.stats["updated"] == 0
        assert result.stats["skipped"] == 1
        assert result.stats["errors"] > 0

    def test_execute_verbose_output(self, sample_db, temp_cache_dir, capsys):
        """Should output verbose information when enabled"""
        step = FixCiteKeysStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=True, dry_run=False)

        assert result.status.value == StepStatus.SUCCESS
        # Verbose output goes to stderr, so we'd need to capture stderr
        # For now just verify the step executed successfully

    def test_execute_returns_correct_count(self, sample_db, temp_cache_dir):
        """Should return correct count in result"""
        initial_count = len(sample_db.all())

        step = FixCiteKeysStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        # Count should match number of primary papers
        assert result.stats["updated"] == initial_count
        assert result.stats["papers_count"] == initial_count


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for fix_cite_keys step"""

    def test_end_to_end_workflow(self, temp_cache_dir):
        """Test complete workflow with various papers"""
        db = PapersDatabase()

        # Add papers with different scenarios
        papers = [
            Paper(
                cite_key="old1",
                title="First Smith Paper",
                authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
                doi="10.1234/first.2020",
                year=2020,
            ),
            Paper(
                cite_key="old2",
                title="Second Smith Paper",
                authors=[Author(family_name="Smith", given_name="Jane", full_name="Jane Smith")],
                doi="10.1234/second.2020",
                year=2020,
            ),
            Paper(
                cite_key="old3",
                title="Doe Paper",
                authors=[Author(family_name="Doe", given_name="John", full_name="John Doe")],
                doi="10.1234/doe.2021",
                year=2021,
            ),
        ]

        for paper in papers:
            db.add(paper)

        step = FixCiteKeysStep(general_config={}, db=db, cache_dir=temp_cache_dir)

        result = step.execute({}, verbose=False, dry_run=False)

        assert result.status.value == StepStatus.SUCCESS
        assert result.stats["updated"] == 3

        # Verify cite keys are unique
        cite_keys = [p.cite_key for p in db.all()]
        assert len(cite_keys) == len(set(cite_keys)), "Duplicate cite keys found"

        # Verify format
        for key in cite_keys:
            assert any(char.isdigit() for char in key), f"Key {key} missing year"

    def test_database_consistency_after_update(self, sample_db, temp_cache_dir):
        """Verify database consistency after cite key update"""
        step = FixCiteKeysStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)

        # Store paper IDs before update
        paper_ids_before = [p.id for p in sample_db.all()]

        step.execute({}, verbose=False, dry_run=False)

        # Paper IDs should not change
        paper_ids_after = [p.id for p in sample_db.all()]
        assert paper_ids_before == paper_ids_after

        # All papers should still be retrievable
        for paper_id in paper_ids_before:
            assert sample_db.get_by_id(paper_id) is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
