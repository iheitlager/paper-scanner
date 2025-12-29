"""
Unit tests for StepExecutor template and batch execution functionality

Tests cover:
- Template definition and reference validation
- Batch execution via run_all
- Callback handling during execution
- Error handling in batch mode
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from paper_scanner.core.exceptions import PipelineExecutionError
from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.reporter import NoOpReporter

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_cache_dir():
    """Temporary cache directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def general_config():
    """Basic project configuration"""
    return {
        "project_name": "Test Project",
        "researcher": "Test Researcher",
    }


@pytest.fixture
def executor(general_config, temp_cache_dir):
    """Create a StepExecutor instance"""
    return StepExecutor(
        general_config=general_config,
        cache_dir=temp_cache_dir,
        step_reporter=NoOpReporter(),
        verbose=False,
        debug=False,
    )


@pytest.fixture
def sample_definition_file(temp_cache_dir):
    """Create a sample YAML definition file"""
    definition = {
        "project": {
            "name": "Test Review",
            "description": "Test definition",
        },
        "templates": [
            {
                "template": "screening",
                "steps": [
                    {
                        "step": "Screen papers",
                        "builtin.echo": {"message": "Screening..."}
                    }
                ]
            }
        ],
        "steps": [
            {
                "step": "Import data",
                "builtin.echo": {"message": "Importing..."}
            },
            {
                "step": "Apply screening",
                "builtin.run-template": {"template": "screening"}
            },
            {
                "step": "Export results",
                "builtin.echo": {"message": "Exporting..."}
            }
        ]
    }

    def_file = temp_cache_dir / "definition.yml"
    with open(def_file, "w") as f:
        yaml.dump(definition, f)

    return def_file


@pytest.fixture
def simple_definition_file(temp_cache_dir):
    """Create a simple definition without templates for tests"""
    definition = {
        "project": {"name": "Simple Test"},
        "steps": [
            {"step": "Step 1", "builtin.echo": {"message": "One"}},
            {"step": "Step 2", "builtin.echo": {"message": "Two"}},
            {"step": "Step 3", "builtin.echo": {"message": "Three"}},
        ]
    }
    def_file = temp_cache_dir / "simple_definition.yml"
    with open(def_file, "w") as f:
        yaml.dump(definition, f)
    return def_file


# ============================================================================
# TestTemplateHandling
# ============================================================================

class TestTemplateHandling:
    """Tests for template definition and execution"""

    def test_describe_next_step_for_template(self, executor, sample_definition_file):
        """describe_next_step returns template info for run-template"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = 1  # Move to run-template step

        info = executor.describe_next_step()

        assert info["is_template"] is True
        assert info["template_name"] == "screening"

    def test_validate_template_references_success(self, executor, sample_definition_file):
        """Test successful template reference validation"""
        executor.load_definition(sample_definition_file)
        # Should not raise
        executor._validate_template_references()

    def test_validate_template_references_undefined(self, executor, temp_cache_dir):
        """Test validation fails for undefined template reference"""
        definition = {
            "project": {"name": "Test"},
            "templates": [
                {
                    "template": "screening",
                    "steps": [{"step": "Echo", "builtin.echo": {}}]
                }
            ],
            "steps": [
                {
                    "step": "Apply template",
                    "builtin.run-template": {"template": "nonexistent"}
                }
            ]
        }

        def_file = temp_cache_dir / "bad_template.yml"
        with open(def_file, "w") as f:
            yaml.dump(definition, f)

        with pytest.raises(ValueError, match="Referenced template 'nonexistent' not found"):
            executor.load_definition(def_file)


# ============================================================================
# TestRunAll
# ============================================================================

class TestRunAll:
    """Tests for batch execution of all steps"""

    def test_run_all_success(self, executor, sample_definition_file):
        """Test running all steps successfully"""
        executor.load_definition(sample_definition_file)

        results = executor.run_all()

        assert results["status"] == "ok"
        assert results["steps_executed"] == 3
        assert results["steps_failed"] == 0
        assert len(results["step_results"]) == 3

    def test_run_all_with_error(self, executor, sample_definition_file):
        """Test run_all raises PipelineExecutionError on template step failure"""
        executor.load_definition(sample_definition_file)

        # Mock second step to fail
        call_count = [0]
        def mock_get_step(name):
            call_count[0] += 1
            mock_step = Mock()
            if call_count[0] == 2:
                mock_step.execute.return_value = {
                    "status": "error",
                    "error": "Step failed",
                    "count": 0,
                }
            else:
                mock_step.execute.return_value = {
                    "status": "ok",
                    "count": 0,
                }
            return mock_step

        with patch.object(executor, 'get_step', side_effect=mock_get_step):
            with pytest.raises(PipelineExecutionError, match="Template 'screening' failed"):
                executor.run_all()

    def test_run_all_resume_from_checkpoint(self, executor, sample_definition_file):
        """Test run_all resumes from checkpoint"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = 1

        results = executor.run_all()

        # Should only execute steps 1 and 2 (3 total - 1 skipped)
        assert len(results["step_results"]) == 2

    def test_run_all_dry_run(self, executor, sample_definition_file):
        """Test run_all with dry_run flag"""
        executor.load_definition(sample_definition_file)

        results = executor.run_all(dry_run=True)

        assert results["status"] == "ok"

    def test_run_all_timing(self, executor, sample_definition_file):
        """Test run_all records total duration"""
        executor.load_definition(sample_definition_file)

        results = executor.run_all()

        assert "total_duration_seconds" in results.timings
        assert results.timings["total_duration_seconds"] >= 0

    def test_run_all_stops_on_halt(self, general_config, temp_cache_dir, simple_definition_file):
        """Test that run_all stops execution when HaltException is raised"""
        from paper_scanner.steps.halt import HaltException

        executor = StepExecutor(
            general_config=general_config,
            cache_dir=temp_cache_dir,
            step_reporter=NoOpReporter(),
            verbose=False,
        )
        executor.load_definition(simple_definition_file)

        call_count = [0]
        def mock_get_step(name):
            call_count[0] += 1
            mock_step = Mock()
            if call_count[0] == 2:
                # Second step raises halt
                mock_step.execute.side_effect = HaltException("Halt at step 2")
            else:
                mock_step.execute.return_value = {"status": "ok", "count": 0}
            return mock_step

        with patch.object(executor, 'get_step', side_effect=mock_get_step):
            results = executor.run_all()

        assert results["status"] == "halted"
        assert results["steps_executed"] == 1  # Only first step completed
        assert results["steps_failed"] == 0    # Halt is not a failure

    def test_run_all_halt_returns_step_results(self, general_config, temp_cache_dir, simple_definition_file):
        """Test that run_all includes all step results including halted step"""
        from paper_scanner.steps.halt import HaltException

        executor = StepExecutor(
            general_config=general_config,
            cache_dir=temp_cache_dir,
            step_reporter=NoOpReporter(),
            verbose=False,
        )
        executor.load_definition(simple_definition_file)

        call_count = [0]
        def mock_get_step(name):
            call_count[0] += 1
            mock_step = Mock()
            if call_count[0] == 2:
                mock_step.execute.side_effect = HaltException("Stopping here")
            else:
                mock_step.execute.return_value = {"status": "ok", "count": 5}
            return mock_step

        with patch.object(executor, 'get_step', side_effect=mock_get_step):
            results = executor.run_all()

        # Should have 2 step results: 1 ok + 1 halted
        assert len(results["step_results"]) == 2
        assert results["step_results"][0]["status"] == "ok"
        assert results["step_results"][1]["status"] == "halted"


