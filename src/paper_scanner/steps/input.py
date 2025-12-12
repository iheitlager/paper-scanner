"""
Input step for paper scanner

Reads JSON Lines from file or stdin and adds papers to the database.
Supports both file-based import and stdin streaming.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
from rich.console import Console

from ..io.json import dict_to_paper
from ..core.models import Paper
from ..core.database import PapersDatabase
from ..core.enum import DiscoveryMethod

# Initialize rich console
console = Console(file=sys.stderr)


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate input step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check that either 'file' or 'input' is provided (or both, but 'file' takes precedence)
    has_file = "file" in config
    has_input = "input" in config
    
    if not has_file and not has_input:
        errors.append("Either 'file' or 'input' must be specified")
    
    # Validate file path if provided
    if has_file:
        file_path = config["file"]
        if not isinstance(file_path, str):
            errors.append("'file' must be a string")
    
    # Validate input source if provided
    if has_input:
        input_source = config["input"]
        if not isinstance(input_source, str):
            errors.append("'input' must be a string")
        elif input_source not in {"stdin"}:
            errors.append(f"'input' must be 'stdin', got '{input_source}'")
    
    # Validate expected_count if provided
    if "expected_count" in config:
        expected = config["expected_count"]
        if not isinstance(expected, int) or expected < 0:
            errors.append("'expected_count' must be a non-negative integer")
    
    return len(errors) == 0, errors


def _read_json_lines(file_handle) -> List[Dict[str, Any]]:
    """
    Read JSON Lines from a file handle.
    
    Args:
        file_handle: Open file handle or stdin
    
    Returns:
        List of parsed JSON objects
    """
    records = []
    for line_num, line in enumerate(file_handle, 1):
        line = line.strip()
        if not line:
            # Skip empty lines
            continue
        
        try:
            record = json.loads(line)
            records.append(record)
        except json.JSONDecodeError as e:
            console.print(f"[yellow]⚠️  Skipping line {line_num}: Invalid JSON - {e}[/yellow]")
            continue
    
    return records


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute input step - read JSON Lines from file or stdin and add to database.
    
    Args:
        config: Step configuration with 'file' or 'input' keys
        papers_db: Current papers database
        verbose: Enable verbose output
        dry_run: If True, don't actually add papers to database
    
    Returns:
        Execution result with import statistics
    """
    
    records = []
    source_description = ""
    
    # Determine source and read records
    if "file" in config:
        file_path = Path(config["file"]).expanduser()
        source_description = f"file '{file_path}'"
        
        console.print(f"[bold blue]Reading from file:[/bold blue] {file_path}")
        
        if not file_path.exists():
            return {
                "status": "error",
                "error": f"File not found: {file_path}",
                "papers_count": papers_db.count(primary_only=False)
            }
        
        try:
            with open(file_path, 'r') as f:
                records = _read_json_lines(f)
        except IOError as e:
            return {
                "status": "error",
                "error": f"Failed to read file {file_path}: {e}",
                "papers_count": papers_db.count(primary_only=False)
            }
    
    elif "input" in config and config["input"] == "stdin":
        source_description = "stdin"
        console.print(f"[bold blue]Reading from stdin...[/bold blue]")
        records = _read_json_lines(sys.stdin)
    
    # Validate expected_count if provided
    expected_count = config.get("expected_count")
    if expected_count is not None and len(records) != expected_count:
        console.print(
            f"[yellow]⚠️  Expected {expected_count} records but got {len(records)}[/yellow]"
        )
    
    # Convert records to Paper objects
    papers = []
    failed_count = 0
    
    for i, record in enumerate(records):
        try:
            # Convert dict to Paper
            paper = dict_to_paper(record)
            
            # Ensure paper has discovery method set
            if paper.discovery is None:
                from ..core.models import Discovery
                paper.discovery = Discovery(
                    method=DiscoveryMethod.MANUAL,
                    date=datetime.now()
                )
            
            papers.append(paper)
        except Exception as e:
            if verbose:
                console.print(f"[yellow]⚠️  Record {i+1}: Failed to convert - {e}[/yellow]")
            failed_count += 1
    
    # Add papers to database
    added_count = 0
    if not dry_run:
        for paper in papers:
            papers_db.add(paper)
        added_count = len(papers)
    
    # Display results
    total_before = papers_db.count(primary_only=False) - added_count
    console.print(
        f"[bold green]✓ Input from {source_description}[/bold green]"
    )
    console.print(f"  Records read: {len(records)}")
    console.print(f"  Records converted: {len(papers)}")
    console.print(f"  Records failed: {failed_count}")
    console.print(f"  Papers before: {total_before}")
    console.print(f"  Papers added: {added_count}")
    console.print(f"  Papers total: {papers_db.count(primary_only=False)}")
    
    result = {
        "status": "ok",
        "source": source_description,
        "records_read": len(records),
        "papers_converted": len(papers),
        "papers_failed": failed_count,
        "papers_added": added_count,
        "papers_count": papers_db.count(primary_only=False)
    }
    
    return result
