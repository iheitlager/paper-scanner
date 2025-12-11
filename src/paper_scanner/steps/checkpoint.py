"""
Checkpoint step - Save paper database state at key points in processing

This step exports the current paper database to a checkpoint file in the cache
directory. The filename is deterministic based on project name hash and step order,
allowing the pipeline to resume from this checkpoint on subsequent runs.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

from rich.console import Console

from paper_scanner.core.models import Paper
from paper_scanner.core.database import PapersDatabase
from paper_scanner.io.json import paper_to_dict

console = Console()


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


def execute(config: Dict[str, Any], papers: PapersDatabase, verbose: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    """
    Execute checkpoint step
    
    Args:
        config: Step configuration (may contain 'cache_dir' and 'step_index')
        papers: Current papers database
        verbose: Enable verbose output
        dry_run: Don't actually save checkpoint
    
    Returns:
        Result dictionary
    """
    
    # Get cache directory and step index from config
    cache_dir = config.get("cache_dir")
    step_index = config.get("step_index")
    project_name = config.get("project_name", "Unknown")
    
    if not cache_dir:
        return {
            "status": "error",
            "message": "cache_dir not provided to checkpoint step"
        }
    
    cache_dir = Path(cache_dir)
    
    # Create checkpoints subdirectory
    checkpoints_dir = cache_dir / "checkpoints"
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
            "papers_count": papers.count(primary_only=False),
            "papers": _serialize_papers(papers.to_list(primary_only=False))
        }
        
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2)
    
    if verbose:
        console.print(f"[cyan]Checkpoint saved[/cyan]: {checkpoint_file.name} ({papers.count(primary_only=False)} papers)")
    
    return {
        "status": "ok",
        "checkpoint_file": str(checkpoint_file),
        "papers_count": papers.count(primary_only=False)
    }


def load_checkpoint(checkpoint_file: Path) -> tuple[List[Paper], int]:
    """
    Load papers from a checkpoint file
    
    Args:
        checkpoint_file: Path to checkpoint file
    
    Returns:
        Tuple of (papers_list, step_index)
    """
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    papers = _deserialize_papers(data.get("papers", []))
    step_index = data.get("step_index", 0)
    
    return papers, step_index