# ============================================================================
# TestRunAllCallbacks
# ============================================================================

class TestRunAllCallbacks:
    """Tests for run_all callback functionality"""

    def test_on_step_start_called_for_each_step(self, executor, sample_definition_file):
        """Test that on_step_start is called for each step"""
        executor.load_definition(sample_definition_file)

        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 1}

        start_calls = []
        def on_start(idx, config, total):
            start_calls.append((idx, config, total))

        with patch.object(executor, 'get_step', return_value=mock_step):
            executor.run_all(on_step_start=on_start)

        # Should be called for each of the 3 steps
        assert len(start_calls) == 3
        assert start_calls[0][0] == 0  # first step index
        assert start_calls[0][2] == 3  # total steps
        assert start_calls[1][0] == 1
        assert start_calls[2][0] == 2

    def test_on_step_end_called_for_each_step(self, executor, sample_definition_file):
        """Test that on_step_end is called for each step with result"""
        executor.load_definition(sample_definition_file)

        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 5}

        end_calls = []
        def on_end(idx, config, result):
            end_calls.append((idx, config, result))

        with patch.object(executor, 'get_step', return_value=mock_step):
            executor.run_all(on_step_end=on_end)

        # Should be called for each step
        assert len(end_calls) == 3
        # Each call should have the result
        for idx, config, result in end_calls:
            assert result["status"] == "ok"

    def test_callbacks_called_in_order(self, executor, sample_definition_file):
        """Test that callbacks are called in correct order: start, execute, end"""
        executor.load_definition(sample_definition_file)

        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 1}

        call_order = []
        def on_start(idx, config, total):
            call_order.append(f"start_{idx}")
        def on_end(idx, config, result):
            call_order.append(f"end_{idx}")

        with patch.object(executor, 'get_step', return_value=mock_step):
            executor.run_all(on_step_start=on_start, on_step_end=on_end)

        # Should alternate: start_0, end_0, start_1, end_1, start_2, end_2
        expected = ["start_0", "end_0", "start_1", "end_1", "start_2", "end_2"]
        assert call_order == expected

    def test_callbacks_stop_on_error(self, executor, sample_definition_file):
        """Test that exception halts callbacks on template step error"""
        executor.load_definition(sample_definition_file)

        call_count = [0]
        def mock_get_step(name):
            call_count[0] += 1
            mock_step = Mock()
            if call_count[0] == 2:
                mock_step.execute.return_value = {"status": "error", "error": "fail"}
            else:
                mock_step.execute.return_value = {"status": "ok", "count": 1}
            return mock_step

        end_calls = []
        def on_end(idx, config, result):
            end_calls.append((idx, result["status"]))

        with patch.object(executor, 'get_step', side_effect=mock_get_step):
            with pytest.raises(PipelineExecutionError):
                executor.run_all(on_step_end=on_end)

        # Only first step's callback is called; exception prevents second callback
        assert len(end_calls) == 1
        assert end_calls[0][1] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
