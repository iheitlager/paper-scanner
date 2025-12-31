"""
Unit tests for ris_import step
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper, PaperType
from paper_scanner.core.enum import DiscoveryMethod, StepStatus
from paper_scanner.core.exceptions import ConfigurationError
from paper_scanner.steps.ris_import import RisImportStep, _fix_cite_key_collisions


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestValidate:
    """Tests for RisImportStep.validate method"""

    def test_validate_valid_basic_config(self):
        """Test validation of minimal valid config"""
        config = {
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_full_config(self):
        """Test validation of full config with all fields"""
        config = {
            "file_path": "test.ris",
            "source_database": "proquest",
            "expected_count": 10,
            "fix_cite_key": True,
            "limit": 20,
            "randomize": True,
            "random_seed": 42
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_file_path(self):
        """Test validation fails without file_path"""
        config = {
            "source_database": "proquest"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("file_path" in err for err in errors)

    def test_validate_invalid_source_database(self):
        """Test validation fails with invalid source_database"""
        config = {
            "file_path": "test.ris",
            "source_database": "invalid_source"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("source_database" in err for err in errors)

    def test_validate_valid_source_databases(self):
        """Test validation passes for all valid source databases"""
        valid_sources = ["proquest", "scopus", "web_of_science", "mendeley", "zotero", "other"]
        for source in valid_sources:
            config = {
                "file_path": "test.ris",
                "source_database": source
            }
            is_valid, errors = RisImportStep.validate(config)
            assert is_valid is True, f"Failed for source_database={source}"

    def test_validate_invalid_expected_count(self):
        """Test validation fails with invalid expected_count"""
        config = {
            "file_path": "test.ris",
            "expected_count": "not_a_number"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("expected_count" in err for err in errors)

    def test_validate_negative_expected_count(self):
        """Test validation fails with negative expected_count"""
        config = {
            "file_path": "test.ris",
            "expected_count": -1
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("expected_count" in err for err in errors)

    def test_validate_invalid_fix_cite_key(self):
        """Test validation fails with non-boolean fix_cite_key"""
        config = {
            "file_path": "test.ris",
            "fix_cite_key": "true"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("fix_cite_key" in err for err in errors)

    def test_validate_valid_limit_parameter(self):
        """Test validation with valid limit parameter"""
        config = {
            "limit": 25,
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_limit_not_positive(self):
        """Test validation fails with non-positive limit"""
        config = {
            "limit": 0,
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("limit" in err for err in errors)

    def test_validate_invalid_limit_not_integer(self):
        """Test validation fails with non-integer limit"""
        config = {
            "limit": "25",
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("limit" in err for err in errors)

    def test_validate_valid_randomize_parameter(self):
        """Test validation with valid randomize parameter"""
        config = {
            "randomize": True,
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_randomize_not_boolean(self):
        """Test validation fails with non-boolean randomize"""
        config = {
            "randomize": "true",
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("randomize" in err for err in errors)

    def test_validate_valid_random_seed_parameter(self):
        """Test validation with valid random_seed parameter"""
        config = {
            "random_seed": 42,
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_random_seed_not_integer(self):
        """Test validation fails with non-integer random_seed"""
        config = {
            "random_seed": "42",
            "file_path": "test.ris"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("random_seed" in err for err in errors)

    def test_validate_unknown_key(self):
        """Test validation fails with unknown configuration key"""
        config = {
            "file_path": "test.ris",
            "unknown_key": "value"
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is False
        assert any("unknown_key" in err for err in errors)

    def test_validate_full_complex_config(self):
        """Test validation with full complex config including all parameters"""
        config = {
            "limit": 25,
            "randomize": True,
            "random_seed": 42,
            "file_path": "data/ris/proquest.ris",
            "source_database": "proquest",
            "fix_cite_key": False,
            "expected_count": 19,
        }
        is_valid, errors = RisImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0


class TestFixCiteKeyCollisions:
    """Tests for _fix_cite_key_collisions function"""

    def test_no_collisions(self):
        """Test when there are no collisions"""
        papers_db = PapersDatabase()
        papers = [
            Paper(
                id="p1", cite_key="ris_an_paper1",
                title="Paper 1",
                authors=[Author(family_name="A", given_name="A", full_name="A A")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2", cite_key="ris_an_paper2",
                title="Paper 2",
                authors=[Author(family_name="B", given_name="B", full_name="B B")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # Cite keys should remain unchanged
        assert papers[0].cite_key == "ris_an_paper1"
        assert papers[1].cite_key == "ris_an_paper2"
        assert fixed_count == 0

    def test_collision_with_existing_database(self):
        """Test collision with existing database entry"""
        papers_db = PapersDatabase()
        existing_paper = Paper(
            id="p_existing", cite_key="duplicate",
            title="Existing Paper",
            authors=[Author(family_name="E", given_name="E", full_name="E E")],
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        papers_db.add(existing_paper)

        papers = [
            Paper(
                id="p1", cite_key="duplicate",
                title="New Paper",
                authors=[Author(family_name="N", given_name="N", full_name="N N")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # New paper should have _01 suffix
        assert papers[0].cite_key == "duplicate_01"
        assert fixed_count == 1

    def test_multiple_collisions_in_batch(self):
        """Test multiple collision handling within imported papers"""
        papers_db = PapersDatabase()

        # Add existing papers with suffixes
        for i in range(3):
            key = "paper" if i == 0 else f"paper_{i:02d}"
            existing_paper = Paper(
                id=f"p_existing_{i}", cite_key=key,
                title=f"Existing Paper {i}",
                authors=[Author(family_name="E", given_name="E", full_name="E E")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
            papers_db.add(existing_paper)

        papers = [
            Paper(
                id="p1", cite_key="paper",
                title="New Paper 1",
                authors=[Author(family_name="N", given_name="N", full_name="N N")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2", cite_key="paper",
                title="New Paper 2",
                authors=[Author(family_name="N", given_name="N", full_name="N N")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # Both should have different suffixes
        assert papers[0].cite_key == "paper_03"
        assert papers[1].cite_key == "paper_04"
        assert fixed_count == 2

    def test_collision_within_batch(self):
        """Test collisions within the same batch of papers"""
        papers_db = PapersDatabase()

        papers = [
            Paper(
                id="p1", cite_key="duplicate",
                title="Paper 1",
                authors=[Author(family_name="A", given_name="A", full_name="A A")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2", cite_key="duplicate",
                title="Paper 2",
                authors=[Author(family_name="B", given_name="B", full_name="B B")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p3", cite_key="duplicate",
                title="Paper 3",
                authors=[Author(family_name="C", given_name="C", full_name="C C")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # All should have different suffixes
        assert papers[0].cite_key == "duplicate"
        assert papers[1].cite_key == "duplicate_01"
        assert papers[2].cite_key == "duplicate_02"
        assert fixed_count == 2


class TestExecute:
    """Tests for RisImportStep.execute method"""

    def test_execute_file_not_found(self, temp_cache_dir):
        """Test execute fails gracefully when file not found"""
        step = RisImportStep(general_config={}, db=PapersDatabase(), cache_dir=temp_cache_dir)
        config = {
            "file_path": "/nonexistent/file.ris"
        }

        with pytest.raises(ConfigurationError) as exc_info:
            step.execute(config)

        assert "not found" in str(exc_info.value).lower()

    def test_execute_dry_run(self, temp_cache_dir):
        """Test execute with dry_run=True doesn't add to database"""
        # Create a temporary RIS file
        ris_content = """TY  - JOUR
T1  - Test Paper
AU  - Smith, John
JF  - Test Journal
PY  - 2023
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "other"
            }

            result = step.execute(config, dry_run=True)

            assert result.status == StepStatus.SUCCESS
            # Database should remain empty in dry_run mode
            assert len(db.to_list()) == 0
        finally:
            Path(temp_file).unlink()

    def test_execute_with_limit(self, temp_cache_dir):
        """Test execute respects limit parameter"""
        # Create a RIS file with multiple papers
        ris_content = """TY  - JOUR
