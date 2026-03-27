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

from paper_scanner.core.enum import StepStatus
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
    """Tests for run_all functionality with templates"""

    def test_run_all_executes_all_template_steps(self, executor, sample_definition_file):
        """Test that run_all executes all steps including template expansions"""
        executor.load_definition(sample_definition_file)

        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 1}

        with patch.object(executor, 'get_step', return_value=mock_step):
            result = executor.run_all()

        # Should execute all steps
        assert result.status == StepStatus.SUCCESS
        assert result.stats["steps_executed"] > 0

    def test_run_all_stops_on_template_error(self, executor, sample_definition_file):
        """Test that run_all stops when a template step returns error"""
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

        with patch.object(executor, 'get_step', side_effect=mock_get_step):
            with pytest.raises(PipelineExecutionError):
                executor.run_all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
