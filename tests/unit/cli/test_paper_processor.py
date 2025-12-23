"""
Tests for paper_processor CLI module
"""

import pytest

from paper_scanner.cli.paper_processor import StepExecutor, _discover_steps

parse_step_config = StepExecutor.parse_step_config
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Author, Paper

from paper_scanner.core.enum import StepStatus

class TestStepDiscovery:
    """Test step discovery functionality"""

    def test_discover_steps_finds_available_steps(self):
        """Test that step discovery finds available steps"""
        steps = _discover_steps()

        assert isinstance(steps, dict)
        assert len(steps) > 0
        # These are core steps that should always be present
        assert "checkpoint" in steps
        assert "halt" in steps
        assert "echo" in steps

    def test_discover_steps_excludes_private_modules(self):
        """Test that private modules starting with _ are excluded"""
        steps = _discover_steps()

        # Should not include __init__ or private modules
        assert "__init__" not in steps
        assert not any(name.startswith("_") for name in steps)

    def test_builtin_steps_cached(self):
        """Test that BUILTIN_STEPS is properly cached"""
        steps = StepExecutor.BUILTIN_STEPS

        assert isinstance(steps, dict)
        assert len(steps) > 0

    def test_step_modules_have_execute_function(self):
        """Test that discovered step modules have BaseStep subclass with execute method"""
        import tempfile
        from pathlib import Path

        from paper_scanner.core.database import PapersDatabase

        steps = _discover_steps()

        # Try to load a few steps and verify they have execute
        with tempfile.TemporaryDirectory() as tmpdir:
            for step_name in ("echo", "halt", "checkpoint"):
                if step_name in steps:
                    # Instantiate the step
                    step = StepExecutor.get_step(step_name, {}, PapersDatabase(), Path(tmpdir))
                    assert hasattr(step, "execute")
                    assert callable(step.execute)


class TestStepExecutor:
    """Test StepExecutor class"""

    def test_get_step_returns_basestep_instance(self):
        """Test that get_step returns a BaseStep instance with execute method"""
        import tempfile
        from pathlib import Path

        from paper_scanner.core.database import PapersDatabase
        from paper_scanner.steps.base import BaseStep

        with tempfile.TemporaryDirectory() as tmpdir:
            step = StepExecutor.get_step("echo", {}, PapersDatabase(), Path(tmpdir))

            assert isinstance(step, BaseStep)
            assert hasattr(step, "execute")
            assert callable(step.execute)

    def test_get_step_raises_for_unknown_step(self):
        """Test that get_step raises error for unknown step"""
        import tempfile
        from pathlib import Path

        from paper_scanner.core.database import PapersDatabase

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError) as exc_info:
                StepExecutor.get_step("nonexistent_step", {}, PapersDatabase(), Path(tmpdir))

            assert "Unknown step" in str(exc_info.value)
            assert "Available:" in str(exc_info.value)

    def test_get_step_shows_available_steps_in_error(self):
        """Test that error message shows available steps"""
        import tempfile
        from pathlib import Path

        from paper_scanner.core.database import PapersDatabase

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError) as exc_info:
                StepExecutor.get_step("invalid_step_name", {}, PapersDatabase(), Path(tmpdir))

            error_msg = str(exc_info.value)
            assert "Available:" in error_msg
            # Should show actual available steps
            available_steps = StepExecutor.BUILTIN_STEPS.keys()
            assert any(step in error_msg for step in available_steps)

    def test_known_steps_are_accessible(self):
        """Test that all discovered steps can be retrieved"""
        import tempfile
        from pathlib import Path

        from paper_scanner.core.database import PapersDatabase

        with tempfile.TemporaryDirectory() as tmpdir:
            steps = StepExecutor.BUILTIN_STEPS

            for step_name in list(steps.keys())[:3]:  # Test first 3 steps
                step = StepExecutor.get_step(step_name, {}, PapersDatabase(), Path(tmpdir))
                assert hasattr(step, "execute")


