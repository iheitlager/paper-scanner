"""
Unit tests for MetadataScreeningStep

Tests metadata-based paper filtering with tri-state logic:
- Hard INCLUDE: Must have these values
- Hard EXCLUDE: Must NOT have these values  
- OMITTED: No requirement (leave aside)

Run with:
    pytest tests/unit/steps/test_metadata_screening.py -v
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import (
    PaperType,
    QualityTier,
    ScreeningDecision,
    StudyType,
    StepStatus,
)
from paper_scanner.core.models import Paper, Screening, MetadataScreening, ProcessingMetadata
from paper_scanner.steps.metadata_screening import MetadataScreeningStep


class TestMetadataScreeningValidation:
    """Tests for configuration validation"""

    def test_validate_empty_config(self):
        """Should accept empty config"""
        is_valid, errors = MetadataScreeningStep.validate({})
        assert is_valid is True
        assert errors == []

    def test_validate_enabled_flag_true(self):
        """Should accept enabled: true"""
        is_valid, errors = MetadataScreeningStep.validate({"enabled": True})
        assert is_valid is True
        assert errors == []

    def test_validate_enabled_flag_false(self):
        """Should accept enabled: false"""
        is_valid, errors = MetadataScreeningStep.validate({"enabled": False})
        assert is_valid is True
        assert errors == []

    def test_validate_enabled_flag_invalid(self):
        """Should reject non-boolean enabled"""
        is_valid, errors = MetadataScreeningStep.validate({"enabled": "true"})
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_exclude_dict(self):
        """Should accept exclude as dict"""
        config = {
            "exclude": {
                "language": ["en"]
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_exclude_not_dict(self):
        """Should reject exclude not dict"""
        config = {
            "exclude": ["language"]
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_exclude_field_list(self):
        """Should require exclude field values to be lists"""
        config = {
            "exclude": {
                "language": "en"
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is False
        assert any("must be a list" in e for e in errors)

    def test_validate_exclude_criterion_string(self):
        """Should accept string criteria"""
        config = {
            "exclude": {
                "language": ["NOT: en", "other"]
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_exclude_criterion_dict_with_not(self):
        """Should accept dict criteria with NOT key"""
        config = {
            "exclude": {
                "language": [{"NOT": "en"}]
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is True
        assert errors == []

    def test_validate_exclude_criterion_dict_without_not(self):
        """Should reject dict without NOT key"""
        config = {
            "exclude": {
                "language": [{"EXCLUDE": "en"}]
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is False

    def test_validate_exclude_criterion_invalid_type(self):
        """Should reject invalid criterion types"""
        config = {
            "exclude": {
                "language": [123]
            }
        }
        is_valid, errors = MetadataScreeningStep.validate(config)
        assert is_valid is False


class TestMetadataScreeningExecution:
    """Tests for step execution"""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Temporary cache directory"""
        return tmp_path / "cache"

    @pytest.fixture
    def papers_db(self):
        """In-memory database with test papers"""
        db = PapersDatabase()
        return db

    @pytest.fixture
    def metadata_screening_step(self, papers_db, temp_cache_dir):
        """Create MetadataScreeningStep instance"""
        temp_cache_dir.mkdir(exist_ok=True)
        return MetadataScreeningStep(
            general_config={},
            db=papers_db,
            cache_dir=temp_cache_dir
        )

    def test_execute_empty_database(self, metadata_screening_step):
        """Should handle empty database gracefully"""
        config = {}
        result = metadata_screening_step.execute(config)
        
        assert result.status == StepStatus.SUCCESS
        assert result.stats["total_papers"] == 0
        assert result.stats["screened"] == 0


    def test_execute_with_papers(self, papers_db, metadata_screening_step):
        """Should process papers in database"""
        # Add test papers
        paper1 = Paper(cite_key="paper1", title="Test Paper 1", language="en")
        paper2 = Paper(cite_key="paper2", title="Test Paper 2", language="fr")
        papers_db.add(paper1)
        papers_db.add(paper2)
        
        config = {"exclude": {"language": ["NOT: en"]}}
        result = metadata_screening_step.execute(config)
        
        assert result.status == StepStatus.SUCCESS
        assert result.stats["screened"] == 2
        assert result.stats["passed"] == 1  # Only paper1 with language "en"
        assert result.stats["failed"] == 1  # paper2 with language "fr"

    def test_execute_no_exclusions(self, papers_db, metadata_screening_step):
        """Should pass all papers when no exclusions defined"""
        paper1 = Paper(cite_key="paper1", title="Test Paper 1", language="en")
        paper2 = Paper(cite_key="paper2", title="Test Paper 2", language="fr")
        papers_db.add(paper1)
        papers_db.add(paper2)
        
        config = {}
        result = metadata_screening_step.execute(config)
        
        assert result.status == StepStatus.SUCCESS
        assert result.stats["screened"] == 2
        assert result.stats["passed"] == 2
        assert result.stats["failed"] == 0

    def test_execute_hard_exclude_logic(self, papers_db, metadata_screening_step):
        """Should implement hard exclude logic correctly"""
        paper1 = Paper(cite_key="paper1", title="Editorial", paper_type=PaperType.JOURNAL_ARTICLE)
        paper2 = Paper(cite_key="paper2", title="Conference", paper_type=PaperType.CONFERENCE_PAPER)
        papers_db.add(paper1)
        papers_db.add(paper2)
        
        # Exclude conference papers
        config = {
            "exclude": {
                "paper_types": ["conference_paper"]
            }
        }
        result = metadata_screening_step.execute(config)
        
        assert result.stats["passed"] == 1
        assert result.stats["failed"] == 1

    def test_execute_not_operator_string_format(self, papers_db, metadata_screening_step):
        """Should parse NOT: operator in string format"""
        paper1 = Paper(cite_key="paper1", title="Test", language="en")
        paper2 = Paper(cite_key="paper2", title="Test", language="fr")
        papers_db.add(paper1)
        papers_db.add(paper2)
        
        # Use string format: "NOT: en"
        config = {
            "exclude": {
                "language": ["NOT: en"]
            }
        }
        result = metadata_screening_step.execute(config)
        
        assert result.stats["passed"] == 1
        assert result.stats["failed"] == 1

    def test_execute_not_operator_dict_format(self, papers_db, metadata_screening_step):
        """Should parse NOT: operator in dict format"""
        paper1 = Paper(cite_key="paper1", title="Test", language="en")
        paper2 = Paper(cite_key="paper2", title="Test", language="fr")
        papers_db.add(paper1)
        papers_db.add(paper2)
        
        # Use dict format: {"NOT": "en"}
        config = {
            "exclude": {
                "language": [{"NOT": "en"}]
            }
        }
        result = metadata_screening_step.execute(config)
        
        assert result.stats["passed"] == 1
        assert result.stats["failed"] == 1

    def test_execute_mixed_exclude_logic(self, papers_db, metadata_screening_step):
        """Should handle mix of hard excludes and NOT operator"""
        paper1 = Paper(cite_key="paper1", title="Test1", paper_type=PaperType.JOURNAL_ARTICLE)
        paper2 = Paper(cite_key="paper2", title="Test2", paper_type=PaperType.CONFERENCE_PAPER)
        paper3 = Paper(cite_key="paper3", title="Test3", paper_type=PaperType.BOOK)
        papers_db.add(paper1)
        papers_db.add(paper2)
        papers_db.add(paper3)
        
        # Exclude conference papers AND only allow journal articles
        config = {
            "exclude": {
                "paper_types": ["conference_paper", "NOT: journal_article"]
            }
        }
        result = metadata_screening_step.execute(config)
        
        # Only paper1 (journal_article) should pass
        assert result.stats["passed"] == 1
        assert result.stats["failed"] == 2

    def test_execute_updates_database(self, papers_db, metadata_screening_step):
        """Should update papers in database with screening results"""
        paper = Paper(cite_key="paper1", title="Test", language="en")
        papers_db.add(paper)
        
        config = {"exclude": {"language": ["NOT: en"]}}
        result = metadata_screening_step.execute(config)
        
        # Retrieve paper from database
        updated_paper = papers_db.to_list()[0]
        assert updated_paper.screening.metadata_screening is not None
        assert updated_paper.screening.metadata_screening.language == "en"

    def test_execute_sets_screening_decision(self, papers_db, metadata_screening_step):
        """Should update final_decision when paper is excluded"""
        paper = Paper(cite_key="paper1", title="Test", language="fr")
        papers_db.add(paper)
        
        config = {"exclude": {"language": ["NOT: en"]}}
        result = metadata_screening_step.execute(config)
        
        updated_paper = papers_db.to_list()[0]
        assert updated_paper.screening.final_decision == ScreeningDecision.EXCLUDED
        assert updated_paper.screening.final_decision_by == "automated:metadata_screening"

    def test_execute_dry_run_mode(self, papers_db, metadata_screening_step):
        """Should not persist changes in dry_run mode"""
        paper = Paper(cite_key="paper1", title="Test", language="fr")
        papers_db.add(paper)
        original_screening = paper.screening.metadata_screening
        
        config = {"exclude": {"language": ["NOT: en"]}}
        result = metadata_screening_step.execute(config, dry_run=True)
        
        # Paper in database should not be updated
        db_paper = papers_db.to_list()[0]
        assert db_paper.screening.metadata_screening == original_screening


