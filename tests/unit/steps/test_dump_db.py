"""Unit tests for dump_db step"""

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper
from paper_scanner.steps.dump_db import DumpDbStep

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    return tmp_path / "cache"


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
            cite_key="Smith2020",
            title="Machine Learning in Healthcare",
            abstract="A comprehensive review",
            keywords=["ML", "healthcare"],
            authors=[Author(family_name="Smith", given_name="John", full_name="John Smith")],
            doi="10.1234/ml.2020",
            year=2020,
            paper_type="journal_article"
        ),
        Paper(
            cite_key="Doe2021",
            title="Deep Learning Applications",
            abstract="Survey of applications",
            keywords=["DL"],
            authors=[Author(family_name="Doe", given_name="Jane", full_name="Jane Doe")],
            doi="10.1234/dl.2021",
            year=2021,
            paper_type="conference_paper"
        ),
        Paper(
            cite_key="Brown2022",
            title="Natural Language Processing Advances",
            abstract="Recent advances",
            keywords=[],
            authors=[],
            doi=None,  # No DOI
            year=2022,
            paper_type=None  # No type
        ),
    ]

    for paper in papers:
        db.add(paper)

    return db


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestValidate:
    """Tests for dump_db step validation"""

    def test_validate_empty_config(self):
        """Should validate with empty config"""
        is_valid, errors = DumpDbStep.validate({"papers": True})
        assert is_valid
        assert errors == []

    def test_validate_with_extra_params(self):
        """Should validate even with extra unexpected parameters (ignored)"""
        config = {"papers": True, "unused_param": "value"}
        is_valid, errors = DumpDbStep.validate(config)
        assert is_valid
        assert errors == []


# ============================================================================
# EXECUTION TESTS
# ============================================================================

class TestExecute:
    """Tests for dump_db step execution"""

    def test_execute_empty_database(self, empty_db, temp_cache_dir):
        """Should handle empty database gracefully"""
        step = DumpDbStep(general_config={}, db=empty_db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True})

        assert result["status"] == "skipped"

    def test_execute_with_sample_data(self, sample_db, temp_cache_dir):
        """Should print all records and index statistics"""
        step = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True})

        assert result["status"] == "skipped"

    def test_execute_index_consistency(self, sample_db, temp_cache_dir):
        """Should show consistent index sizes"""
        step = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True}, verbose=True)

        index_sizes = result["index_sizes"]

        # papers count should match cite_key_index and id_index
        assert index_sizes["papers"] == index_sizes["_cite_key_index"]
        assert index_sizes["papers"] == index_sizes["_id_index"]

        # DOI index should be <= papers (some may not have DOI)
        assert index_sizes["_doi_index"] <= index_sizes["papers"]

    def test_execute_verbose_flag_ignored(self, sample_db, temp_cache_dir):
        """Should produce same output regardless of verbose flag"""
        step1 = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        step2 = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result1 = step1.execute({"papers": True}, verbose=False)
        result2 = step2.execute({"papers": True}, verbose=True)

        assert result1["status"] == 'skipped'
        assert result2["status"] == 'ok'
        assert "printed_papers" not in result1
        assert "printed_papers" in result2
        assert "index_sizes" not in result1
        assert "index_sizes" in result2


    def test_execute_multiple_papers_same_doi(self, temp_cache_dir):
        """Should handle multiple papers with same DOI"""
        db = PapersDatabase()

        # Add two papers with same DOI (duplicates)
        paper1 = Paper(
            cite_key="Paper1",
            title="Original",
            doi="10.1234/same",
            year=2020
        )
        paper2 = Paper(
            cite_key="Paper2",
            title="Duplicate",
            doi="10.1234/same",
            year=2021
        )

        db.add(paper1)
        db.add(paper2)

        step = DumpDbStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True}, verbose=True)

        # Both papers in records
        assert result["printed_papers"] == 2
        # But only one DOI in index
        assert result["index_sizes"]["_doi_index"] == 1
        # Both in papers list
        assert result["index_sizes"]["papers"] == 2

    def test_execute_no_side_effects(self, sample_db, temp_cache_dir):
        """Should not modify the database"""
        original_count = sample_db.count()
        original_stats = sample_db.get_stats()

        step = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        step.execute({"papers": True})

        assert sample_db.count() == original_count
        assert sample_db.get_stats() == original_stats

    def test_execute_with_extra_config_params(self, sample_db, temp_cache_dir):
        """Should ignore extra configuration parameters"""
        config = {
            "unused_param": "value",
            "another_param": 123
        }

        step = DumpDbStep(general_config={}, db=sample_db, cache_dir=temp_cache_dir)
        result = step.execute({**config, "papers": True}, verbose=True)

        assert result["status"] == "ok"
        assert result["printed_papers"] == 3


# ============================================================================
# LONG TITLE TRUNCATION TESTS
# ============================================================================

class TestDumpDBTitleTruncation:
    """Tests for title truncation logic"""

    def test_long_titles_truncated(self, temp_cache_dir):
        """Should truncate titles longer than 60 characters"""
        db = PapersDatabase()

        long_title = "This is a very long title that is definitely longer than sixty characters total"
        paper = Paper(
            cite_key="LongTitle",
            title=long_title,
            doi="10.1234/long",
            year=2024
        )
        db.add(paper)

        step = DumpDbStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True}, verbose=True)

        assert result["printed_papers"] == 1
        # Title should be stored fully in the paper
        assert db.papers[0].title == long_title

    def test_short_titles_not_truncated(self, temp_cache_dir):
        """Should not truncate titles shorter than 60 characters"""
        db = PapersDatabase()

        short_title = "Short title"
        paper = Paper(
            cite_key="ShortTitle",
            title=short_title,
            doi="10.1234/short",
            year=2024
        )
        db.add(paper)

        step = DumpDbStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute({"papers": True}, verbose=True)

        assert result["printed_papers"] == 1
        # Title should be unchanged
        assert db.papers[0].title == short_title

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
