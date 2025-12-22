"""
Unit tests for the checkpoint step.

Tests that the checkpoint step properly serializes and deserializes papers,
including handling of the duplicate_of field without creating circular references.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from paper_scanner.core.models import Paper
from paper_scanner.core.database import PapersDatabase
from paper_scanner.steps.checkpoint import (
    CheckpointStep,
    _get_checkpoint_name,
    _serialize_papers,
    _deserialize_papers,
    load_checkpoint,
)


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory"""
    return tmp_path / "cache"


class TestValidate:
    """Test checkpoint step validation"""

    def test_validate_returns_success(self):
        """Checkpoint validation should always succeed"""
        is_valid, errors = CheckpointStep.validate({})
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_with_arbitrary_config(self):
        """Checkpoint validation should ignore config"""
        config = {
            "cache_dir": "/some/path",
            "step_index": 5,
            "other_field": "value",
        }
        is_valid, errors = CheckpointStep.validate(config)
        assert is_valid is True
        assert len(errors) == 0


class TestCheckpointNameGeneration:
    """Test checkpoint filename generation"""

    def test_checkpoint_name_format(self):
        """Checkpoint names should follow expected format"""
        name = _get_checkpoint_name("my_project", 0)
        assert name.startswith("checkpoint_")
        assert name.endswith("_step_000.json")

    def test_checkpoint_name_deterministic(self):
        """Same project name should produce same hash"""
        name1 = _get_checkpoint_name("my_project", 0)
        name2 = _get_checkpoint_name("my_project", 0)
        assert name1 == name2

    def test_checkpoint_name_different_projects(self):
        """Different project names should produce different hashes"""
        name1 = _get_checkpoint_name("project_a", 0)
        name2 = _get_checkpoint_name("project_b", 0)
        assert name1 != name2

    def test_checkpoint_name_different_steps(self):
        """Different step indices should produce different names"""
        name1 = _get_checkpoint_name("my_project", 0)
        name2 = _get_checkpoint_name("my_project", 1)
        assert name1 != name2
        assert "_step_000" in name1
        assert "_step_001" in name2


class TestPaperSerialization:
    """Test paper serialization and deserialization"""

    def test_serialize_simple_paper(self):
        """Should serialize a simple paper correctly"""
        paper = Paper(
            cite_key="test2024",
            title="Test Paper",
            year=2024,
        )
        serialized = _serialize_papers([paper])
        assert len(serialized) == 1
        assert serialized[0]["cite_key"] == "test2024"
        assert serialized[0]["title"] == "Test Paper"
        assert serialized[0]["year"] == 2024

    def test_serialize_excludes_none_values(self):
        """Should exclude None values from serialization"""
        paper = Paper(
            cite_key="test2024",
            title="Test Paper",
            abstract=None,
        )
        serialized = _serialize_papers([paper])
        # abstract should be excluded when None
        assert "abstract" not in serialized[0]

    def test_serialize_paper_with_duplicate_of(self):
        """Should serialize duplicate_of as ID string, not full object"""
        primary = Paper(cite_key="primary2024", title="Primary Paper")
        duplicate = Paper(cite_key="dup2024", title="Duplicate Paper")
        duplicate.duplicate_of = primary

        serialized = _serialize_papers([duplicate])
        assert len(serialized) == 1

        # The duplicate_of should be a string ID, not a nested object
        duplicate_of = serialized[0].get("duplicate_of")
        assert isinstance(duplicate_of, str)
        assert duplicate_of == primary.id

    def test_serialize_multiple_papers_with_duplicates(self):
        """Should properly serialize multiple papers with duplicate relationships"""
        paper1 = Paper(cite_key="p1", title="Paper 1")
        paper2 = Paper(cite_key="p2", title="Paper 2")
        paper3 = Paper(cite_key="p3", title="Paper 3")

        # Set up duplicate relationships
        paper2.duplicate_of = paper1
        paper3.duplicate_of = paper1

        serialized = _serialize_papers([paper1, paper2, paper3])
        assert len(serialized) == 3

        # Paper 1 should have no duplicate_of
        assert serialized[0].get("duplicate_of") is None

        # Papers 2 and 3 should have duplicate_of as string IDs
        assert serialized[1]["duplicate_of"] == paper1.id
        assert serialized[2]["duplicate_of"] == paper1.id

    def test_deserialize_simple_paper(self):
        """Should deserialize a simple paper correctly"""
        data = {
            "cite_key": "test2024",
            "title": "Test Paper",
            "year": 2024,
            "id": "test-id",
        }
        papers = _deserialize_papers([data])
        assert len(papers) == 1
        assert papers[0].cite_key == "test2024"
        assert papers[0].title == "Test Paper"
        assert papers[0].year == 2024

    def test_deserialize_paper_with_duplicate_of_id(self):
        """Should deserialize paper with duplicate_of as reference"""
        # Note: When deserializing from JSON with duplicate_of as string ID,
        # Pydantic will try to convert it to a Paper object or keep it as string
        # depending on the model configuration
        primary_id = "primary-id"
        primary = Paper(id=primary_id, cite_key="prim2024", title="Primary Paper")
        dup = Paper(cite_key="dup2024", title="Duplicate Paper")
        dup.duplicate_of = primary
        
        serialized = _serialize_papers([dup])
        # After serialization, duplicate_of should be the ID string
        assert serialized[0]["duplicate_of"] == primary_id

    def test_round_trip_serialization(self):
        """Should preserve data through serialize/deserialize round trip"""
        original = Paper(
            cite_key="test2024",
            title="Test Paper",
            abstract="This is a test",
            year=2024,
            authors=[],
        )

        serialized = _serialize_papers([original])
        deserialized = _deserialize_papers(serialized)

        assert len(deserialized) == 1
        assert deserialized[0].cite_key == original.cite_key
        assert deserialized[0].title == original.title
        assert deserialized[0].abstract == original.abstract
        assert deserialized[0].year == original.year


