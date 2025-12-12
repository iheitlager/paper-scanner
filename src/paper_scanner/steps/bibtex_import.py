"""
BibTeX import step for paper scanner

Sequentially imports BibTeX files and adds papers to the database
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from rich.console import Console
import yaml

from ..io.bibtex import bibtex_file_to_papers, load_type_mapping_config
from ..core.models import Paper
from ..core.database import PapersDatabase
from ..core.enum import DiscoveryMethod

# Initialize rich console
console = Console(file=sys.stderr)

# Valid source types
VALID_SOURCE_TYPES = {"scopus", "web_of_science", "ieee_xplore", "other"}


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate bibtex_import step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check batch_id
    if "batch_id" in config and not isinstance(config["batch_id"], str):
        errors.append("'batch_id' must be a string")
    
    # Check imports list
    imports = config.get("imports", [])
    if not isinstance(imports, list):
        errors.append("'imports' must be a list")
    else:
        for i, imp in enumerate(imports):
            if not isinstance(imp, dict):
                errors.append(f"Import {i} must be a dictionary")
                continue
            
            # Check required fields
            if "file_path" not in imp:
                errors.append(f"Import {i} missing required field 'file_path'")
            elif not isinstance(imp["file_path"], str):
                errors.append(f"Import {i} 'file_path' must be a string")
            
            if "source_type" in imp:
                source_type = imp["source_type"]
                if source_type not in VALID_SOURCE_TYPES:
                    errors.append(f"Import {i} 'source_type' must be one of {VALID_SOURCE_TYPES}, got '{source_type}'")
            
            if "expected_count" in imp:
                expected = imp["expected_count"]
                if not isinstance(expected, int) or expected < 0:
                    errors.append(f"Import {i} 'expected_count' must be a non-negative integer")
            
            if "fix_cite_key" in imp:
                fix_cite_key = imp["fix_cite_key"]
                if not isinstance(fix_cite_key, bool):
                    errors.append(f"Import {i} 'fix_cite_key' must be a boolean")
    
    # Check type_mapping_config_path
    if "type_mapping_config_path" in config and not isinstance(config["type_mapping_config_path"], str):
        errors.append("'type_mapping_config_path' must be a string")
    
    return len(errors) == 0, errors


def _fix_cite_key_collisions(papers: List[Paper], existing_db: PapersDatabase) -> int:
    """
    Fix cite_key collisions by adding _XX suffix to duplicates.
    
    For each paper with a cite_key that collides with existing entries in the database
    or with other papers in the import, add a _XX suffix where XX is a decimal number
    starting from 01 and incrementing until the key is unique.
    
    Args:
        papers: List of papers to fix
        existing_db: Existing papers database to check against
    
    Returns:
        Number of cite_keys that were fixed (had collisions)
    """
    seen_keys = set()
    fixed_count = 0
    
    for paper in papers:
        original_key = paper.cite_key
        unique_key = original_key
        counter = 1
        
        # Check if the key already exists in the database or was already processed
        while existing_db.get_by_cite_key(unique_key) is not None or unique_key in seen_keys:
            unique_key = f"{original_key}_{counter:02d}"
            counter += 1
        
        # If the key was changed, increment fixed count
        if unique_key != original_key:
            fixed_count += 1
        
        paper.cite_key = unique_key
        seen_keys.add(unique_key)
    
    return fixed_count


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute BibTeX import step
    
    Args:
        config: Step configuration (includes batch_id and imports list)
        papers_db: Current papers database (PapersDatabase instance)
        verbose: Enable verbose output
        dry_run: Don't actually import, just show what would happen
    
    Returns:
        Dictionary with execution results
    """
    
    batch_id = config.get("batch_id", f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    imports = config.get("imports", [])
    type_mapping_config_path = config.get("type_mapping_config_path")
    
    # Load type mapping configuration
    type_mapping_config = None
    if type_mapping_config_path:
        if verbose:
            console.print(f"[cyan]Loading type mapping config from:[/cyan] {type_mapping_config_path}")
        type_mapping_config = load_type_mapping_config(type_mapping_config_path)
    else:
        # Use default location
        type_mapping_config = load_type_mapping_config()
        if verbose:
            console.print("[cyan]Using default type mapping configuration[/cyan]")
    
    results = {
        "step": "bibtex_import",
        "batch_id": batch_id,
        "total_files": len(imports),
        "files_processed": 0,
        "papers_imported": 0,
        "errors": [],
        "details": []
    }
    
    for import_spec in imports:
        name = import_spec.get("name", "Unknown")
        file_path = import_spec.get("file_path")
        source_type = import_spec.get("source_type", "manual")
        expected_count = import_spec.get("expected_count")
        fix_cite_key = import_spec.get("fix_cite_key", False)
        
        try:
            # Check file exists
            path = Path(file_path)
            if not path.exists():
                error_msg = f"File not found: {file_path}"
                results["errors"].append(error_msg)
                if verbose:
                    console.print(f"  [red]✗ {name}: {error_msg}[/red]")
                continue
            
            if verbose:
                console.print(f"\n  [bold cyan]Processing:[/bold cyan] {name}")
                console.print(f"    [yellow]File:[/yellow] {file_path}")
                console.print(f"    [yellow]Source:[/yellow] {source_type}")
            
            if not dry_run:
                # Parse BibTeX file with type mapping config
                papers = bibtex_file_to_papers(
                    str(path),
                    source_type=source_type,
                    discovery_method=DiscoveryMethod.KEYWORD_SEARCH,
                    import_batch_id=batch_id,
                    type_mapping_config=type_mapping_config
                )
                
                # Fix cite_key collisions if requested
                if fix_cite_key:
                    fixed_count = _fix_cite_key_collisions(papers, papers_db)
                    if verbose:
                        console.print(f"    [cyan]✓ Fixed {fixed_count} cite_key collisions[/cyan]")
                
                # Add to database
                papers_db.add_many(papers)
                count = len(papers)
                results["papers_imported"] += count
                
                if verbose:
                    console.print(f"    [green]✓ Imported {count} papers[/green]")
                    if expected_count:
                        match = "✓" if count == expected_count else "!"
                        style = "green" if count == expected_count else "yellow"
                        console.print(f"    [{style}]{match} Expected: {expected_count}, Got: {count}[/{style}]")
            else:
                # Dry run: just show what would happen
                papers = bibtex_file_to_papers(
                    str(path),
                    type_mapping_config=type_mapping_config
                )
                count = len(papers)
                if verbose:
                    console.print(f"    [yellow][DRY RUN] Would import {count} papers[/yellow]")
                    if expected_count:
                        match = "✓" if count == expected_count else "!"
                        style = "green" if count == expected_count else "yellow"
                        console.print(f"    [{style}]{match} Expected: {expected_count}, Would get: {count}[/{style}]")
            
            results["files_processed"] += 1
            results["details"].append({
                "name": name,
                "file_path": file_path,
                "source_type": source_type,
                "papers_imported": count if not dry_run else 0,
                "status": "success"
            })
            
        except Exception as e:
            error_msg = f"{name}: {str(e)}"
            results["errors"].append(error_msg)
            if verbose:
                console.print(f"  [red]✗ Error: {error_msg}[/red]")
            results["details"].append({
                "name": name,
                "file_path": file_path,
                "status": "error",
                "error": str(e)
            })
    
    return results