class TestParseNotOperator:
    """Tests for NOT operator parsing"""

    def test_parse_not_string_format(self):
        """Should extract value from NOT: string"""
        step = MetadataScreeningStep({}, None, None)
        value = step._parse_not_operator("NOT: en")
        assert value == "en"

    def test_parse_not_string_with_whitespace(self):
        """Should handle whitespace around NOT:"""
        step = MetadataScreeningStep({}, None, None)
        value = step._parse_not_operator("NOT:   en   ")
        assert value is None or value == "en"  # Depends on implementation

    def test_parse_not_dict_format(self):
        """Should extract value from dict format"""
        step = MetadataScreeningStep({}, None, None)
        value = step._parse_not_operator({"NOT": "en"})
        assert value == "en"

    def test_parse_not_plain_string(self):
        """Should return None for plain string"""
        step = MetadataScreeningStep({}, None, None)
        value = step._parse_not_operator("en")
        assert value is None

    def test_parse_not_none(self):
        """Should handle None gracefully"""
        step = MetadataScreeningStep({}, None, None)
        value = step._parse_not_operator(None)
        assert value is None


class TestExtractExcludeLogic:
    """Tests for exclude logic extraction"""

    def test_extract_simple_not_logic(self):
        """Should extract NOT: logic"""
        step = MetadataScreeningStep({}, None, None)
        exclude_config = {"language": ["NOT: en"]}
        logic = step._extract_exclude_logic(exclude_config)
        
        assert "language" in logic
        assert logic["language"]["exclude_all_except"] == "en"
        assert logic["language"]["hard_excludes"] == []

    def test_extract_hard_exclude_logic(self):
        """Should extract hard excludes"""
        step = MetadataScreeningStep({}, None, None)
        exclude_config = {"paper_types": ["conference_paper", "book"]}
        logic = step._extract_exclude_logic(exclude_config)
        
        assert logic["paper_types"]["exclude_all_except"] is None
        assert set(logic["paper_types"]["hard_excludes"]) == {"conference_paper", "book"}

    def test_extract_mixed_logic(self):
        """Should extract mix of NOT and hard excludes"""
        step = MetadataScreeningStep({}, None, None)
        exclude_config = {"paper_types": ["conference_paper", "NOT: journal_article"]}
        logic = step._extract_exclude_logic(exclude_config)
        
        assert logic["paper_types"]["exclude_all_except"] == "journal_article"
        assert "conference_paper" in logic["paper_types"]["hard_excludes"]

    def test_extract_multiple_fields(self):
        """Should extract logic for multiple fields"""
        step = MetadataScreeningStep({}, None, None)
        exclude_config = {
            "language": ["NOT: en"],
            "paper_types": ["conference_paper"]
        }
        logic = step._extract_exclude_logic(exclude_config)
        
        assert len(logic) == 2
        assert logic["language"]["exclude_all_except"] == "en"
        assert logic["paper_types"]["hard_excludes"] == ["conference_paper"]


