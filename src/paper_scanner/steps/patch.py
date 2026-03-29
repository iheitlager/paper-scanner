"""
Patch step for paper scanner

Updates existing paper records by DOI with field values from an external file or inline config.
Supports replacing and appending field values. Dot-notation paths (e.g. screening.final_decision)
are supported for nested Pydantic model fields.
"""

import copy
import enum
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel
from rich.console import Console

from paper_scanner.core.enum import StepStatus

from ..core.models import Paper
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)
logger = logging.getLogger(__name__)

# Keys recognized inside a patch entry (besides 'doi')
_KNOWN_PATCH_KEYS = {"doi", "replace_fields", "append_fields", "set"}



def _has_nested(obj: Any, path: str) -> bool:
    """Check if a dot-notation path exists on a (possibly nested) object."""
    parts = path.split(".")
    for part in parts:
        if not hasattr(obj, part):
            return False
        obj = getattr(obj, part)
    return True


def _get_nested(obj: Any, path: str) -> Any:
    """Get a value via dot-notation path."""
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _set_nested(obj: Any, path: str, value: Any) -> None:
    """Set a value via dot-notation path, coercing enums when needed."""
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)

    field_name = parts[-1]

    # Coerce string values to enums when the target field is an enum type
    if isinstance(obj, BaseModel) and isinstance(value, str):
        field_info = obj.__class__.model_fields.get(field_name)
        if field_info and field_info.annotation:
            annotation = field_info.annotation
            # Unwrap Optional[X] → X
            origin = getattr(annotation, "__origin__", None)
            if origin is type(None):
                pass
            elif hasattr(annotation, "__args__"):
                for arg in annotation.__args__:
                    if isinstance(arg, type) and issubclass(arg, enum.Enum):
                        annotation = arg
                        break
            if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
                value = annotation(value)

    setattr(obj, field_name, value)


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
    if file_path.suffix.lower() in ('.yaml', '.yml'):
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

    Supports dot-notation paths (e.g. ``screening.final_decision``) and
    automatic enum coercion for Pydantic model fields. The ``set:`` key is
    accepted as an alias for ``replace_fields:``.

    Args:
        paper: Paper to patch
        patch: Patch dictionary with replace_fields/set and append_fields

    Returns:
        Tuple of (success, error_message)
    """
    # 'set' is an alias for 'replace_fields'
    replace_fields = patch.get("replace_fields", {})
    set_fields = patch.get("set", {})
    replace_fields = {**replace_fields, **set_fields}

    append_fields = patch.get("append_fields", {})

    # Warn on unknown keys
    unknown_keys = set(patch.keys()) - _KNOWN_PATCH_KEYS
    for key in sorted(unknown_keys):
        logger.warning("Patch for DOI '%s': unknown key '%s' (ignored)", patch.get("doi", "?"), key)

    try:
        # Apply replace operations (supports dot-notation)
        for field_path, value in replace_fields.items():
            if not _has_nested(paper, field_path):
                return False, f"Paper has no field '{field_path}'"
            _set_nested(paper, field_path, value)

        # Apply append operations (for list fields, supports dot-notation)
        for field_path, value in append_fields.items():
            if not _has_nested(paper, field_path):
                return False, f"Paper has no field '{field_path}'"

            current = _get_nested(paper, field_path)

            # Handle string appending
            if isinstance(current, str):
                if not isinstance(value, str):
                    return False, f"Cannot append non-string to string field '{field_path}'"
                new_value = current + value if current else value
                _set_nested(paper, field_path, new_value)

            # Handle list appending
            elif isinstance(current, list):
                if isinstance(value, list):
                    current.extend(value)
                else:
                    current.append(value)

            else:
                return False, f"Cannot append to field '{field_path}' of type {type(current).__name__}"

        return True, None

    except Exception as e:
        return False, str(e)



# Class-based step interface (new architecture)
class PatchStep(BaseStep):
    """Wrapper for patch step (legacy function-based)."""

    @staticmethod
    def validate(config):
        """Delegate to module validate function."""
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
                    elif not isinstance(patch.get("set", {}), dict):
                        errors.append(f"Patch {i} 'set' must be a dictionary")
                    elif not isinstance(patch.get("append_fields", {}), dict):
                        errors.append(f"Patch {i} 'append_fields' must be a dictionary")

        return (len(errors) == 0, errors)

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        """
        Execute patch step - update existing papers based on DOI matching.

        Args:
            config: Step configuration with 'file' or 'patches' keys
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
                    "status": StepStatus.ERROR,
                    "error": str(e),
                    "papers_count": self.db.count(primary_only=False)
                }

        elif "patches" in config:
            patches = config["patches"]
            source_description = "inline configuration"
            if verbose:
                console.print(f"[bold blue]Applying patches from:[/bold blue] {source_description}")

        if not patches:
            return {
                "status": StepStatus.SUCCESS,
                "message": "No patches to apply",
                "patches_found": 0,
                "patches_applied": 0,
                "patches_failed": 0,
                "papers_count": self.db.count(primary_only=False)
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
            matching_papers = self.db.get_by_doi(doi, primary_only=True)

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
                        self.db.update(working_paper)
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

        return {
            "status": StepStatus.SUCCESS if patches_failed == 0 else StepStatus.WARNING,
            "patches_found": len(patches),
            "patches_applied": patches_applied,
            "patches_failed": patches_failed,
            "failed_details": failed_patches if failed_patches else None,
            "papers_count": self.db.count(primary_only=False)
        }