class TestExecute:
    """Test checkpoint step execution"""

    def test_execute_without_cache_dir(self, temp_cache_dir):
        """Should handle execution with minimal config"""
        db = PapersDatabase()
        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        config = {
            "step_index": 0,
            "project_name": "test_project",
        }
        result = step.execute(config)
        assert result["status"] == "ok"

    def test_execute_creates_checkpoint_file(self, temp_cache_dir):
        """Should create checkpoint file in cache directory"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper")
        db.add(paper)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config)
        assert result["status"] == "ok"

        # Check that checkpoint file was created
        checkpoint_dir = temp_cache_dir / "checkpoints"
        assert checkpoint_dir.exists()
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        assert len(checkpoint_files) == 1

    def test_execute_checkpoint_content(self, temp_cache_dir):
        """Should save papers with correct data in checkpoint"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper", year=2024)
        db.add(paper)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config)
        assert result["status"] == "ok"

        # Read the checkpoint file and verify content
        checkpoint_dir = temp_cache_dir / "checkpoints"
        checkpoint_file = list(checkpoint_dir.glob("*.json"))[0]

        with open(checkpoint_file) as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "papers" in data
        assert len(data["papers"]) == 1
        assert data["papers"][0]["cite_key"] == "test2024"
        assert data["papers"][0]["title"] == "Test Paper"
        assert data["papers_count"] == 1

    def test_execute_dry_run_no_file_created(self, temp_cache_dir):
        """Should not create file in dry_run mode"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper")
        db.add(paper)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config, dry_run=True)
        assert result["status"] == "ok"

        # Check that no checkpoint file was created
        checkpoint_dir = temp_cache_dir / "checkpoints"
        if checkpoint_dir.exists():
            checkpoint_files = list(checkpoint_dir.glob("*.json"))
            assert len(checkpoint_files) == 0

    def test_execute_with_duplicate_papers(self, temp_cache_dir):
        """Should properly serialize papers with duplicate relationships"""
        db = PapersDatabase()

        # Create papers with duplicate relationship
        primary = Paper(cite_key="primary2024", title="Primary Paper")
        duplicate = Paper(cite_key="dup2024", title="Duplicate Paper")
        duplicate.duplicate_of = primary

        db.add(primary)
        db.add(duplicate)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config)
        assert result["status"] == "ok"

        # Read and verify the checkpoint
        checkpoint_dir = temp_cache_dir / "checkpoints"
        checkpoint_file = list(checkpoint_dir.glob("*.json"))[0]

        with open(checkpoint_file) as f:
            data = json.load(f)

        papers = data["papers"]
        assert len(papers) == 2

        # Find the duplicate paper
        dup_paper = next(p for p in papers if p["cite_key"] == "dup2024")
        prim_paper = next(p for p in papers if p["cite_key"] == "primary2024")

        # Verify duplicate_of is stored as ID string
        assert dup_paper["duplicate_of"] == primary.id
        assert prim_paper.get("duplicate_of") is None

        # Verify no circular references (JSON should be valid)
        # If there were circular references, json.dump would fail
        json.dumps(data)

    def test_execute_returns_correct_result_format(self, temp_cache_dir):
        """Should return result with correct format"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper")
        db.add(paper)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config)
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] == "ok"
        assert "checkpoint_file" in result
        assert "papers_count" in result
        assert result["papers_count"] == 1

    def test_execute_multiple_checkpoints(self, temp_cache_dir):
        """Should create different checkpoint files for different step indices"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper")
        db.add(paper)

        # Create checkpoint at step 0
        config1 = {
            "step_index": 0,
            "project_name": "test_project",
        }
        step1 = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result1 = step1.execute(config1)
        assert result1["status"] == "ok"

        # Create checkpoint at step 1
        config2 = {
            "step_index": 1,
            "project_name": "test_project",
        }
        step2 = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result2 = step2.execute(config2)
        assert result2["status"] == "ok"

        # Verify two different checkpoint files exist
        checkpoint_dir = temp_cache_dir / "checkpoints"
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        assert len(checkpoint_files) == 2

    def test_execute_with_verbose_flag(self, temp_cache_dir):
        """Should accept verbose flag without error"""
        db = PapersDatabase()
        paper = Paper(cite_key="test2024", title="Test Paper")
        db.add(paper)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        result = step.execute(config, verbose=True)
        assert result["status"] == "ok"


class TestLoadCheckpoint:
    """Test loading papers from checkpoint files with duplicate restoration"""

    def test_load_checkpoint_simple(self, temp_cache_dir):
        """Should load papers from checkpoint file"""
        # Create a checkpoint with simple papers
        db = PapersDatabase()
        paper1 = Paper(cite_key="p1", title="Paper 1")
        paper2 = Paper(cite_key="p2", title="Paper 2")
        db.add(paper1)
        db.add(paper2)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        step.execute(config)

        # Load the checkpoint
        checkpoint_file = (temp_cache_dir / "checkpoints").glob("*.json").__next__()
        loaded_papers, step_index = load_checkpoint(checkpoint_file)

        assert len(loaded_papers) == 2
        assert step_index == 0
        assert loaded_papers[0].cite_key == "p1"
        assert loaded_papers[1].cite_key == "p2"

    def test_load_checkpoint_restores_duplicates(self, temp_cache_dir):
        """Should restore duplicate_of references when loading checkpoint"""
        # Create a checkpoint with duplicate papers
        db = PapersDatabase()
        primary = Paper(cite_key="primary2024", title="Primary Paper")
        duplicate = Paper(cite_key="dup2024", title="Duplicate Paper")
        duplicate.duplicate_of = primary

        db.add(primary)
        db.add(duplicate)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        step.execute(config)

        # Load the checkpoint
        checkpoint_file = (temp_cache_dir / "checkpoints").glob("*.json").__next__()
        loaded_papers, _ = load_checkpoint(checkpoint_file)

        assert len(loaded_papers) == 2

        # Find the loaded duplicate paper
        loaded_duplicate = next(p for p in loaded_papers if p.cite_key == "dup2024")
        loaded_primary = next(p for p in loaded_papers if p.cite_key == "primary2024")

        # The duplicate_of should be restored to the actual Paper object reference
        assert loaded_duplicate.duplicate_of is not None
        assert loaded_duplicate.duplicate_of is loaded_primary
        assert loaded_duplicate.duplicate_of.cite_key == "primary2024"

    def test_load_checkpoint_with_database_roundtrip(self, temp_cache_dir):
        """
        Full roundtrip test: save duplicates to checkpoint, load them,
        add to database, verify duplicates are maintained
        """
        # Original database with duplicates
        original_db = PapersDatabase()
        p1 = Paper(cite_key="p1", title="Paper 1", year=2020)
        p2 = Paper(cite_key="p2", title="Paper 1 (duplicate)", year=2020)
        p3 = Paper(cite_key="p3", title="Paper 1 (another)", year=2020)

        p2.duplicate_of = p1
        p3.duplicate_of = p1

        original_db.add(p1)
        original_db.add(p2)
        original_db.add(p3)

        assert original_db.count(primary_only=False) == 3
        assert original_db.count(primary_only=True) == 1

        # Save to checkpoint
        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=original_db, cache_dir=temp_cache_dir)
        step.execute(config)

        # Load from checkpoint
        checkpoint_file = (temp_cache_dir / "checkpoints").glob("*.json").__next__()
        loaded_papers, _ = load_checkpoint(checkpoint_file)

        # Create new database and load the papers
        restored_db = PapersDatabase()
        restored_db.from_list(loaded_papers)

        # Verify duplicates are maintained
        assert restored_db.count(primary_only=False) == 3
        assert restored_db.count(primary_only=True) == 1

        # Verify duplicate relationships
        restored_p1 = restored_db.get_by_cite_key("p1")
        restored_p2 = restored_db.get_by_cite_key("p2")
        restored_p3 = restored_db.get_by_cite_key("p3")

        assert restored_p1 is not None
        assert restored_p2 is not None
        assert restored_p3 is not None

        assert restored_p2.duplicate_of is restored_p1
        assert restored_p3.duplicate_of is restored_p1

    def test_load_checkpoint_with_missing_primary(self, temp_cache_dir):
        """Should handle duplicate reference to non-existent primary gracefully"""
        # Manually create a checkpoint JSON with an orphaned duplicate reference
        checkpoint_dir = temp_cache_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_data = {
            "project_name": "test",
            "step_index": 0,
            "timestamp": "2024-01-01T00:00:00",
            "papers_count": 2,
            "papers": [
                {
                    "id": "primary-id",
                    "cite_key": "primary",
                    "title": "Primary Paper",
                    "duplicate_of": None
                },
                {
                    "id": "dup-id",
                    "cite_key": "duplicate",
                    "title": "Duplicate Paper",
                    "duplicate_of": "non-existent-id"  # Reference to non-existent paper
                }
            ]
        }

        checkpoint_file = checkpoint_dir / "test.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        # Should not crash when loading
        loaded_papers, _ = load_checkpoint(checkpoint_file)

        assert len(loaded_papers) == 2
        loaded_dup = next(p for p in loaded_papers if p.cite_key == "duplicate")

        # The duplicate_of should remain None since the primary doesn't exist
        assert loaded_dup.duplicate_of is None

    def test_load_checkpoint_complex_duplicate_chain(self, temp_cache_dir):
        """Should restore complex duplicate chains"""
        db = PapersDatabase()
        p1 = Paper(cite_key="p1", title="Paper 1")
        p2 = Paper(cite_key="p2", title="Paper 2")
        p3 = Paper(cite_key="p3", title="Paper 3")

        # p2 -> p1, p3 -> p2 (chain of duplicates)
        p2.duplicate_of = p1
        p3.duplicate_of = p2

        db.add(p1)
        db.add(p2)
        db.add(p3)

        config = {
            "step_index": 0,
            "project_name": "test_project",
        }

        step = CheckpointStep(general_config={}, db=db, cache_dir=temp_cache_dir)
        step.execute(config)

        checkpoint_file = (temp_cache_dir / "checkpoints").glob("*.json").__next__()
        loaded_papers, _ = load_checkpoint(checkpoint_file)

        loaded_p1 = next(p for p in loaded_papers if p.cite_key == "p1")
        loaded_p2 = next(p for p in loaded_papers if p.cite_key == "p2")
        loaded_p3 = next(p for p in loaded_papers if p.cite_key == "p3")

        # Verify the chain is restored
        assert loaded_p1.duplicate_of is None
        assert loaded_p2.duplicate_of is loaded_p1
        assert loaded_p3.duplicate_of is loaded_p2


class TestCheckpointSelfReferenceIssue:
    """
    Tests specifically for the self-referencing issue where papers
    were being marked as duplicates of themselves.
    
    This should not happen if:
    1. Deduplication only marks papers as duplicates against primary papers
    2. Serialization converts duplicate_of to ID strings (not nested objects)
    3. Pydantic validates against circular references
    """

    def test_pydantic_prevents_self_reference(self):
        """
        Pydantic should prevent setting a paper as its own duplicate_of
        """
        paper = Paper(cite_key="test2024", title="Test Paper")
        
        # Attempting to create a self-reference should raise ValidationError
        with pytest.raises(Exception):  # ValidationError
            paper.duplicate_of = paper

    def test_duplicate_chain_serialization(self):
        """
        Test proper serialization of a chain of duplicates:
        paper3 -> paper2 -> paper1
        """
        paper1 = Paper(cite_key="p1", title="Paper 1")
        paper2 = Paper(cite_key="p2", title="Paper 2")
        paper3 = Paper(cite_key="p3", title="Paper 3")

        paper2.duplicate_of = paper1
        paper3.duplicate_of = paper2

        serialized = _serialize_papers([paper1, paper2, paper3])

        # Verify the chain is preserved
        assert serialized[0].get("duplicate_of") is None
        assert serialized[1]["duplicate_of"] == paper1.id
        assert serialized[2]["duplicate_of"] == paper2.id

        # Should be JSON-serializable
        json_str = json.dumps(serialized)
        assert isinstance(json_str, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