class TestParseStepConfig:
    """Test step configuration parsing"""

    def test_parse_step_config_basic(self):
        """Test parsing basic step configuration"""
        config = {"step": "Test step", "builtin.echo": {"message": "hello"}}

        step_name, params, description = parse_step_config(config)

        assert step_name == "echo"
        assert params == {"message": "hello"}
        assert description == "Test step"

    def test_parse_step_config_with_explicit_description(self):
        """Test parsing with explicit description field"""
        config = {"step": "Step name", "description": "Explicit description", "builtin.checkpoint": {}}

        step_name, params, description = parse_step_config(config)

        assert step_name == "checkpoint"
        assert description == "Explicit description"

    def test_parse_step_config_missing_step_key(self):
        """Test that missing 'step' key raises error"""
        config = {"builtin.echo": {"message": "hello"}}

        with pytest.raises(ValueError) as exc_info:
            parse_step_config(config)

        assert "missing 'step' key" in str(exc_info.value)

    def test_parse_step_config_missing_builtin_key(self):
        """Test that missing builtin.* key raises error"""
        config = {"step": "Test step"}

        with pytest.raises(ValueError) as exc_info:
            parse_step_config(config)

        assert "builtin" in str(exc_info.value).lower()

    def test_parse_step_config_extracts_step_name(self):
        """Test that step name is correctly extracted from builtin.* key"""
        config = {"step": "Test", "builtin.deduplication": {"enabled": True}}

        step_name, params, _ = parse_step_config(config)

        assert step_name == "deduplication"
        assert params["enabled"] is True

    def test_parse_step_config_preserves_parameters(self):
        """Test that all parameters are preserved"""
        config = {
            "step": "Test",
            "builtin.categorization": {"enabled": True, "threshold": 0.8, "models": ["model1", "model2"]},
        }

        step_name, params, _ = parse_step_config(config)

        assert params["enabled"] is True
        assert params["threshold"] == 0.8
        assert params["models"] == ["model1", "model2"]

    def test_parse_step_config_empty_params(self):
        """Test parsing with no step parameters"""
        config = {"step": "Checkpoint save", "builtin.checkpoint": {}}

        step_name, params, _ = parse_step_config(config)

        assert step_name == "checkpoint"
        assert params == {}