T1  - Paper 1
AU  - Smith, John
JF  - Journal
PY  - 2023
AN  - 12345
ER  -

TY  - JOUR
T1  - Paper 2
AU  - Jones, Jane
JF  - Journal
PY  - 2023
AN  - 12346
ER  -

TY  - JOUR
T1  - Paper 3
AU  - Brown, Bob
JF  - Journal
PY  - 2023
AN  - 12347
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "other",
                "limit": 2
            }

            result = step.execute(config)

            assert result.status == StepStatus.SUCCESS
            assert result.stats["count"] == 2
            assert len(db.to_list()) == 2
        finally:
            Path(temp_file).unlink()

    def test_execute_with_randomize(self, temp_cache_dir):
        """Test execute with randomize parameter"""
        # Create a RIS file with multiple papers
        ris_content = """TY  - JOUR
T1  - Paper 1
AU  - Smith, John
JF  - Journal
PY  - 2023
AN  - 12345
ER  -

TY  - JOUR
T1  - Paper 2
AU  - Jones, Jane
JF  - Journal
PY  - 2023
AN  - 12346
ER  -

TY  - JOUR
T1  - Paper 3
AU  - Brown, Bob
JF  - Journal
PY  - 2023
AN  - 12347
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "other",
                "randomize": True,
                "random_seed": 42
            }

            result = step.execute(config)

            assert result.status == StepStatus.SUCCESS
            assert result.stats["count"] == 3
            assert len(db.to_list()) == 3
        finally:
            Path(temp_file).unlink()

    def test_execute_with_fix_cite_key(self, temp_cache_dir):
        """Test execute with fix_cite_key parameter"""
        # Create a RIS file
        ris_content = """TY  - JOUR
