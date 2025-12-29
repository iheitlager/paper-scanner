"""
Unit tests for StepExecutor checkpoint functionality

Tests cover:
- Checkpoint saving and loading
- Checkpoint file format validation
- Resume from checkpoint
- Clear checkpoint operations
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from paper_scanner.core.executor import StepExecutor
from paper_scanner.core.models import Paper
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
            {"template": "screening", "steps": [{"step": "Screen papers", "builtin.echo": {"message": "Screening..."}}]}
        ],
        "steps": [
            {"step": "Import data", "builtin.echo": {"message": "Importing..."}},
            {"step": "Apply screening", "builtin.run-template": {"template": "screening"}},
            {"step": "Export results", "builtin.echo": {"message": "Exporting..."}},
        ],
    }

    def_file = temp_cache_dir / "definition.yml"
    with open(def_file, "w") as f:
        yaml.dump(definition, f)

    return def_file


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
            step_reporter=NoOpReporter(),
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


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
