"""
Tests for the validate CLI task

Tests the validate_definition_file and execute_validate functions
"""

import pytest
from pathlib import Path
import yaml

from paper_scanner.cli.tasks.validate import validate_definition_file, execute_validate
from paper_scanner.cli.paper_processor import StepExecutor


class TestValidateFunctionality:
    """Test the validate_definition_file function"""

    def test_validate_simple_definition(self, tmp_path):
        """Test validation of a simple valid definition file"""
        # Create a simple valid definition
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_steps_key(self, tmp_path):
        """Test validation fails when 'steps' key is missing"""
        # Create definition without steps
        definition = {"project": {"name": "Test"}}

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is False
        assert any("steps" in error.lower() for error in errors)

    def test_validate_unknown_step(self, tmp_path):
        """Test validation fails for unknown step"""
        # Create definition with unknown step
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Unknown",
                    "builtin.unknown_step": {}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is False
        assert any("unknown" in error.lower() for error in errors)

    def test_validate_step_parameter_validation(self, tmp_path):
        """Test that step-specific parameter validation is called"""
        # Create definition with missing required parameters
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Load files",
                    "builtin.load_files": {}  # Missing required file_path and store_path
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_multiple_steps(self, tmp_path):
        """Test validation of multiple steps"""
        # Create definition with multiple steps
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Step 1"}
                },
                {
                    "step": "Halt",
                    "builtin.halt": {"message": "Step 2"}
                },
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Step 3"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_description(self, tmp_path):
        """Test validation with step descriptions"""
        # Create definition with descriptions
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo a message",
                    "description": "This is a test echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_file_not_found(self):
        """Test validation with non-existent file"""
        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(Path("/nonexistent/file.yml"), builtin_steps=builtin_steps)

        assert is_valid is False
        assert any("not found" in error.lower() for error in errors)

    def test_validate_empty_file(self, tmp_path):
        """Test validation with empty YAML file"""
        definition_file = tmp_path / "empty.yml"
        definition_file.write_text("")

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is False
        assert any("empty" in error.lower() for error in errors)

    def test_validate_verbose_mode(self, tmp_path, capsys):
        """Test validation in verbose mode"""
        # Create a simple valid definition
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo test",
                    "builtin.echo": {"message": "Hello World"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, verbose=True, builtin_steps=builtin_steps)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_complex_definition(self, tmp_path):
        """Test validation of a complex definition with various step types"""
        definition = {
            "project": {"name": "Complex Project"},
            "steps": [
                {
                    "step": "Load files",
                    "description": "Load PDF files",
                    "builtin.load_files": {
                        "file_path": "/path/to/pdfs",
                        "store_path": "/path/to/store"
                    }
                },
                {
                    "step": "Echo status",
                    "builtin.echo": {"message": "Files loaded"}
                }
            ]
        }

        definition_file = tmp_path / "complex.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        is_valid, errors = validate_definition_file(definition_file, builtin_steps=builtin_steps)

        assert is_valid is True
        assert len(errors) == 0


class TestExecuteValidateFunction:
    """Test the execute_validate function"""

    def test_execute_validate_success(self, tmp_path):
        """Test execute_validate returns 0 for valid definition"""
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        exit_code = execute_validate(definition_file, builtin_steps=builtin_steps)

        assert exit_code == 0

    def test_execute_validate_failure(self, tmp_path):
        """Test execute_validate returns 1 for invalid definition"""
        definition = {"project": {"name": "Test"}}  # Missing steps

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        exit_code = execute_validate(definition_file, builtin_steps=builtin_steps)

        assert exit_code == 1

    def test_execute_validate_with_verbose(self, tmp_path):
        """Test execute_validate with verbose mode"""
        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "test.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        builtin_steps = StepExecutor.BUILTIN_STEPS
        exit_code = execute_validate(definition_file, verbose=True, builtin_steps=builtin_steps)

        assert exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
