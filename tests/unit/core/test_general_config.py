"""
Unit tests for GeneralConfigLoader

Tests for loading project configuration from YAML definitions.

Run with:
    pytest tests/unit/core/test_general_config.py -v
"""

import pytest
from datetime import datetime, timezone
from paper_scanner.core.general_config import GeneralConfigLoader


class TestFieldMapping:
    """Tests for field mapping constants"""

    def test_field_mapping_exists(self):
        """Should have field mapping defined"""
        assert hasattr(GeneralConfigLoader, 'FIELD_MAPPING')
        assert isinstance(GeneralConfigLoader.FIELD_MAPPING, dict)

    def test_field_mapping_hardcoded_fields(self):
        """Should have all expected fields in mapping"""
        expected_fields = {
            "project_name": "name",
            "description": "description",
            "created_at": "created_at",
            "researcher": "researcher",
            "research_question": "research_question",
            "research_dimensions": "research_dimensions",
            "email": "email",
        }
        assert GeneralConfigLoader.FIELD_MAPPING == expected_fields

    def test_field_mapping_project_name(self):
        """Should map project_name to name"""
        assert GeneralConfigLoader.FIELD_MAPPING["project_name"] == "name"

    def test_field_mapping_description(self):
        """Should map description to description"""
        assert GeneralConfigLoader.FIELD_MAPPING["description"] == "description"

    def test_field_mapping_created_at(self):
        """Should map created_at to created_at"""
        assert GeneralConfigLoader.FIELD_MAPPING["created_at"] == "created_at"

    def test_field_mapping_researcher(self):
        """Should map researcher to researcher"""
        assert GeneralConfigLoader.FIELD_MAPPING["researcher"] == "researcher"

    def test_field_mapping_research_question(self):
        """Should map research_question to research_question"""
        assert GeneralConfigLoader.FIELD_MAPPING["research_question"] == "research_question"

    def test_field_mapping_research_dimensions(self):
        """Should map research_dimensions to research_dimensions"""
        assert GeneralConfigLoader.FIELD_MAPPING["research_dimensions"] == "research_dimensions"

    def test_field_mapping_email(self):
        """Should map email to email"""
        assert GeneralConfigLoader.FIELD_MAPPING["email"] == "email"


