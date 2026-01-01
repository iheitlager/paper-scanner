"""
Unit tests for bibtex_import step (updated for flat structure - no nested imports)
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper, PaperType
from paper_scanner.steps.bibtex_import import BibtexImportStep, _fix_cite_key_collisions


class TestValidate:
    """Tests for BibtexImportStep.validate method"""

    def test_validate_valid_basic_config(self):
        """Test validation of minimal valid config"""
        config = {
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_valid_full_config(self):
        """Test validation of full config with all fields"""
        config = {
            "file_path": "test.bib",
            "source_type": "scopus",
            "expected_count": 10,
            "fix_cite_key": True
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_file_path(self):
        """Test validation fails without file_path"""
        config = {
            "source_type": "scopus"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("file_path" in err for err in errors)

    def test_validate_invalid_source_type(self):
        """Test validation fails with invalid source_type"""
        config = {
            "file_path": "test.bib",
            "source_type": "invalid"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("source_type" in err for err in errors)

    def test_validate_invalid_expected_count(self):
        """Test validation fails with invalid expected_count"""
        config = {
            "file_path": "test.bib",
            "expected_count": "not_a_number"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("expected_count" in err for err in errors)

    def test_validate_invalid_fix_cite_key(self):
        """Test validation fails with non-boolean fix_cite_key"""
        config = {
            "file_path": "test.bib",
            "fix_cite_key": "true"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("fix_cite_key" in err for err in errors)

    def test_validate_valid_limit_parameter(self):
        """Test validation with valid limit parameter"""
        config = {
            "limit": 25,
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_limit_not_positive(self):
        """Test validation fails with non-positive limit"""
        config = {
            "limit": 0,
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("limit" in err for err in errors)

    def test_validate_invalid_limit_not_integer(self):
        """Test validation fails with non-integer limit"""
        config = {
            "limit": "25",
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("limit" in err for err in errors)

    def test_validate_valid_randomize_parameter(self):
        """Test validation with valid randomize parameter"""
        config = {
            "randomize": True,
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_randomize_not_boolean(self):
        """Test validation fails with non-boolean randomize"""
        config = {
            "randomize": "true",
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("randomize" in err for err in errors)

    def test_validate_valid_random_seed_parameter(self):
        """Test validation with valid random_seed parameter"""
        config = {
            "random_seed": 42,
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_random_seed_not_integer(self):
        """Test validation fails with non-integer random_seed"""
        config = {
            "random_seed": "42",
            "file_path": "test.bib"
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is False
        assert any("random_seed" in err for err in errors)

    def test_validate_full_complex_config(self):
        """Test validation with full complex config including all parameters"""
        config = {
            "limit": 25,
            "randomize": True,
            "random_seed": 42,
            "file_path": "data/bib/scopus.bib",
            "source_type": "scopus",
            "fix_cite_key": False,
            "expected_count": 19
        }
        is_valid, errors = BibtexImportStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0


class TestFixCiteKeyCollisions:
    """Tests for _fix_cite_key_collisions function"""

    def test_no_collisions(self):
        """Test when there are no collisions"""
        papers_db = PapersDatabase()
        papers = [
            Paper(
                id="p1", cite_key="paper1",
                title="Paper 1",
                authors=[Author(family_name="A", given_name="A", full_name="A A")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2", cite_key="paper2",
                title="Paper 2",
                authors=[Author(family_name="B", given_name="B", full_name="B B")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # Cite keys should remain unchanged
        assert papers[0].cite_key == "paper1"
        assert papers[1].cite_key == "paper2"
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

    def test_multiple_collisions(self):
        """Test multiple collision handling"""
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

        # Should get paper_03 and paper_04
        assert papers[0].cite_key == "paper_03"
        assert papers[1].cite_key == "paper_04"
        assert fixed_count == 2

    def test_same_file_collisions(self):
        """Test handling of duplicate cite_keys within the same file"""
        papers_db = PapersDatabase()

        papers = [
            Paper(
                id="p1", cite_key="samefile",
                title="Paper 1",
                authors=[Author(family_name="A", given_name="A", full_name="A A")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2", cite_key="samefile",
                title="Paper 2",
                authors=[Author(family_name="B", given_name="B", full_name="B B")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p3", cite_key="samefile",
                title="Paper 3",
                authors=[Author(family_name="C", given_name="C", full_name="C C")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # First should keep original, others get suffixes
        assert papers[0].cite_key == "samefile"
        assert papers[1].cite_key == "samefile_01"
        assert papers[2].cite_key == "samefile_02"
        assert fixed_count == 2

    def test_suffix_format(self):
        """Test that suffix is correctly formatted with leading zeros"""
        papers_db = PapersDatabase()

        # Add existing paper "paper" and papers with suffixes up to _08
        existing_paper = Paper(
            id="p_existing_0", cite_key="paper",
            title="Original Paper",
            authors=[Author(family_name="E", given_name="E", full_name="E E")],
            paper_type=PaperType.JOURNAL_ARTICLE
        )
        papers_db.add(existing_paper)

        for i in range(1, 9):
            existing_paper = Paper(
                id=f"p_existing_{i}", cite_key=f"paper_{i:02d}",
                title=f"Existing Paper {i}",
                authors=[Author(family_name="E", given_name="E", full_name="E E")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
            papers_db.add(existing_paper)

        papers = [
            Paper(
                id="p1", cite_key="paper",
                title="New Paper",
                authors=[Author(family_name="N", given_name="N", full_name="N N")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        fixed_count = _fix_cite_key_collisions(papers, papers_db)

        # Should be paper_09 (9 with leading zero, since _01 through _08 exist)
        assert papers[0].cite_key == "paper_09"
        assert fixed_count == 1


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestExecute:
    """Tests for BibtexImportStep.execute method"""

    def test_execute_file_not_found(self, temp_cache_dir):
        """Test execute with non-existent file raises ConfigurationError"""
        from paper_scanner.core.exceptions import ConfigurationError

        config = {
            "file_path": "/nonexistent/file.bib"
        }
        papers_db = PapersDatabase()
        step = BibtexImportStep(general_config={}, db=papers_db, cache_dir=temp_cache_dir)

        # Missing file is a configuration error - should raise
        with pytest.raises(ConfigurationError):
            step.execute(config, verbose=False, dry_run=False)

    @patch("paper_scanner.steps.bibtex_import.bibtex_file_to_papers")
    def test_execute_dry_run(self, mock_bibtex_parser, temp_cache_dir):
        """Test execute in dry run mode"""
        mock_bibtex_parser.return_value = [
            Paper(
                id="p1",
                cite_key="test",
                title="Test Paper",
                authors=[Author(family_name="T", given_name="T", full_name="T T")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]

        papers_db = PapersDatabase()
        step = BibtexImportStep(general_config={}, db=papers_db, cache_dir=temp_cache_dir)

        with tempfile.NamedTemporaryFile(suffix=".bib") as tmp:
            config = {
                "file_path": tmp.name,
                "expected_count": 1
            }
            result = step.execute(config, verbose=False, dry_run=True)

        assert result.stats["count"] == 1  # Still counted papers even in dry run
        assert len(papers_db.to_list()) == 0  # But not added to database

    @patch("paper_scanner.steps.bibtex_import.bibtex_file_to_papers")
    def test_execute_with_fix_cite_key(self, mock_bibtex_parser, temp_cache_dir):
        """Test execute with fix_cite_key enabled"""
        papers_list = [
            Paper(
                id="p1",
                cite_key="dup",
                title="Paper 1",
                authors=[Author(family_name="A", given_name="A", full_name="A A")],
                paper_type=PaperType.JOURNAL_ARTICLE
            ),
            Paper(
                id="p2",
                cite_key="dup",
                title="Paper 2",
                authors=[Author(family_name="B", given_name="B", full_name="B B")],
                paper_type=PaperType.JOURNAL_ARTICLE
            )
        ]
        mock_bibtex_parser.return_value = papers_list

        papers_db = PapersDatabase()
        step = BibtexImportStep(general_config={}, db=papers_db, cache_dir=temp_cache_dir)

        with tempfile.NamedTemporaryFile(suffix=".bib") as tmp:
            config = {
                "file_path": tmp.name,
                "fix_cite_key": True,
                "expected_count": 2
            }
            result = step.execute(config, verbose=False, dry_run=False)

        assert result.stats["count"] == 2

        # Verify papers in database have unique cite_keys
        db_papers = papers_db.to_list()
        cite_keys = [p.cite_key for p in db_papers]
        assert len(cite_keys) == len(set(cite_keys))  # All unique

    def test_execute_randomize_with_seed(self, temp_cache_dir):
        """Test execute with randomization and seed"""
        sample_bib = Path(__file__).parent.parent.parent / "data" / "scopus_sample_20.bib"
        if not sample_bib.exists():
            pytest.skip(f"Sample BibTeX file not found: {sample_bib}")

        config = {
            "randomize": True,
            "random_seed": 42,
            "limit": 2,
            "file_path": str(sample_bib),
            "source_type": "scopus"
        }

        # Execute first time with seed
        papers_db1 = PapersDatabase()
        step1 = BibtexImportStep(general_config={}, db=papers_db1, cache_dir=temp_cache_dir)
        result1 = step1.execute(config, verbose=False)
        papers1 = papers_db1.to_list()
        titles1 = sorted([p.title for p in papers1])

        # Execute again with same seed (new database instance)
        papers_db2 = PapersDatabase()
        step2 = BibtexImportStep(general_config={}, db=papers_db2, cache_dir=temp_cache_dir)
        result2 = step2.execute(config, verbose=False)
        papers2 = papers_db2.to_list()
        titles2 = sorted([p.title for p in papers2])

        # With same seed, should get same papers (though order may differ due to sorting)
        assert titles1 == titles2, "Same seed should produce same set of papers"
        assert len(papers1) == 2, "Should have limited to 2 papers"
        assert result1.stats["count"] == 2
        assert result2.stats["count"] == 2

    def test_execute_randomize_different_seeds(self, temp_cache_dir):
        """Test that different seeds produce different orders"""
        sample_bib = Path(__file__).parent.parent.parent / "data" / "scopus_sample_20.bib"
        if not sample_bib.exists():
            pytest.skip(f"Sample BibTeX file not found: {sample_bib}")

        # Execute with seed 42
        config1 = {
            "randomize": True,
            "random_seed": 42,
            "limit": 5,
            "file_path": str(sample_bib),
            "source_type": "scopus"
        }
        papers_db1 = PapersDatabase()
        step1 = BibtexImportStep(general_config={}, db=papers_db1, cache_dir=temp_cache_dir)
        result1 = step1.execute(config1, verbose=False)
        papers1 = papers_db1.to_list()
        titles1 = [p.title for p in papers1]

        # Execute with different seed
        config2 = {
            "randomize": True,
            "random_seed": 123,
            "limit": 5,
            "file_path": str(sample_bib),
            "source_type": "scopus"
        }
        papers_db2 = PapersDatabase()
        step2 = BibtexImportStep(general_config={}, db=papers_db2, cache_dir=temp_cache_dir)
        result2 = step2.execute(config2, verbose=False)
        papers2 = papers_db2.to_list()
        titles2 = [p.title for p in papers2]

        # Both should import 5 papers
        assert len(titles1) == 5 and len(titles2) == 5
        assert result1.stats["count"] == 5
        assert result2.stats["count"] == 5
        # Orders should be different due to different seeds
        assert titles1 != titles2 or len(set(titles1)) < 5

    @patch("paper_scanner.steps.bibtex_import.bibtex_file_to_papers")
    def test_execute_bibtex_parsing_failure_raises(self, mock_bibtex_parser, temp_cache_dir):
        """Test that BibTeX parsing failure raises fatal error"""
        mock_bibtex_parser.side_effect = ValueError("Invalid BibTeX format")

        papers_db = PapersDatabase()
        step = BibtexImportStep(general_config={}, db=papers_db, cache_dir=temp_cache_dir)

        with tempfile.NamedTemporaryFile(suffix=".bib") as tmp:
            config = {
                "file_path": tmp.name
            }
            # Should raise because parsing failed
            with pytest.raises(ValueError):
                step.execute(config, verbose=False, dry_run=False)