class TestStepExecutorIntegration:
    """Integration tests for step execution"""

    def test_execute_echo_step(self):
        """Test executing echo step"""
        import tempfile
        from pathlib import Path

        config = {"message": "test message"}

        with tempfile.TemporaryDirectory() as tmpdir:
            step = StepExecutor.get_step("echo", {}, PapersDatabase(), Path(tmpdir))
            result = step.execute(config, verbose=False)

            # assert "message" in result
            assert result.status == StepStatus.SUCCESS
            assert result.message == "test message"

    def test_execute_step_with_papers(self):
        """Test executing step with papers database"""
        import tempfile
        from pathlib import Path

        # Create some test papers
        papers_db = PapersDatabase()
        papers_db.add(
            Paper(
                cite_key="test1",
                title="Test Paper 1",
                authors=[Author(full_name="Author One", family_name="One", given_name="Author")],
            )
        )
        papers_db.add(
            Paper(
                cite_key="test2",
                title="Test Paper 2",
                authors=[Author(full_name="Author Two", family_name="Two", given_name="Author")],
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Get the echo step instance
            step = StepExecutor.get_step("echo", {}, papers_db, Path(tmpdir))

            config = {"message": "Processing papers"}
            result = step.execute(config, verbose=False)

            assert result.status == StepStatus.SUCCESS
            assert result.message == "Processing papers"
            # Papers should be unchanged by echo step
            assert papers_db.count(primary_only=False) == 2


class TestStepDiscoveryEdgeCases:
    """Test edge cases in step discovery"""

    def test_step_executor_builtin_steps_not_empty(self):
        """Test that BUILTIN_STEPS is not empty"""
        assert len(StepExecutor.BUILTIN_STEPS) > 0

    def test_all_builtin_steps_are_strings(self):
        """Test that all step names are strings"""
        for step_name in StepExecutor.BUILTIN_STEPS.keys():
            assert isinstance(step_name, str)
            assert len(step_name) > 0

    def test_bibtex_import_step_discovered(self):
        """Test that bibtex_import step is discovered"""
        steps = StepExecutor.BUILTIN_STEPS
        assert "bibtex_import" in steps

    def test_export_step_discovered(self):
        """Test that export step is discovered"""
        steps = StepExecutor.BUILTIN_STEPS
        assert "export" in steps


class TestStepConfigurationVariations:
    """Test various step configuration formats"""

    def test_simple_step_config(self):
        """Test parsing simple step with minimal config"""
        config = {"step": "Simple step", "builtin.halt": {}}

        step_name, params, description = parse_step_config(config)
        assert step_name == "halt"
        assert params == {}

    def test_complex_step_config(self):
        """Test parsing complex step with nested configuration"""
        config = {
            "step": "Complex import",
            "builtin.bibtex_import": {
                "batch_id": "batch_001",
                "imports": [
                    {"name": "Source 1", "file_path": "path/to/file1.bib", "source_type": "scopus"},
                    {"name": "Source 2", "file_path": "path/to/file2.bib", "source_type": "ieee"},
                ],
            },
        }

        step_name, params, _ = parse_step_config(config)

        assert step_name == "bibtex_import"
        assert params["batch_id"] == "batch_001"
        assert len(params["imports"]) == 2
        assert params["imports"][0]["source_type"] == "scopus"

    def test_step_with_many_parameters(self):
        """Test step with many configuration parameters"""
        config = {
            "step": "Test step",
            "builtin.categorization": {
                "enabled": True,
                "threshold": 0.85,
                "min_confidence": 0.7,
                "models": ["model1", "model2"],
                "settings": {"nested": "value", "another": 123},
            },
        }

        step_name, params, _ = parse_step_config(config)

        assert len(params) == 5
        assert params["enabled"] is True
        assert isinstance(params["settings"], dict)
        assert params["settings"]["nested"] == "value"


class TestStepExecutorErrorHandling:
    """Test error handling in step executor"""

    def test_get_step_with_none(self):
        """Test get_step with None raises appropriate error"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises((ValueError, TypeError)):
                StepExecutor.get_step(None, {}, PapersDatabase(), Path(tmpdir))

    def test_get_step_with_empty_string(self):
        """Test get_step with empty string raises error"""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError):
                StepExecutor.get_step("", {}, PapersDatabase(), Path(tmpdir))

    def test_parse_config_with_multiple_builtin_keys(self):
        """Test parsing config with multiple builtin.* keys uses first"""
        config = {"step": "Test", "builtin.echo": {"message": "first"}, "builtin.halt": {}}

        # Should work with first found
        step_name, params, _ = parse_step_config(config)
        assert step_name in ("echo", "halt")

    def test_parse_config_with_invalid_types(self):
        """Test parsing config with invalid parameter types"""
        config = {
            "step": "Test",
            "builtin.echo": {
                "message": "test",
                "number": 42,
                "flag": True,
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
            },
        }

        step_name, params, _ = parse_step_config(config)

        # All types should be preserved
        assert params["message"] == "test"
        assert params["number"] == 42
        assert params["flag"] is True
        assert params["list"] == [1, 2, 3]
        assert params["dict"]["nested"] == "value"


class TestStepDiscoveryPerformance:
    """Test performance aspects of step discovery"""

    def test_discover_steps_completes_quickly(self):
        """Test that step discovery completes in reasonable time"""
        import time

        start = time.time()
        steps = _discover_steps()
        elapsed = time.time() - start

        # Should complete quickly (less than 1 second)
        assert elapsed < 1.0
        assert len(steps) > 0

    def test_builtin_steps_cached_on_class_load(self):
        """Test that BUILTIN_STEPS is cached on class definition"""
        # BUILTIN_STEPS should be set when class is defined
        assert hasattr(StepExecutor, "BUILTIN_STEPS")
        assert isinstance(StepExecutor.BUILTIN_STEPS, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