T1  - Paper 1
AU  - Smith, John
JF  - Journal
PY  - 2023
AN  - 12345
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            # Add an existing paper with the same cite_key
            existing_paper = Paper(
                id="existing", cite_key="ris_an_12345",
                title="Existing",
                authors=[Author(family_name="E", given_name="E", full_name="E E")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
            db.add(existing_paper)

            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "other",
                "fix_cite_key": True
            }

            result = step.execute(config)

            assert result.status == StepStatus.SUCCESS
            # Should report collisions fixed
            assert "collisions fixed" in result.message.lower()
        finally:
            Path(temp_file).unlink()

    def test_execute_with_expected_count_match(self, temp_cache_dir):
        """Test execute when expected_count matches actual"""
        # Create a RIS file with exactly 2 papers
        ris_content = """TY  - JOUR
T1  - Paper 1
AU  - Smith, John
JF  - Journal
PY  - 2023
AN  - 12345
ER  -

TY  - JOUR
T1  - Paper 2
AU  - Jones, Jane
JF  - Journal
PY  - 2023
AN  - 12346
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "other",
                "expected_count": 2
            }

            result = step.execute(config)

            assert result.status == StepStatus.SUCCESS
            assert result.stats["count"] == 2
        finally:
            Path(temp_file).unlink()

    def test_execute_basic_success(self, temp_cache_dir):
        """Test basic successful execution"""
        ris_content = """TY  - JOUR
T1  - Test Paper
AU  - Smith, John
JF  - Test Journal
PY  - 2023
AN  - 12345
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            temp_file = f.name

        try:
            db = PapersDatabase()
            step = RisImportStep(general_config={}, db=db, cache_dir=temp_cache_dir)
            config = {
                "file_path": temp_file,
                "source_database": "proquest"
            }

            result = step.execute(config)

            assert result.status == StepStatus.SUCCESS
            assert result.stats["count"] == 1
            assert len(db.to_list()) == 1

            # Verify paper was imported correctly
            papers = db.to_list()
            paper = papers[0]
            assert paper.title == "Test Paper"
            assert paper.discovery.source_database == "proquest"
            assert paper.discovery.method == DiscoveryMethod.KEYWORD_SEARCH
        finally:
            Path(temp_file).unlink()
