"""
BibTeX import step for paper scanner

Sequentially imports BibTeX files and adds papers to the database
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from rich.console import Console

from ..io.bibtex import bibtex_file_to_papers
from ..core.models import Paper
from ..core.enum import DiscoveryMethod

# Initialize rich console
console = Console()


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute BibTeX import step
    
    Args:
        config: Step configuration (includes batch_id and imports list)
        papers_db: Current papers database (list of Paper objects)
        verbose: Enable verbose output
        dry_run: Don't actually import, just show what would happen
    
    Returns:
        Dictionary with execution results
    """
    
    batch_id = config.get("batch_id", f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    imports = config.get("imports", [])
    
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
                # Parse BibTeX file
                papers = bibtex_file_to_papers(
                    str(path),
                    source_type=source_type,
                    discovery_method=DiscoveryMethod.KEYWORD_SEARCH,
                    import_batch_id=batch_id
                )
                
                # Add to database
                papers_db.extend(papers)
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
                papers = bibtex_file_to_papers(str(path))
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
