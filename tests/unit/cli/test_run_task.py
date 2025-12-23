"""
Tests for the run CLI task

Tests the execution of definition files and step processing
"""

import json
from unittest.mock import patch

import pytest
import yaml

from paper_scanner.cli.tasks.run import StepExecutor, _find_latest_checkpoint, _load_checkpoint, execute_run


class TestStepExecutorParsing:
    """Test step configuration parsing"""

    def test_parse_simple_step(self):
        """Test parsing a simple step configuration"""
        step_config = {
            "step": "Echo",
            "builtin.echo": {"message": "Hello"}
        }
        builtin_steps = {"echo": "EchoStep"}

        name, params, desc = StepExecutor.parse_step_config(step_config, builtin_steps)

        assert name == "echo"
        assert params == {"message": "Hello"}
        assert desc == "Echo"

    def test_parse_step_with_description(self):
        """Test parsing step with explicit description"""
        step_config = {
            "step": "Echo",
            "description": "Echo a message",
            "builtin.echo": {"message": "Hello"}
        }
        builtin_steps = {"echo": "EchoStep"}

        name, params, desc = StepExecutor.parse_step_config(step_config, builtin_steps)

        assert name == "echo"
        assert params == {"message": "Hello"}
        assert desc == "Echo a message"

    def test_parse_step_with_space_name(self):
        """Test parsing step with space in name (used as description)"""
        step_config = {
            "step": "Echo status",
            "builtin.echo": {"message": "Hello"}
        }
        builtin_steps = {"echo": "EchoStep"}

        name, params, desc = StepExecutor.parse_step_config(step_config, builtin_steps)

        assert name == "echo"
        assert desc == "Echo status"

    def test_parse_missing_step_key(self):
        """Test parsing fails when 'step' key is missing"""
        step_config = {"builtin.echo": {"message": "Hello"}}
        builtin_steps = {"echo": "EchoStep"}

        with pytest.raises(ValueError, match="Step configuration missing 'step' key"):
            StepExecutor.parse_step_config(step_config, builtin_steps)

    def test_parse_missing_builtin_key(self):
        """Test parsing fails when builtin key is missing"""
        step_config = {"step": "Echo"}
        builtin_steps = {"echo": "EchoStep"}

        with pytest.raises(ValueError, match="Step configuration missing 'builtin.<step>' key"):
            StepExecutor.parse_step_config(step_config, builtin_steps)

    def test_parse_step_with_root_level_params(self):
        """Test parsing step with parameters at root level"""
        step_config = {
            "step": "Echo",
            "builtin.echo": {},
            "message": "Hello"
        }
        builtin_steps = {"echo": "EchoStep"}

        name, params, desc = StepExecutor.parse_step_config(step_config, builtin_steps)

        assert name == "echo"
        assert params == {"message": "Hello"}


