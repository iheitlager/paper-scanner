"""
Metadata Screening - YAML Configuration Parsing Test
Tests parsing and validation of metadata-screening step configuration

Run with:
    pytest test_01_metadata_screening_parse.py -v
    or
    python test_01_metadata_screening_parse.py
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml


class MetadataScreeningConfigParser:
    """Parser for metadata-screening step configuration"""

    @staticmethod
    def load_yaml_config(yaml_file: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        with open(yaml_file, 'r') as f:
            return yaml.safe_load(f)

    @staticmethod
    def parse_screening_step(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract metadata-screening step from config

        Args:
            config: Full configuration dict (with 'steps' key at top level)

        Returns:
            The metadata-screening step config or None if not found
        """
        steps = config.get("steps", [])
        for step in steps:
            if "builtin.metadata_screening" in step:
                return step["builtin.metadata_screening"]
        return None

    @staticmethod
    def validate_exclude_criteria(exclude_config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate exclude criteria structure

        Args:
            exclude_config: The exclude section of config

        Returns:
            (is_valid, errors)
        """
        errors = []

        # Each field should have a list of criteria
        for field, criteria in exclude_config.items():
            if not isinstance(criteria, list):
                errors.append(f"Field '{field}' must have a list of criteria, got {type(criteria).__name__}")
            else:
                for criterion in criteria:
                    # Accept both string and dict (YAML NOT: syntax)
                    if isinstance(criterion, str):
                        # Plain string criterion
                        pass
                    elif isinstance(criterion, dict):
                        # YAML dict syntax like "NOT: value"
                        if "NOT" in criterion:
                            value = criterion["NOT"]
                            if not value:
                                errors.append(f"Field '{field}': NOT: operator missing value")
                        else:
                            errors.append(f"Field '{field}': dict criteria must have 'NOT' key, got {list(criterion.keys())}")
                    else:
                        errors.append(f"Field '{field}': criteria must be strings or dicts, got {type(criterion).__name__}")

        return len(errors) == 0, errors

    @staticmethod
    def parse_not_operator(criterion: Any) -> Optional[str]:
        """
        Parse NOT operator from criterion

        Accepts both formats:
        - Dict syntax: {"NOT": "en"}
        - String syntax: "NOT: en"

        Returns the value after NOT or None if not present
        """
        if isinstance(criterion, dict):
            return criterion.get("NOT")
        elif isinstance(criterion, str) and criterion.startswith("NOT:"):
            return criterion.replace("NOT:", "").strip()
        return None

    @staticmethod
    def extract_exclude_logic(exclude_config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Extract exclude logic from config into structured format

        Returns:
        {
            "field_name": {
                "exclude_all_except": "value" or None,
                "hard_excludes": ["value1", "value2"]
            }
        }
        """
        logic = {}

        for field, criteria in exclude_config.items():
            exclude_all_except = None
            hard_excludes = []

            for criterion in criteria:
                not_value = MetadataScreeningConfigParser.parse_not_operator(criterion)
                if not_value:
                    exclude_all_except = not_value
                else:
                    # Hard exclude: add the value
                    if isinstance(criterion, dict):
                        # Skip dict entries that aren't NOT
                        pass
                    elif isinstance(criterion, str):
                        hard_excludes.append(criterion)

            logic[field] = {
                "exclude_all_except": exclude_all_except,
                "hard_excludes": hard_excludes
            }

        return logic


class TestYAMLLoading:
    """Tests for loading YAML configuration"""

    @pytest.fixture
    def config_file(self) -> Path:
        """Get path to test YAML file"""
        return Path(__file__).parent / "test_01_metadata_screening_parse.yml"

    def test_yaml_file_exists(self, config_file):
        """Should find YAML configuration file"""
        assert config_file.exists(), f"Config file not found: {config_file}"

    def test_load_yaml_config(self, config_file):
        """Should load YAML file successfully"""
        parser = MetadataScreeningConfigParser()
        config = parser.load_yaml_config(str(config_file))

        assert config is not None
        assert "pipeline" in config
        assert "steps" in config

    def test_yaml_has_steps(self, config_file):
        """Should have multiple steps"""
        parser = MetadataScreeningConfigParser()
        config = parser.load_yaml_config(str(config_file))

        steps = config["steps"]
        assert len(steps) >= 2, "Should have at least 2 steps"


class TestScreeningStepParsing:
    """Tests for parsing metadata-screening step configuration"""

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load test configuration"""
        config_file = Path(__file__).parent / "test_01_metadata_screening_parse.yml"
        parser = MetadataScreeningConfigParser()
        full_config = parser.load_yaml_config(str(config_file))
        return full_config

    def test_extract_screening_step(self, config):
        """Should extract metadata-screening step from config"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)

        assert screening_config is not None, "metadata-screening step not found"
        assert "exclude" in screening_config

    def test_screening_step_has_exclude(self, config):
        """Should have exclude section"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)

        exclude = screening_config.get("exclude", {})
        assert "language" in exclude
        assert "paper_types" in exclude

    def test_screening_step_no_include(self, config):
        """Should NOT have include section"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)

        assert "include" not in screening_config, "include section should be removed"

    def test_screening_step_no_value_mapping(self, config):
        """Should NOT have value_mapping section"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)

        assert "value_mapping" not in screening_config, "value_mapping should be removed"


class TestExcludeCriteriaValidation:
    """Tests for validating exclude criteria"""

    def test_validate_exclude_language(self):
        """Should validate language exclude criteria"""
        exclude_config = {
            "language": ["NOT: en"]
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is True
        assert errors == []

    def test_validate_exclude_paper_types(self):
        """Should validate paper_types exclude criteria"""
        exclude_config = {
            "paper_types": ["NOT: journal_article"]
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is True
        assert errors == []

    def test_validate_exclude_study_types(self):
        """Should validate study_types exclude criteria"""
        exclude_config = {
            "study_types": ["editorial", "conceptual", "theoretical"]
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is True
        assert errors == []

    def test_validate_mixed_exclude(self):
        """Should validate mixed NOT and hard excludes"""
        exclude_config = {
            "study_types": ["editorial", "NOT: empirical"]
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is True
        assert errors == []

    def test_invalid_exclude_not_list(self):
        """Should fail when criteria is not a list"""
        exclude_config = {
            "language": "NOT: en"  # Should be list
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is False
        assert len(errors) > 0

    def test_invalid_exclude_empty_not(self):
        """Should fail when NOT: has no value (dict syntax)"""
        exclude_config = {
            "language": [{"NOT": ""}]  # Missing value
        }
        parser = MetadataScreeningConfigParser()
        is_valid, errors = parser.validate_exclude_criteria(exclude_config)

        assert is_valid is False
        assert len(errors) > 0


class TestParseNotOperator:
    """Tests for parsing NOT: operator"""

    def test_parse_not_operator_present(self):
        """Should extract value from NOT: operator"""
        parser = MetadataScreeningConfigParser()
        value = parser.parse_not_operator("NOT: en")

        assert value == "en"

    def test_parse_not_operator_with_whitespace(self):
        """Should handle whitespace around NOT: operator"""
        parser = MetadataScreeningConfigParser()
        value = parser.parse_not_operator("NOT:   en   ")

        assert value == "en"

    def test_parse_not_operator_absent(self):
        """Should return None when NOT: not present"""
        parser = MetadataScreeningConfigParser()
        value = parser.parse_not_operator("editorial")

        assert value is None

    def test_parse_not_operator_complex_value(self):
        """Should handle complex values after NOT:"""
        parser = MetadataScreeningConfigParser()
        value = parser.parse_not_operator("NOT: journal_article")

        assert value == "journal_article"


class TestExtractExcludeLogic:
    """Tests for extracting and structuring exclude logic"""

    def test_extract_simple_not_logic(self):
        """Should extract NOT: logic into structured format"""
        exclude_config = {
            "language": ["NOT: en"]
        }
        parser = MetadataScreeningConfigParser()
        logic = parser.extract_exclude_logic(exclude_config)

        assert "language" in logic
        assert logic["language"]["exclude_all_except"] == "en"
        assert logic["language"]["hard_excludes"] == []

    def test_extract_hard_exclude_logic(self):
        """Should extract hard excludes into structured format"""
        exclude_config = {
            "study_types": ["editorial", "conceptual", "theoretical"]
        }
        parser = MetadataScreeningConfigParser()
        logic = parser.extract_exclude_logic(exclude_config)

        assert "study_types" in logic
        assert logic["study_types"]["exclude_all_except"] is None
        assert set(logic["study_types"]["hard_excludes"]) == {"editorial", "conceptual", "theoretical"}

    def test_extract_mixed_logic(self):
        """Should extract mixed NOT and hard excludes"""
        exclude_config = {
            "study_types": ["editorial", "NOT: empirical"]
        }
        parser = MetadataScreeningConfigParser()
        logic = parser.extract_exclude_logic(exclude_config)

        assert logic["study_types"]["exclude_all_except"] == "empirical"
        assert "editorial" in logic["study_types"]["hard_excludes"]

    def test_extract_multiple_fields(self):
        """Should extract logic for multiple fields"""
        exclude_config = {
            "language": ["NOT: en"],
            "paper_types": ["NOT: journal_article"],
            "study_types": ["editorial", "conceptual"]
        }
        parser = MetadataScreeningConfigParser()
        logic = parser.extract_exclude_logic(exclude_config)

        assert len(logic) == 3
        assert logic["language"]["exclude_all_except"] == "en"
        assert logic["paper_types"]["exclude_all_except"] == "journal_article"
        assert logic["study_types"]["exclude_all_except"] is None


class TestIntegrationYAMLParsing:
    """Integration tests for full YAML parsing"""

    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load test configuration"""
        config_file = Path(__file__).parent / "test_01_metadata_screening_parse.yml"
        parser = MetadataScreeningConfigParser()
        full_config = parser.load_yaml_config(str(config_file))
        return full_config

    def test_full_pipeline_parsing(self, config):
        """Should parse entire config"""
        MetadataScreeningConfigParser()

        assert "pipeline" in config
        assert "version" in config["pipeline"]
        assert "steps" in config

    def test_full_screening_step_parsing(self, config):
        """Should parse complete screening step"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)

        assert screening_config is not None
        is_valid, errors = parser.validate_exclude_criteria(screening_config["exclude"])
        assert is_valid is True, f"Validation errors: {errors}"

    def test_full_exclude_logic_extraction(self, config):
        """Should extract complete exclude logic"""
        parser = MetadataScreeningConfigParser()
        screening_config = parser.parse_screening_step(config)
        logic = parser.extract_exclude_logic(screening_config["exclude"])

        assert "language" in logic
        assert "paper_types" in logic

        # Verify NOT: logic
        assert logic["language"]["exclude_all_except"] == "en"
        assert logic["paper_types"]["exclude_all_except"] == "journal_article"


def run_manual_tests():
    """Run tests manually for debugging"""
    print("=" * 80)
    print("Running YAML Configuration Parsing Tests")
    print("=" * 80)

    config_file = Path(__file__).parent / "test_01_metadata_screening_parse.yml"
    parser = MetadataScreeningConfigParser()

    # Test 1: Load YAML
    print("\n[Test 1] Loading YAML configuration")
    config = parser.load_yaml_config(str(config_file))
    pipeline = config["pipeline"]
    print(f"  Name: {pipeline['name']}")
    print(f"  Version: {pipeline['version']}")
    print(f"  Steps: {len(config['steps'])}")
    print("  ✓ PASSED")

    # Test 2: Extract screening step
    print("\n[Test 2] Extracting metadata-screening step")
    screening_config = parser.parse_screening_step(config)
    print("  Found metadata-screening step")
    print(f"  Has exclude: {'exclude' in screening_config}")
    print(f"  Has include: {'include' in screening_config}")
    print(f"  Has value_mapping: {'value_mapping' in screening_config}")
    assert "include" not in screening_config
    assert "value_mapping" not in screening_config
    print("  ✓ PASSED")

    # Test 3: Validate exclude criteria
    print("\n[Test 3] Validating exclude criteria")
    is_valid, errors = parser.validate_exclude_criteria(screening_config["exclude"])
    print(f"  Valid: {is_valid}")
    if errors:
        for error in errors:
            print(f"    - {error}")
    assert is_valid is True
    print("  ✓ PASSED")

    # Test 4: Extract exclude logic
    print("\n[Test 4] Extracting exclude logic")
    logic = parser.extract_exclude_logic(screening_config["exclude"])

    for field, field_logic in logic.items():
        print(f"  {field}:")
        if field_logic["exclude_all_except"]:
            print(f"    - Exclude all except: {field_logic['exclude_all_except']}")
        if field_logic["hard_excludes"]:
            print(f"    - Hard excludes: {field_logic['hard_excludes']}")
    print("  ✓ PASSED")

    # Test 5: Parse NOT operators
    print("\n[Test 5] Parsing NOT operators")
    for field, criteria_list in screening_config["exclude"].items():
        for criterion in criteria_list:
            not_value = parser.parse_not_operator(criterion)
            if not_value:
                print(f"  {field}: NOT {not_value}")
    print("  ✓ PASSED")

    print("\n" + "=" * 80)
    print("All manual tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    import sys
    if "--manual" in sys.argv:
        run_manual_tests()
    else:
        pytest.main([__file__, "-v"])