class TestValueMatching:
    """Tests for value matching logic"""

    def test_value_matches_exact(self):
        """Should match exact values"""
        assert MetadataScreeningStep._value_matches("en", "en") is True

    def test_value_matches_case_insensitive(self):
        """Should match case-insensitively"""
        assert MetadataScreeningStep._value_matches("EN", "en") is True
        assert MetadataScreeningStep._value_matches("en", "EN") is True

    def test_value_matches_partial(self):
        """Should match partial values"""
        assert MetadataScreeningStep._value_matches("journal_article", "journal") is True

    def test_value_no_match(self):
        """Should not match when no overlap"""
        assert MetadataScreeningStep._value_matches("en", "fr") is False


class TestScreeningResults:
    """Tests for screening result generation"""

    def test_screening_metadata_created(self, tmp_path):
        """Should create MetadataScreening model"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db = PapersDatabase()
        step = MetadataScreeningStep({}, db, cache_dir)
        
        paper = Paper(cite_key="paper1", title="Test", language="en", paper_type=PaperType.JOURNAL_ARTICLE)
        screening, passed, reason = step._screen_paper(paper, {})
        
        assert isinstance(screening, MetadataScreening)
        assert screening.language == "en"
        assert screening.paper_type == PaperType.JOURNAL_ARTICLE

    def test_exclusion_reason_set(self, tmp_path):
        """Should set exclusion reason when paper is excluded"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        db = PapersDatabase()
        step = MetadataScreeningStep({}, db, cache_dir)
        
        paper = Paper(cite_key="paper1", title="Test", language="fr")
        exclude_logic = {
            "language": {
                "exclude_all_except": "en",
                "hard_excludes": []
            }
        }
        screening, passed, reason = step._screen_paper(paper, exclude_logic)
        
        assert passed is False
        assert reason is not None
        assert "language" in reason
        assert screening.exclusion_reason is not None