class TestGetDefaults:
    """Tests for default values"""

    def test_get_defaults_returns_dict(self):
        """Should return a dictionary"""
        defaults = GeneralConfigLoader.get_defaults()
        assert isinstance(defaults, dict)

    def test_defaults_has_all_fields(self):
        """Should include all field mappings in defaults"""
        defaults = GeneralConfigLoader.get_defaults()
        for key in GeneralConfigLoader.FIELD_MAPPING.keys():
            assert key in defaults, f"Missing default for {key}"

    def test_defaults_project_name(self):
        """Should have default project_name"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["project_name"] == "unknown"

    def test_defaults_description_empty(self):
        """Should have empty default description"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["description"] == ""

    def test_defaults_created_at_is_timestamp(self):
        """Should have created_at as ISO format timestamp"""
        defaults = GeneralConfigLoader.get_defaults()
        created_at = defaults["created_at"]
        assert isinstance(created_at, str)
        # Should be ISO format with Z suffix
        assert created_at.endswith("Z")
        # Should be parseable as ISO format
        assert "T" in created_at

    def test_defaults_researcher_empty(self):
        """Should have empty default researcher"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["researcher"] == ""

    def test_defaults_research_question_empty(self):
        """Should have empty default research_question"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["research_question"] == ""

    def test_defaults_research_dimensions_empty_list(self):
        """Should have empty list default for research_dimensions"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["research_dimensions"] == []
        assert isinstance(defaults["research_dimensions"], list)

    def test_defaults_email_empty(self):
        """Should have empty default email"""
        defaults = GeneralConfigLoader.get_defaults()
        assert defaults["email"] == ""


class TestLoadMethod:
    """Tests for the load() method"""

    def test_load_empty_project_config(self):
        """Should not modify general_config if project_config is empty"""
        general_config = {"project_name": "original"}
        project_config = {}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "original"

    def test_load_updates_project_name(self):
        """Should update project_name from project_config"""
        general_config = {"project_name": "original"}
        project_config = {"name": "new_project"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "new_project"

    def test_load_updates_description(self):
        """Should update description from project_config"""
        general_config = {"description": ""}
        project_config = {"description": "Test description"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["description"] == "Test description"

    def test_load_updates_researcher(self):
        """Should update researcher from project_config"""
        general_config = {"researcher": ""}
        project_config = {"researcher": "Dr. Smith"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["researcher"] == "Dr. Smith"

    def test_load_updates_research_question(self):
        """Should update research_question from project_config"""
        general_config = {"research_question": ""}
        project_config = {"research_question": "What is AI?"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["research_question"] == "What is AI?"

    def test_load_updates_research_dimensions(self):
        """Should update research_dimensions from project_config"""
        general_config = {"research_dimensions": []}
        project_config = {"research_dimensions": ["novelty", "impact"]}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["research_dimensions"] == ["novelty", "impact"]

    def test_load_updates_email(self):
        """Should update email from project_config"""
        general_config = {"email": ""}
        project_config = {"email": "user@example.com"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["email"] == "user@example.com"

    def test_load_updates_created_at(self):
        """Should update created_at from project_config"""
        general_config = {"created_at": "old"}
        timestamp = "2026-01-03T10:00:00Z"
        project_config = {"created_at": timestamp}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["created_at"] == timestamp

    def test_load_multiple_fields(self):
        """Should update multiple fields from project_config"""
        general_config = {
            "project_name": "original",
            "description": "",
            "researcher": "",
            "email": ""
        }
        project_config = {
            "name": "new_project",
            "description": "New description",
            "researcher": "Dr. Jones",
            "email": "jones@example.com"
        }
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "new_project"
        assert general_config["description"] == "New description"
        assert general_config["researcher"] == "Dr. Jones"
        assert general_config["email"] == "jones@example.com"

    def test_load_ignores_unknown_fields(self):
        """Should ignore unknown fields in project_config"""
        general_config = {"project_name": "original"}
        project_config = {
            "name": "new_project",
            "unknown_field": "should be ignored"
        }
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "new_project"
        assert "unknown_field" not in general_config

    def test_load_modifies_in_place(self):
        """Should modify general_config in-place"""
        general_config = {"project_name": "original"}
        original_id = id(general_config)
        project_config = {"name": "new_project"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert id(general_config) == original_id
        assert general_config["project_name"] == "new_project"

    def test_load_handles_none_values(self):
        """Should handle None values in project_config"""
        general_config = {"project_name": "original"}
        project_config = {"name": None}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] is None

    def test_load_handles_various_types(self):
        """Should handle various data types in project_config"""
        general_config = {
            "research_dimensions": [],
            "email": ""
        }
        project_config = {
            "research_dimensions": ["dim1", "dim2", "dim3"],
            "email": "test@test.com"
        }
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["research_dimensions"] == ["dim1", "dim2", "dim3"]
        assert general_config["email"] == "test@test.com"

    def test_load_partial_fields(self):
        """Should only update fields present in project_config"""
        general_config = {
            "project_name": "original",
            "description": "original_desc",
            "researcher": "original_researcher"
        }
        project_config = {"name": "new_project"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "new_project"
        assert general_config["description"] == "original_desc"
        assert general_config["researcher"] == "original_researcher"

    def test_load_preserves_unmapped_fields(self):
        """Should preserve fields not in FIELD_MAPPING"""
        general_config = {
            "project_name": "original",
            "custom_field": "custom_value"
        }
        project_config = {"name": "new_project"}
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["project_name"] == "new_project"
        assert general_config["custom_field"] == "custom_value"

    def test_load_with_complex_research_dimensions(self):
        """Should handle complex research_dimensions data"""
        general_config = {"research_dimensions": []}
        project_config = {
            "research_dimensions": {
                "tier1": ["quality", "novelty"],
                "tier2": ["relevance", "impact"]
            }
        }
        
        GeneralConfigLoader.load(general_config, project_config)
        
        assert general_config["research_dimensions"] == {
            "tier1": ["quality", "novelty"],
            "tier2": ["relevance", "impact"]
        }