class TestCheckpointFunctions:
    """Test checkpoint-related functions"""

    def test_find_latest_checkpoint_none_exist(self, tmp_path):
        """Test finding checkpoint when none exist"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        steps = [
            {"step": "Load"},
            {"step": "Process"}
        ]

        resume_idx, checkpoint_file = _find_latest_checkpoint(cache_dir, "test", steps)

        assert resume_idx is None
        assert checkpoint_file is None

    def test_find_latest_checkpoint_single(self, tmp_path):
        """Test finding single checkpoint"""
        import hashlib

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()

        project_name = "test"
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        checkpoint_file = checkpoints_dir / f"checkpoint_{project_hash}_step_000.json"
        checkpoint_file.write_text('{"papers": []}')

        steps = [{"step": "Load"}]

        resume_idx, found_file = _find_latest_checkpoint(cache_dir, project_name, steps)

        assert resume_idx == 1
        assert found_file == checkpoint_file

    def test_find_latest_checkpoint_multiple(self, tmp_path):
        """Test finding latest of multiple checkpoints"""
        import hashlib

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()

        project_name = "test"
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]

        # Create multiple checkpoints
        for i in range(3):
            checkpoint_file = checkpoints_dir / f"checkpoint_{project_hash}_step_{i:03d}.json"
            checkpoint_file.write_text('{"papers": []}')

        steps = [{"step": "Load"}, {"step": "Process"}, {"step": "Export"}]

        resume_idx, found_file = _find_latest_checkpoint(cache_dir, project_name, steps)

        assert resume_idx == 3  # Resume from step 3 (after step 2)
        assert "step_002" in str(found_file)

    def test_load_checkpoint(self, tmp_path):
        """Test loading checkpoint file"""
        with patch('paper_scanner.steps.checkpoint.load_checkpoint') as mock_load:
            checkpoint_papers = [{"id": 1, "title": "Test"}]
            mock_load.return_value = (checkpoint_papers, {})

            checkpoint_file = tmp_path / "checkpoint.json"
            checkpoint_file.write_text('{"papers": []}')

            papers = _load_checkpoint(checkpoint_file)

            assert papers == checkpoint_papers
            mock_load.assert_called_once_with(checkpoint_file)


class MockStep:
    """Simple mock step that returns ok status"""
    def execute(self, config, verbose=False, dry_run=False, debug=False):
        return {"status": "ok"}


class ErrorStep:
    """Mock step that returns error status"""
    def execute(self, config, verbose=False, dry_run=False, debug=False):
        return {"status": "error", "error": "Test error"}


class TestExecuteRun:
    """Test the main execute_run function"""

    def test_execute_run_simple_definition(self, tmp_path):
        """Test executing a simple definition file"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test Project"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert results["dry_run"] is False
        assert len(results["steps_executed"]) == 1
        assert results["steps_executed"][0]["step"] == "echo"

    def test_execute_run_missing_file(self, tmp_path):
        """Test executing with missing definition file"""
        definition_file = tmp_path / "nonexistent.yml"

        with pytest.raises(FileNotFoundError, match="Definition file not found"):
            execute_run(definition_file)

    def test_execute_run_empty_file(self, tmp_path):
        """Test executing with empty definition file"""
        definition_file = tmp_path / "empty.yml"
        definition_file.write_text("")

        with pytest.raises(ValueError, match="Definition file is empty"):
            execute_run(definition_file)

    def test_execute_run_with_dry_run(self, tmp_path):
        """Test executing with dry_run flag"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            dry_run=True,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert results["dry_run"] is True

    def test_execute_run_with_verbose(self, tmp_path, capsys):
        """Test executing with verbose output"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test Project", "description": "A test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            verbose=True,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert results["dry_run"] is False

    def test_execute_run_with_timings(self, tmp_path):
        """Test executing with timing information"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            show_timings=True,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert results["step_timings"] is not None
        assert len(results["step_timings"]) == 1
        assert "duration_seconds" in results["step_timings"][0]

    def test_execute_run_with_output_file(self, tmp_path):
        """Test executing with output file"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        output_file = tmp_path / "output.json"

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            output_file=output_file,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert output_file.exists()
        with open(output_file) as f:
            saved_results = json.load(f)
        assert saved_results["dry_run"] is False

    def test_execute_run_cache_dir_from_env(self, tmp_path, monkeypatch):
        """Test cache dir is loaded from environment variable"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        monkeypatch.setenv("CACHE_DIR", str(cache_dir))

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert str(cache_dir) in results["cache_dir"]

    def test_execute_run_cache_dir_from_definition(self, tmp_path):
        """Test cache dir is loaded from definition file"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {
                "name": "Test",
                "cache_dir": str(cache_dir)
            },
            "steps": [
                {
                    "step": "Echo",
                    "builtin.echo": {"message": "Hello"}
                }
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert str(cache_dir) in results["cache_dir"]

    def test_execute_run_multiple_steps(self, tmp_path):
        """Test executing multiple steps"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {"step": "Echo 1", "builtin.echo": {"message": "Step 1"}},
                {"step": "Echo 2", "builtin.echo": {"message": "Step 2"}},
                {"step": "Echo 3", "builtin.echo": {"message": "Step 3"}},
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        assert len(results["steps_executed"]) == 3

    def test_execute_run_step_error(self, tmp_path):
        """Test handling step execution error"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {"step": "Echo", "builtin.echo": {"message": "Hello"}},
                {"step": "Bad", "builtin.bad": {}},
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            if step_name == "bad":
                return ErrorStep()
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep", "bad": "BadStep"}
        )

        assert len(results["steps_executed"]) == 2
        assert len(results["errors"]) >= 1

    def test_execute_run_skip_checkpoint_flag(self, tmp_path):
        """Test skip_checkpoint flag disables checkpoint loading"""
        import hashlib

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()

        project_name = "Test"
        project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
        checkpoint_file = checkpoints_dir / f"checkpoint_{project_hash}_step_000.json"
        checkpoint_file.write_text('{"papers": []}')

        definition = {
            "project": {"name": project_name},
            "steps": [
                {"step": "Echo", "builtin.echo": {"message": "Hello"}}
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        with patch('paper_scanner.cli.tasks.run._load_checkpoint') as mock_load:
            results = execute_run(
                definition_file,
                cache_dir=cache_dir,
                skip_checkpoint=True,
                get_step_func=mock_get_step,
                builtin_steps={"echo": "EchoStep"}
            )

            # Checkpoint should not be loaded
            mock_load.assert_not_called()
            assert results["checkpoint"] is None

    def test_execute_run_clear_checkpoint(self, tmp_path):
        """Test clear_checkpoint flag removes existing checkpoints"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        checkpoints_dir = cache_dir / "checkpoints"
        checkpoints_dir.mkdir()
        (checkpoints_dir / "checkpoint_old.json").write_text('{}')

        assert checkpoints_dir.exists()

        definition = {
            "project": {"name": "Test"},
            "steps": [
                {"step": "Echo", "builtin.echo": {"message": "Hello"}}
            ]
        }

        definition_file = tmp_path / "definition.yml"
        with open(definition_file, "w") as f:
            yaml.dump(definition, f)

        def mock_get_step(step_name):
            return MockStep()

        results = execute_run(
            definition_file,
            cache_dir=cache_dir,
            clear_checkpoint=True,
            get_step_func=mock_get_step,
            builtin_steps={"echo": "EchoStep"}
        )

        # Checkpoints should be cleared
        assert not checkpoints_dir.exists() or len(list(checkpoints_dir.glob("*"))) == 0
