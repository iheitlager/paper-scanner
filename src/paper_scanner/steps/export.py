"""
Database output step for paper scanner

Exports papers database to various formats (JSONL, BibTeX)
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json
from rich.console import Console

from ..io.json import papers_to_jsonl
from ..io.bibtex import papers_to_bibtex
from ..core.models import Paper
from ..core.database import PapersDatabase
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)

VALID_FORMATS = {"jsonl", "bibtex"}
VALID_DUPLICATES = {False, True, "only"}


class ExportStep(BaseStep):
    """Export papers database to various formats."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate export step configuration.
        
        Args:
            config: Step configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check format
        if "format" in config:
            fmt = config["format"]
            if fmt.lower() not in VALID_FORMATS:
                errors.append(f"'format' must be one of {VALID_FORMATS}, got '{fmt}'")
        
        # Check output (new parameter) or output_path (legacy)
        has_output = "output" in config
        has_output_path = "output_path" in config
        
        if not has_output and not has_output_path:
            errors.append("Either 'output' or 'output_path' is required")
        elif has_output:
            if not isinstance(config["output"], str):
                errors.append("'output' must be a string")
            elif config["output"] != "stdout" and not config["output"]:
                errors.append("'output' must be either 'stdout' or a file path")
        elif has_output_path:
            if not isinstance(config["output_path"], str):
                errors.append("'output_path' must be a string")
        
        # Check boolean fields
        if "exclude_none" in config and not isinstance(config["exclude_none"], bool):
            errors.append("'exclude_none' must be a boolean")
        
        if "overwrite" in config and not isinstance(config["overwrite"], bool):
            errors.append("'overwrite' must be a boolean")
        
        # Check duplicates option
        if "duplicates" in config:
            dup = config["duplicates"]
            if dup not in VALID_DUPLICATES:
                errors.append(f"'duplicates' must be one of {VALID_DUPLICATES}, got {dup}")
        
        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute database export step
        
        Args:
            config: Step configuration (includes format and output/output_path)
            verbose: Enable verbose output
            dry_run: Don't actually write files
            debug: Enable debug output
        
        Returns:
            Dictionary with execution results
        """
        
        output_format = config.get("format", "jsonl").lower()
        
        # Support both 'output' (new) and 'output_path' (legacy)
        output_target = config.get("output") or config.get("output_path")
        is_stdout = output_target == "stdout"
        
        exclude_none = config.get("exclude_none", True)
        duplicates_option = config.get("duplicates", False)  # false, true, or "only"
        overwrite = config.get("overwrite", False)  # Default to False - fail on existing files
        
        # Expand tilde and resolve the path (only if not stdout)
        output_path = None
        if output_target and not is_stdout:
            output_path = str(Path(output_target).expanduser().resolve())
        
        # Filter papers based on duplicates option
        if duplicates_option == "only":
            # Export only duplicates
            papers_to_export = self.db.find(lambda p: p.duplicate_of is not None, primary_only=False)
            duplicates_label = "duplicate papers only"
        elif duplicates_option is True:
            # Export all papers (with duplicates)
            papers_to_export = self.db.to_list(primary_only=False)
            duplicates_label = "all papers (including duplicates)"
        else:
            # Export only unique papers (no duplicates)
            papers_to_export = self.db.to_list(primary_only=True)
            duplicates_label = "unique papers only"
        
        results = {
            "step": "export",
            "format": output_format,
            "papers_exported": len(papers_to_export),
            "papers_total": self.db.count(primary_only=False),
            "duplicates_option": duplicates_option,
            "output_path": output_path or "stdout",
            "status": "success",
            "error": None
        }
        
        if not output_target:
            error_msg = "Either 'output' or 'output_path' is required"
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
            # Create output directory if needed (only for file output)
            if not is_stdout and output_path:
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
            else:
                path = None
            
            if verbose:
                # Build descriptive message based on duplicates option
                total_count = self.db.count(primary_only=False)
                if duplicates_option == "only":
                    export_desc = f"[cyan]duplicate papers[/cyan] ({len(papers_to_export)}/{total_count})"
                elif duplicates_option is True:
                    export_desc = f"[cyan]all papers[/cyan] ({len(papers_to_export)}/{total_count})"
                else:
                    export_desc = f"[cyan]unique papers[/cyan] ({len(papers_to_export)}/{total_count})"
                
                console.print(f"\n  [bold cyan]Exporting {export_desc} to {output_format}[/bold cyan]")
                console.print(f"    [yellow]Papers:[/yellow] {duplicates_label} ({len(papers_to_export)}/{total_count})")
                console.print(f"    [yellow]Output path:[/yellow] {output_path}")
            
            if not dry_run:
                if output_format == "jsonl":
                    # Export to JSONL format
                    jsonl_content = papers_to_jsonl(papers_to_export, exclude_none=exclude_none)
                    
                    if is_stdout:
                        sys.stdout.write(jsonl_content)
                    else:
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
                    
                    if is_stdout:
                        sys.stdout.write(json_content)
                    else:
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
                    
                    if is_stdout:
                        sys.stdout.write(bibtex_content)
                    else:
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
