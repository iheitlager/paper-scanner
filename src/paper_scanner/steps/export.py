"""
Database output step for paper scanner

Exports papers database to various formats (JSONL, BibTeX)
"""

from pathlib import Path
from typing import Dict, Any, List
import json
from rich.console import Console

from ..io.json import papers_to_jsonl
from ..io.bibtex import papers_to_bibtex
from ..core.models import Paper

# Initialize rich console
console = Console()


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute database output step
    
    Args:
        config: Step configuration (includes format and output_path)
        papers_db: Current papers database
        verbose: Enable verbose output
        dry_run: Don't actually write files
    
    Returns:
        Dictionary with execution results
    """
    
    output_format = config.get("format", "jsonl").lower()
    output_path = config.get("output_path")
    exclude_none = config.get("exclude_none", True)
    duplicates_option = config.get("duplicates", False)  # false, true, or "only"
    overwrite = config.get("overwrite", False)  # Default to False - fail on existing files
    
    # Expand tilde and resolve the path
    if output_path:
        output_path = str(Path(output_path).expanduser().resolve())
    
    # Filter papers based on duplicates option
    if duplicates_option == "only":
        # Export only duplicates
        papers_to_export = [p for p in papers_db if p.duplicate_of is not None]
        duplicates_label = "duplicate papers only"
    elif duplicates_option is True:
        # Export all papers (with duplicates)
        papers_to_export = papers_db
        duplicates_label = "all papers (including duplicates)"
    else:
        # Export only unique papers (no duplicates)
        papers_to_export = [p for p in papers_db if p.duplicate_of is None]
        duplicates_label = "unique papers only"
    
    results = {
        "step": "output_db",
        "format": output_format,
        "papers_exported": len(papers_to_export),
        "papers_total": len(papers_db),
        "duplicates_option": duplicates_option,
        "output_path": output_path,
        "status": "success",
        "error": None
    }
    
    if not output_path:
        error_msg = "output_path is required"
        results["status"] = "error"
        results["error"] = error_msg
        if verbose:
            console.print(f"  [red]✗ Error: {error_msg}[/red]")
        return results
    
    if output_format not in ["jsonl", "bibtex", "json"]:
        error_msg = f"Unsupported format: {output_format}. Supported: jsonl, json, bibtex"
        results["status"] = "error"
        results["error"] = error_msg
        if verbose:
            console.print(f"  [red]✗ Error: {error_msg}[/red]")
        return results
    
    try:
        # Create output directory if needed
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists and overwrite is False
        if path.exists() and not overwrite:
            error_msg = f"File already exists and overwrite=False: {output_path}"
            results["status"] = "error"
            results["error"] = error_msg
            if verbose:
                console.print(f"  [red]✗ Error: {error_msg}[/red]")
            return results
        
        if verbose:
            # Build descriptive message based on duplicates option
            if duplicates_option == "only":
                export_desc = f"[cyan]duplicate papers[/cyan] ({len(papers_to_export)}/{len(papers_db)})"
            elif duplicates_option is True:
                export_desc = f"[cyan]all papers[/cyan] ({len(papers_to_export)}/{len(papers_db)})"
            else:
                export_desc = f"[cyan]unique papers[/cyan] ({len(papers_to_export)}/{len(papers_db)})"
            
            console.print(f"\n  [bold cyan]Exporting {export_desc} to {output_format}[/bold cyan]")
            console.print(f"    [yellow]Papers:[/yellow] {duplicates_label} ({len(papers_to_export)}/{len(papers_db)})")
            console.print(f"    [yellow]Output path:[/yellow] {output_path}")
        
        if not dry_run:
            if output_format == "jsonl":
                # Export to JSONL format
                jsonl_content = papers_to_jsonl(papers_to_export, exclude_none=exclude_none)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(jsonl_content)
                
                # Count lines
                line_count = len(papers_to_export)
                results["output_format"] = "JSONL (one JSON object per line)"
                results["file_size_bytes"] = len(jsonl_content.encode('utf-8'))
                
                if verbose:
                    console.print(f"    [green]✓ Exported {line_count} papers to JSONL[/green]")
                    console.print(f"    [cyan]File size:[/cyan] {results['file_size_bytes']} bytes")
            
            elif output_format == "json":
                # Export to JSON format (array of papers)
                papers_dicts = [p.model_dump(exclude_none=exclude_none) for p in papers_to_export]
                json_content = json.dumps(papers_dicts, indent=2, default=str)
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(json_content)
                
                results["output_format"] = "JSON (array of papers)"
                results["file_size_bytes"] = len(json_content.encode('utf-8'))
                
                if verbose:
                    console.print(f"    [green]✓ Exported {len(papers_to_export)} papers to JSON array[/green]")
                    console.print(f"    [cyan]File size:[/cyan] {results['file_size_bytes']} bytes")
            
            elif output_format == "bibtex":
                # Export to BibTeX format
                bibtex_content = papers_to_bibtex(papers_to_export)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(bibtex_content)
                
                results["output_format"] = "BibTeX"
                results["file_size_bytes"] = len(bibtex_content.encode('utf-8'))
                
                if verbose:
                    console.print(f"    [green]✓ Exported {len(papers_to_export)} papers to BibTeX[/green]")
                    console.print(f"    [cyan]File size:[/cyan] {results['file_size_bytes']} bytes")
        
        else:
            # Dry run - just show what would happen
            if output_format == "jsonl":
                results["output_format"] = "JSONL (one JSON object per line)"
                if verbose:
                    console.print(f"    [yellow][DRY RUN] Would export {len(papers_to_export)} papers to JSONL[/yellow]")
            elif output_format == "json":
                results["output_format"] = "JSON (array of papers)"
                if verbose:
                    console.print(f"    [yellow][DRY RUN] Would export {len(papers_to_export)} papers to JSON array[/yellow]")
            elif output_format == "bibtex":
                results["output_format"] = "BibTeX"
                if verbose:
                    console.print(f"    [yellow][DRY RUN] Would export {len(papers_to_export)} papers to BibTeX[/yellow]")
        
        return results
    
    except Exception as e:
        error_msg = f"Failed to export database: {str(e)}"
        results["status"] = "error"
        results["error"] = error_msg
        if verbose:
            console.print(f"  [red]✗ Error exporting database: {str(e)}[/red]")
        return results
