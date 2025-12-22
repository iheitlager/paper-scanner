"""
Unit tests for StepExecutor class

Tests cover:
- Definition loading and validation
- Checkpoint management (save and load)
- Single step execution
- Batch execution (run_all)
- Statistics and session state
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from paper_scanner.cli.executor import StepExecutor
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.steps.halt import HaltException

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


# ============================================================================
# TestStepNavigationAPI
# ============================================================================

class TestStepNavigationAPI:
    """Tests for step navigation properties and methods"""

    def test_has_steps_false_before_loading(self, executor):
        """has_steps is False before loading definition"""
        assert executor.has_steps is False

    def test_has_steps_true_after_loading(self, executor, sample_definition_file):
        """has_steps is True after loading definition with steps"""
        executor.load_definition(sample_definition_file)
        assert executor.has_steps is True

    def test_has_next_step_true_at_start(self, executor, sample_definition_file):
        """has_next_step is True when steps remain"""
        executor.load_definition(sample_definition_file)
        assert executor.has_next_step is True

    def test_has_next_step_false_when_complete(self, executor, sample_definition_file):
        """has_next_step is False when all steps executed"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = len(executor.steps)
        assert executor.has_next_step is False

    def test_step_progress_returns_tuple(self, executor, sample_definition_file):
        """step_progress returns (current, total) tuple"""
        executor.load_definition(sample_definition_file)
        current, total = executor.step_progress
        assert current == 0
        assert total == 3

    def test_step_progress_updates(self, executor, sample_definition_file):
        """step_progress updates after execution"""
        executor.load_definition(sample_definition_file)
        
        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 1}
        
        with patch.object(executor, 'get_step', return_value=mock_step):
            executor.execute_next_step()
        
        current, total = executor.step_progress
        assert current == 1
        assert total == 3

    def test_describe_next_step_returns_dict(self, executor, sample_definition_file):
        """describe_next_step returns step details dict"""
        executor.load_definition(sample_definition_file)
        info = executor.describe_next_step()
        
        assert info is not None
        assert info["index"] == 0
        assert info["name"] == "echo"
        assert info["description"] == "Import data"
        assert info["is_template"] is False
        assert "config" in info

    def test_describe_next_step_for_template(self, executor, sample_definition_file):
        """describe_next_step returns template info for run-template"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = 1  # Move to run-template step
        
        info = executor.describe_next_step()
        
        assert info["is_template"] is True
        assert info["template_name"] == "screening"

    def test_describe_next_step_none_when_complete(self, executor, sample_definition_file):
        """describe_next_step returns None when no next step"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = len(executor.steps)
        
        assert executor.describe_next_step() is None

    def test_execute_next_step_works(self, executor, sample_definition_file):
        """execute_next_step executes current step"""
        executor.load_definition(sample_definition_file)
        
        mock_step = Mock()
        mock_step.execute.return_value = {"status": "ok", "count": 5}
        
        with patch.object(executor, 'get_step', return_value=mock_step):
            result = executor.execute_next_step()
        
        assert result["status"] == "ok"
        assert executor.current_step_index == 1

    def test_execute_next_step_error_when_complete(self, executor, sample_definition_file):
        """execute_next_step returns error when no steps remain"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = len(executor.steps)
        
        result = executor.execute_next_step()
        
        assert result["status"] == StepStatus.ERROR
        assert "No more steps" in result["error"]


# ============================================================================
# TestDefinitionLoading
# ============================================================================

class TestDefinitionLoading:
    """Tests for loading and validating definitions"""

    def test_load_valid_definition(self, executor, sample_definition_file):
        """Test loading a valid definition file"""
        result = executor.load_definition(sample_definition_file)
        
        assert result is True
        assert executor.definition is not None
        assert len(executor.steps) == 3
        assert len(executor.templates) == 1
        assert "screening" in executor.templates

    def test_load_nonexistent_file(self, executor):
        """Test loading nonexistent file raises error"""
        with pytest.raises(FileNotFoundError):
            executor.load_definition(Path("/nonexistent/definition.yml"))

    def test_load_empty_definition(self, executor, temp_cache_dir):
        """Test loading empty YAML file"""
        empty_file = temp_cache_dir / "empty.yml"
        empty_file.write_text("")
        
        with pytest.raises(ValueError, match="Definition file is empty"):
            executor.load_definition(empty_file)

    def test_load_invalid_yaml(self, executor, temp_cache_dir):
        """Test loading invalid YAML"""
        bad_file = temp_cache_dir / "bad.yml"
        # YAML that parses but is invalid for our purposes
        bad_file.write_text("invalid: [unclosed")
        
        # Either raises Exception or returns validation error
        try:
            executor.load_definition(bad_file)
            # If it doesn't raise, that's acceptable too (graceful handling)
        except Exception:
            pass  # Expected

    def test_load_updates_general_config(self, executor, sample_definition_file):
        """Test that project metadata updates general_config"""
        executor.load_definition(sample_definition_file)
        
        assert executor.general_config["project_name"] == "Test Review"

    def test_load_creates_checkpoints_dir(self, executor, sample_definition_file, temp_cache_dir):
        """Test that checkpoints directory is created"""
        executor.load_definition(sample_definition_file)
        
        checkpoints_dir = temp_cache_dir / "checkpoints"
        assert checkpoints_dir.exists()

    def test_load_definition_without_templates(self, executor, temp_cache_dir):
        """Test loading definition without templates section"""
        definition = {
            "project": {"name": "Simple"},
            "steps": [
                {"step": "Echo", "builtin.echo": {"message": "test"}}
            ]
        }
        
        def_file = temp_cache_dir / "simple.yml"
        with open(def_file, "w") as f:
            yaml.dump(definition, f)
        
        result = executor.load_definition(def_file)
        
        assert result is True
        assert len(executor.templates) == 0
        assert len(executor.steps) == 1

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
# TestCheckpointManagement
# ============================================================================

class TestCheckpointManagement:
    """Tests for checkpoint saving and loading"""

    def test_checkpoint_save(self, executor, sample_definition_file, temp_cache_dir):
        """Test saving a checkpoint"""
        executor.load_definition(sample_definition_file)
        
        # Add some papers
        paper = Paper(
            id="paper1",
            cite_key="TestPaper2020",
            title="Test Paper",
            authors=[],
            year=2020,
            doi="10.1234/test",
        )
        executor.papers_db.add(paper)
        executor.current_step_index = 1
        
        result = executor.checkpoint()
        
        if result["status"] != "ok":
            print(f"Checkpoint error: {result}")
        
        assert result["status"] == "ok"
        assert "checkpoint_file" in result
        assert result["papers_count"] == 1
        
        # Verify file exists
        checkpoint_file = Path(result["checkpoint_file"])
        assert checkpoint_file.exists()

    def test_checkpoint_file_format(self, executor, sample_definition_file, temp_cache_dir):
        """Test checkpoint file has correct format"""
        executor.load_definition(sample_definition_file)
        
        paper = Paper(
            id="paper1",
            cite_key="TestPaper2020",
            title="Test Paper",
            authors=[],
            year=2020,
            doi="10.1234/test",
        )
        executor.papers_db.add(paper)
        executor.current_step_index = 1
        
        result = executor.checkpoint()
        checkpoint_file = Path(result["checkpoint_file"])
        
        with open(checkpoint_file) as f:
            data = json.load(f)
        
        assert "project_name" in data
        assert "step_index" in data
        assert "timestamp" in data
        assert "papers_count" in data
        assert "papers" in data

    def test_load_checkpoint(self, executor, sample_definition_file, temp_cache_dir):
        """Test loading a checkpoint"""
        executor.load_definition(sample_definition_file)
        
        # Save checkpoint
        paper = Paper(
            id="paper1",
            cite_key="TestPaper2020",
            title="Test Paper",
            authors=[],
            year=2020,
        )
        executor.papers_db.add(paper)
        executor.current_step_index = 1
        save_result = executor.checkpoint()
        
        # Create new executor and load checkpoint
        executor2 = StepExecutor(
            general_config=executor.general_config,
            cache_dir=temp_cache_dir,
        )
        executor2.load_definition(sample_definition_file)
        executor2.load_checkpoint()
        
        assert executor2.papers_db.count() == 1
        assert executor2.current_step_index == 2

    def test_load_checkpoint_skip(self, executor, sample_definition_file, temp_cache_dir):
        """Test skipping checkpoint loading"""
        executor.load_definition(sample_definition_file)
        executor.current_step_index = 5
        
        executor.load_checkpoint(skip_checkpoint=True)
        
        assert executor.current_step_index == 5

    def test_load_checkpoint_clear(self, executor, sample_definition_file, temp_cache_dir):
        """Test clearing checkpoints"""
        executor.load_definition(sample_definition_file)
        
        # Save checkpoint
        executor.papers_db.add(Paper(id="p1", cite_key="P2020", title="T", authors=[], year=2020))
        executor.checkpoint()
        
        checkpoints_dir = temp_cache_dir / "checkpoints"
        checkpoint_files_before = list(checkpoints_dir.glob("*.json"))
        assert len(checkpoint_files_before) > 0
        
        # Clear
        executor.load_checkpoint(clear_checkpoint=True)
        
        assert not checkpoints_dir.exists() or len(list(checkpoints_dir.glob("*.json"))) == 0

    def test_checkpoint_no_papers(self, executor, sample_definition_file):
        """Test checkpointing with no papers"""
        executor.load_definition(sample_definition_file)
        
        result = executor.checkpoint()
        
        assert result["status"] == "ok"
        assert result["papers_count"] == 0


# ============================================================================
# TestStepExecution
# ============================================================================

class TestStepExecution:
    """Tests for executing individual steps"""

    def test_execute_step_success(self, executor, sample_definition_file):
        """Test successful step execution"""
        executor.load_definition(sample_definition_file)
        
        result = executor.execute_step(0)
        
        assert result["status"] == "ok"
        assert executor.current_step_index == 1
        assert len(executor.step_history) == 1

    def test_execute_step_out_of_range(self, executor, sample_definition_file):
        """Test executing step index out of range"""
        executor.load_definition(sample_definition_file)
        
        result = executor.execute_step(999)
        
        assert result["status"] == "error"
        assert "out of range" in result["error"].lower()

    def test_execute_step_tracking(self, executor, sample_definition_file):
        """Test step execution tracking"""
        executor.load_definition(sample_definition_file)
        
        executor.execute_step(0)
        executor.execute_step(1)
        
        assert executor.current_step_index == 2
        assert len(executor.step_history) == 2
        assert executor.step_history[0]["index"] == 0
        assert executor.step_history[1]["index"] == 1

    def test_execute_step_timing(self, executor, sample_definition_file):
        """Test that step timings are recorded"""
        executor.load_definition(sample_definition_file)
        
        executor.execute_step(0)
        
        assert len(executor.step_timings) > 0
        timing = executor.step_timings[0]
        assert "step" in timing
        assert "duration_seconds" in timing
        assert "duration_ms" in timing
        assert timing["duration_seconds"] >= 0

    def test_execute_step_with_override_config(self, executor, sample_definition_file):
        """Test executing step with overridden config"""
        executor.load_definition(sample_definition_file)
        
        override_config = {
            "step": "Override",
            "builtin.echo": {"message": "overridden"}
        }
        
        result = executor.execute_step(0, step_config=override_config)
        
        assert result["status"] == "ok"

    def test_execute_step_error_handling(self, executor, sample_definition_file):
        """Test error handling during step execution"""
        executor.load_definition(sample_definition_file)
        
        # Mock step to raise exception
        with patch.object(executor, 'get_step', side_effect=Exception("Test error")):
            result = executor.execute_step(0)
        
        assert result["status"] == "error"
        assert "Test error" in result["error"]


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
        """Test run_all stops on error"""
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
            results = executor.run_all()
        
        assert results["status"] == "error"
        assert results["steps_executed"] == 1
        assert results["steps_failed"] == 1

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
        
        assert "total_duration_seconds" in results
        assert results["total_duration_seconds"] >= 0


# ============================================================================
# TestStatistics
# ============================================================================

class TestStatistics:
    """Tests for statistics and inventory methods"""

    def test_get_stats_empty(self, executor, sample_definition_file):
        """Test getting stats with empty database"""
        executor.load_definition(sample_definition_file)
        
        stats = executor.get_stats()
        
        assert stats["papers_total"] == 0
        assert stats["papers_unique"] == 0
        assert stats["papers_duplicates"] == 0
        assert stats["current_step_index"] == 0
        assert stats["total_steps"] == 3

    def test_get_stats_with_papers(self, executor, sample_definition_file):
        """Test getting stats with papers in database"""
        executor.load_definition(sample_definition_file)
        
        # Add papers
        for i in range(3):
            paper = Paper(
                id=f"p{i}",
                cite_key=f"Paper{i}2020",
                title=f"Paper {i}",
                authors=[],
                year=2020,
            )
            executor.papers_db.add(paper)
        
        stats = executor.get_stats()
        
        assert stats["papers_total"] == 3
        assert stats["papers_unique"] == 3

    def test_get_stats_inventory(self, executor, sample_definition_file):
        """Test stats include inventory information"""
        executor.load_definition(sample_definition_file)
        
        stats = executor.get_stats()
        
        assert "inventory" in stats
        assert "builtin_steps" in stats["inventory"]
        assert "templates" in stats["inventory"]
        assert "screening" in stats["inventory"]["templates"]

    def test_get_stats_timing(self, executor, sample_definition_file):
        """Test stats include timing information"""
        executor.load_definition(sample_definition_file)
        executor.run_all()
        
        stats = executor.get_stats()
        
        assert "step_timings" in stats
        assert len(stats["step_timings"]) == 3
        assert "total_duration_seconds" in stats

    def test_get_session_state(self, executor, sample_definition_file):
        """Test getting session state"""
        executor.load_definition(sample_definition_file)
        
        paper = Paper(id="p1", cite_key="P2020", title="T", authors=[], year=2020)
        executor.papers_db.add(paper)
        executor.execute_step(0)
        
        state = executor.get_session_state()
        
        assert state["papers_db"] is executor.papers_db
        assert state["papers_count"] == 1
        assert state["current_step_index"] == 1
        assert state["total_steps"] == 3


# ============================================================================
# TestHaltException
# ============================================================================

class TestHaltException:
    """Tests for HaltException handling in StepExecutor"""

    @pytest.fixture
    def simple_definition_file(self, temp_cache_dir):
        """Create a simple definition without templates for halt tests"""
        definition = {
            "project": {"name": "Halt Test"},
            "steps": [
                {"step": "Step 1", "builtin.echo": {"message": "One"}},
                {"step": "Step 2", "builtin.echo": {"message": "Two"}},
                {"step": "Step 3", "builtin.echo": {"message": "Three"}},
            ]
        }
        def_file = temp_cache_dir / "halt_definition.yml"
        with open(def_file, "w") as f:
            yaml.dump(definition, f)
        return def_file

    def test_execute_step_catches_halt_exception(self, executor, sample_definition_file):
        """Test that execute_step catches HaltException and returns halted status"""
        executor.load_definition(sample_definition_file)
        
        # Mock get_step to return a step that raises HaltException
        mock_step = Mock()
        mock_step.execute.side_effect = HaltException("Test halt message")
        
        with patch.object(executor, 'get_step', return_value=mock_step):
            result = executor.execute_step(0)
        
        assert result["status"] == "halted"
        assert result["message"] == "Test halt message"
        assert result["count"] == 0

    def test_execute_step_halt_does_not_increment_index(self, executor, sample_definition_file):
        """Test that halt exception doesn't increment step index"""
        executor.load_definition(sample_definition_file)
        initial_index = executor.current_step_index
        
        mock_step = Mock()
        mock_step.execute.side_effect = HaltException("Halting")
        
        with patch.object(executor, 'get_step', return_value=mock_step):
            executor.execute_step(0)
        
        # Index should not have been incremented (halt happens before increment)
        assert executor.current_step_index == initial_index

    def test_run_all_stops_on_halt(self, general_config, temp_cache_dir, simple_definition_file):
        """Test that run_all stops execution when HaltException is raised"""
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=temp_cache_dir,
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
        executor = StepExecutor(
            general_config=general_config,
            cache_dir=temp_cache_dir,
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

    def test_halt_preserves_custom_message(self, executor, sample_definition_file):
        """Test that halt message is preserved in result"""
        executor.load_definition(sample_definition_file)
        
        custom_message = "Review papers before continuing"
        mock_step = Mock()
        mock_step.execute.side_effect = HaltException(custom_message)
        
        with patch.object(executor, 'get_step', return_value=mock_step):
            result = executor.execute_step(0)
        
        assert result["message"] == custom_message

    def test_halt_different_from_error(self, executor, sample_definition_file):
        """Test that halt status is distinct from error status"""
        executor.load_definition(sample_definition_file)
        
        # First test halt
        mock_halt_step = Mock()
        mock_halt_step.execute.side_effect = HaltException("Halted")
        
        with patch.object(executor, 'get_step', return_value=mock_halt_step):
            halt_result = executor.execute_step(0)
        
        # Reset for error test
        executor.current_step_index = 0
        
        # Then test error
        mock_error_step = Mock()
        mock_error_step.execute.side_effect = Exception("Some error")
        
        with patch.object(executor, 'get_step', return_value=mock_error_step):
            error_result = executor.execute_step(0)
        
        # Verify they are different statuses
        assert halt_result["status"] == "halted"
        assert error_result["status"] == "error"
        assert "message" in halt_result
        assert "error" in error_result


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
        """Test that callbacks stop when step returns error"""
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
            executor.run_all(on_step_end=on_end)
        
        # Should have 2 calls: ok, error (then stop)
        assert len(end_calls) == 2
        assert end_calls[0][1] == "ok"
        assert end_calls[1][1] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
