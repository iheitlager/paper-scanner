"""
Patch step for paper scanner

Updates existing paper records by DOI with field values from an external file or inline config.
Supports replacing and appending field values.
"""

import sys
import json
import yaml
import copy
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from rich.console import Console

from ..core.database import PapersDatabase
from ..core.models import Paper

# Initialize rich console
console = Console(file=sys.stderr)


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate patch step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check that either 'file' or 'patches' is provided
    has_file = "file" in config
    has_patches = "patches" in config
    
    if not has_file and not has_patches:
        errors.append("Either 'file' or 'patches' must be specified")
    
    # Validate file path if provided
    if has_file:
        file_path = config["file"]
        if not isinstance(file_path, str):
            errors.append("'file' must be a string")
    
    # Validate patches structure if provided
    if has_patches:
        patches = config["patches"]
        if not isinstance(patches, list):
            errors.append("'patches' must be a list")
        else:
            for i, patch in enumerate(patches):
                if not isinstance(patch, dict):
                    errors.append(f"Patch {i} must be a dictionary")
                elif "doi" not in patch:
                    errors.append(f"Patch {i} missing required 'doi' field")
                elif not isinstance(patch.get("replace_fields", {}), dict):
                    errors.append(f"Patch {i} 'replace_fields' must be a dictionary")
                elif not isinstance(patch.get("append_fields", {}), dict):
                    errors.append(f"Patch {i} 'append_fields' must be a dictionary")
    
    return (len(errors) == 0, errors)


def _load_patches_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Load patches from YAML or JSON file.

    Args:
        file_path: Path to patch file

    Returns:
        List of patch dictionaries

    Raises:
        IOError: If file cannot be read
        ValueError: If file format is invalid
    """
    if not file_path.exists():
        raise IOError(f"File not found: {file_path}")

    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except IOError as e:
        raise IOError(f"Failed to read file {file_path}: {e}")

    # Determine format by extension
    if file_path.suffix.lower() in ['.yaml', '.yml']:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
    elif file_path.suffix.lower() == '.json':
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}")
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}. Use .yaml, .yml, or .json")

    # Extract patches array
    if isinstance(data, dict):
        patches = data.get("patches", [])
    elif isinstance(data, list):
        patches = data
    else:
        raise ValueError("File must contain a 'patches' array or be an array directly")

    return patches


def _apply_patch_to_paper(paper: Paper, patch: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Apply a patch to a paper object.

    Args:
        paper: Paper to patch
        patch: Patch dictionary with replace_fields and append_fields

    Returns:
        Tuple of (success, error_message)
    """
    replace_fields = patch.get("replace_fields", {})
    append_fields = patch.get("append_fields", {})

    try:
        # Apply replace operations
        for field_name, value in replace_fields.items():
            if not hasattr(paper, field_name):
                return False, f"Paper has no field '{field_name}'"
            setattr(paper, field_name, value)

        # Apply append operations (for list fields)
        for field_name, value in append_fields.items():
            if not hasattr(paper, field_name):
                return False, f"Paper has no field '{field_name}'"

            current = getattr(paper, field_name)

            # Handle string appending
            if isinstance(current, str):
                if not isinstance(value, str):
                    return False, f"Cannot append non-string to string field '{field_name}'"
                new_value = current + value if current else value
                setattr(paper, field_name, new_value)

            # Handle list appending
            elif isinstance(current, list):
                if isinstance(value, list):
                    current.extend(value)
                else:
                    current.append(value)

            else:
                return False, f"Cannot append to field '{field_name}' of type {type(current).__name__}"

        return True, None

    except Exception as e:
        return False, str(e)


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute patch step - update existing papers based on DOI matching.

    Args:
        config: Step configuration with 'file' or 'patches' keys
        papers_db: Current papers database
        verbose: Enable verbose output
        dry_run: If True, don't actually update papers in database

    Returns:
        Execution result with patch statistics
    """

    patches = []
    source_description = ""

    # Load patches from file or config
    if "file" in config:
        file_path = Path(config["file"]).expanduser()
        source_description = f"file '{file_path}'"

        console.print(f"[bold blue]Loading patches from:[/bold blue] {file_path}")

        try:
            patches = _load_patches_from_file(file_path)
        except (IOError, ValueError) as e:
            return {
                "status": "error",
                "error": str(e),
                "papers_count": papers_db.count(primary_only=False)
            }

    elif "patches" in config:
        patches = config["patches"]
        source_description = "inline configuration"
        console.print(f"[bold blue]Applying patches from:[/bold blue] {source_description}")

    if not patches:
        return {
            "status": "success",
            "message": "No patches to apply",
            "patches_found": 0,
            "patches_applied": 0,
            "patches_failed": 0,
            "papers_count": papers_db.count(primary_only=False)
        }

    # Process patches
    patches_applied = 0
    patches_failed = 0
    failed_patches = []

    for i, patch in enumerate(patches):
        doi = patch.get("doi")

        if not doi:
            console.print(f"[yellow]⚠️  Patch {i}: Missing 'doi' field[/yellow]")
            patches_failed += 1
            failed_patches.append((i, "Missing 'doi' field"))
            continue

        # Find papers by DOI
        matching_papers = papers_db.get_by_doi(doi, primary_only=True)

        if not matching_papers:
            console.print(f"[red]✗ Patch {i}: No papers found with DOI '{doi}'[/red]")
            patches_failed += 1
            failed_patches.append((i, f"No papers found with DOI '{doi}'"))
            continue

        # Apply patch to matching papers
        for paper in matching_papers:
            # In dry_run mode, validate on a copy to avoid modifying the original
            working_paper = copy.deepcopy(paper) if dry_run else paper

            success, error = _apply_patch_to_paper(working_paper, patch)

            if not success:
                console.print(f"[red]✗ Patch {i}: Failed to apply to DOI '{doi}': {error}[/red]")
                patches_failed += 1
                failed_patches.append((i, error))
                continue

            # Update in database (only in non-dry_run mode)
            if not dry_run:
                try:
                    papers_db.update(working_paper)
                except Exception as e:
                    console.print(f"[red]✗ Patch {i}: Failed to update paper: {e}[/red]")
                    patches_failed += 1
                    failed_patches.append((i, str(e)))
                    continue

            patches_applied += 1

    # Result summary - one-line feedback format
    message = f"Patched {patches_applied} record{'s' if patches_applied != 1 else ''}"
    if patches_failed > 0:
        message += f" ({patches_failed} failed)"

    if patches_failed == 0:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[yellow]⚠️  {message}[/yellow]")

    return {
        "status": "success" if patches_failed == 0 else "partial",
        "patches_found": len(patches),
        "patches_applied": patches_applied,
        "patches_failed": patches_failed,
        "failed_details": failed_patches if failed_patches else None,
        "papers_count": papers_db.count(primary_only=False)
    }