class TestIntegration:
    """Integration tests for full metadata screening"""

    def test_full_screening_workflow(self):
        """Should complete full screening workflow"""
        db = PapersDatabase()
        cache_dir = Path("/tmp/test_cache")
        cache_dir.mkdir(exist_ok=True)
        
        # Create diverse test papers
        papers = [
            Paper(cite_key="paper1", title="EN Journal", language="en", paper_type=PaperType.JOURNAL_ARTICLE),
            Paper(cite_key="paper2", title="EN Conference", language="en", paper_type=PaperType.CONFERENCE_PAPER),
            Paper(cite_key="paper3", title="FR Journal", language="fr", paper_type=PaperType.JOURNAL_ARTICLE),
            Paper(cite_key="paper4", title="DE Book", language="de", paper_type=PaperType.BOOK),
        ]
        
        for paper in papers:
            db.add(paper)
        
        step = MetadataScreeningStep({}, db, cache_dir)
        
        # Screen: only EN journals
        config = {
            "enabled": True,
            "exclude": {
                "language": ["NOT: en"],
                "paper_types": ["conference_paper", "book"]
            }
        }
        
        result = step.execute(config)
        
        assert result.status == StepStatus.SUCCESS
        assert result.stats["screened"] == 4
        assert result.stats["passed"] == 1  # Only EN Journal
        assert result.stats["failed"] == 3

    def test_screening_with_no_exclusions(self):
        """Should pass all papers when no exclusions defined"""
        db = PapersDatabase()
        cache_dir = Path("/tmp/test_cache")
        cache_dir.mkdir(exist_ok=True)
        
        papers = [
            Paper(cite_key="paper1", title="Paper 1"),
            Paper(cite_key="paper2", title="Paper 2"),
            Paper(cite_key="paper3", title="Paper 3"),
        ]
        
        for paper in papers:
            db.add(paper)
        
        step = MetadataScreeningStep({}, db, cache_dir)
        result = step.execute({"enabled": True})
        
        assert result.stats["passed"] == 3
        assert result.stats["failed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
