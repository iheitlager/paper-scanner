"""
Checkpoint step - Save paper database state at key points in processing

This step exports the current paper database to a checkpoint file in the cache
directory. The filename is deterministic based on project name hash and step order,
allowing the pipeline to resume from this checkpoint on subsequent runs.
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.models import Paper
from paper_scanner.io.json import paper_to_dict

from .base import BaseStep

console = Console(file=sys.stderr)


class CheckpointStep(BaseStep):
    """Save paper database state at key points in processing."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate checkpoint step configuration.
        
        Args:
            config: Step configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Checkpoint has no required configuration
        # It's a marker step that just saves state
        
        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute checkpoint step
        
        Args:
            config: Step configuration (may contain 'step_index')
            verbose: Enable verbose output
            dry_run: Don't actually save checkpoint
            debug: Enable debug output
        
        Returns:
            Result dictionary
        """
        
        # Get step index and project name from config
        step_index = config.get("step_index")
        project_name = config.get("project_name", "Unknown")
        
        # Create checkpoints subdirectory
        checkpoints_dir = self.cache_dir / "checkpoints"
        if not dry_run:
            checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate checkpoint filename
        checkpoint_name = _get_checkpoint_name(project_name, step_index)
        checkpoint_file = checkpoints_dir / checkpoint_name
        
        # Save checkpoint
        if not dry_run:
            checkpoint_data = {
                "project_name": project_name,
                "step_index": step_index,
                "timestamp": datetime.now().isoformat(),
                "papers_count": self.db.count(primary_only=False),
                "papers": _serialize_papers(self.db.to_list(primary_only=False))
            }
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2)
        
        if verbose:
            console.print(f"[cyan]Checkpoint saved[/cyan]: {checkpoint_file.name} ({self.db.count(primary_only=False)} papers)")
        
        return {
            "status": "ok",
            "checkpoint_file": str(checkpoint_file),
            "papers_count": self.db.count(primary_only=False)
        }

def _get_checkpoint_name(project_name: str, step_index: int) -> str:
    """
    Generate deterministic checkpoint filename

    Args:
        project_name: Name of the project (from definition file)
        step_index: Index of this step in the steps list (0-based)

    Returns:
        Filename like: checkpoint_<hash>_step_<index>.json
    """
    # Create hash of project name
    project_hash = hashlib.md5(project_name.encode()).hexdigest()[:8]
    return f"checkpoint_{project_hash}_step_{step_index:03d}.json"


def _serialize_papers(papers: List[Paper]) -> List[Dict[str, Any]]:
    """Convert papers to JSON-serializable format"""
    return [paper_to_dict(p, exclude_none=True) for p in papers]


def _deserialize_papers(data: List[Dict[str, Any]]) -> List[Paper]:
    """Convert JSON data back to Paper objects"""
    return [Paper(**item) for item in data]


def load_checkpoint(checkpoint_file: Path) -> tuple[List[Paper], int]:
    """
    Load papers from a checkpoint file with duplicate reference restoration.
    
    The checkpoint JSON stores duplicate_of as ID strings. When papers are deserialized
    individually, these references are lost. This function restores them in a second pass.
    
    Args:
        checkpoint_file: Path to checkpoint file
    
    Returns:
        Tuple of (papers_list, step_index)
    """
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # First pass: deserialize all papers
    papers_data = data.get("papers", [])
    papers = _deserialize_papers(papers_data)
    
    # Second pass: restore duplicate_of references from raw JSON
    # Create a map of paper ID to paper object for quick lookup
    id_to_paper = {p.id: p for p in papers}
    
    for raw_paper_data, paper in zip(papers_data, papers):
        # Check if the raw JSON has a duplicate_of ID
        if raw_paper_data.get("duplicate_of") and isinstance(raw_paper_data.get("duplicate_of"), str):
            duplicate_of_id = raw_paper_data["duplicate_of"]
            if duplicate_of_id in id_to_paper:
                # Restore the reference to the actual Paper object
                paper.duplicate_of = id_to_paper[duplicate_of_id]
    
    step_index = data.get("step_index", 0)
    
    return papers, step_index
