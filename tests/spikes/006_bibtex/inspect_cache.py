#!/usr/bin/env python3
"""
Validate and display statistics for the Crossref cache.

This script:
1. Scans the cache directory for cached responses
2. Validates JSON integrity
3. Checks for malformed or incomplete entries
4. Displays statistics with colored output
5. Can export a random cached record to stdout with -r flag
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def get_cache_dir() -> Path:
    """Get the cache directory path"""
    return Path.home() / ".crossref"


def validate_cache(export_errors: Optional[str] = None, export_failed: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
    """
    Validate all cache files and return statistics.
    
    Args:
        export_errors: Optional path to export not found records as JSON
        export_failed: Optional path to export invalid/failed records as JSON
    
    Returns:
        Tuple of (stats dict, error count)
    """
    cache_dir = get_cache_dir()
    stats = {
        "total_files": 0,
        "valid_files": 0,
        "invalid_files": 0,
        "total_size_mb": 0,
        "entries_with_references": 0,
        "entries_without_references": 0,
        "records_without_year": 0,
        "papers_by_year": defaultdict(int),
        "errors": [],
        # Categorized tracking for clarity
        "papers_no_references": [],  # Papers where Crossref returned no references
        "references_missing_doi": [],  # References found but missing DOI field
        "invalid_records": [],  # Track invalid/malformed records
    }

    if not cache_dir.exists():
        stats["errors"].append(f"Cache directory does not exist: {cache_dir}")
        return stats, 1

    # Scan all JSON files in cache directory
    json_files = list(cache_dir.glob("*.json"))
    stats["total_files"] = len(json_files)

    for cache_file in json_files:
        try:
            # Check file size
            file_size_mb = cache_file.stat().st_size / (1024 * 1024)
            stats["total_size_mb"] += file_size_mb

            # Validate JSON
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # If it's valid JSON, consider it valid (jq can parse it)
            if isinstance(data, dict):
                stats["valid_files"] += 1

                # Try to extract references if structure matches expected format
                if "message" in data and isinstance(data["message"], dict):
                    message = data["message"]
                    references = message.get("reference", [])

                    # Get citing paper info
                    citing_doi = message.get("DOI", "unknown")
                    citing_title = message.get("title", ["unknown"])[0] if message.get("title") else "unknown"

                    if references:
                        stats["entries_with_references"] += 1
                    else:
                        stats["entries_without_references"] += 1
                        # Track papers with no references found
                        stats["papers_no_references"].append({
                            "citing_doi": citing_doi,
                            "citing_title": citing_title,
                            "status": "needs_investigation"
                        })

                    # Extract publication year from references and track missing DOIs
                    for ref in references:
                        if isinstance(ref, dict):
                            year = ref.get("published-online", {}).get("date-parts", [[None]])[0][0]
                            if not year:
                                year = ref.get("issued", {}).get("date-parts", [[None]])[0][0]
                            if year:
                                stats["papers_by_year"][year] += 1

                            # Track references that SHOULD have DOI but don't (journal articles, conference papers)
                            ref_type = ref.get("type", "journal-article").lower()
                            cited_doi = ref.get("DOI")
                            # Only flag as missing if it's a publication type that typically has DOIs
                            if not cited_doi and ref_type in ("journal-article", "proceedings-article", "article", "journal"):
                                stats["references_missing_doi"].append({
                                    "citing_doi": citing_doi,
                                    "citing_title": citing_title,
                                    "reference_key": ref.get("key", "unknown"),
                                    "reference_title": ref.get("title", "unknown"),
                                    "reference_type": ref_type,
                                    "status": "needs_doi_lookup"
                                })

                    # Also track the citing paper's year
                    citing_year = message.get("issued", {}).get("date-parts", [[None]])[0][0]
                    if citing_year:
                        stats["papers_by_year"][citing_year] += 1
                    else:
                        stats["records_without_year"] += 1
            else:
                error_msg = f"Invalid JSON structure (not a dict): {cache_file.name}"
                stats["errors"].append(error_msg)
                stats["invalid_files"] += 1
                stats["invalid_records"].append({
                    "file": cache_file.name,
                    "error": error_msg
                })

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {cache_file.name}: {str(e)}"
            stats["errors"].append(error_msg)
            stats["invalid_files"] += 1
            stats["invalid_records"].append({
                "file": cache_file.name,
                "error": error_msg
            })
        except Exception as e:
            error_msg = f"Error processing {cache_file.name}: {str(e)}"
            stats["errors"].append(error_msg)
            stats["invalid_files"] += 1
            stats["invalid_records"].append({
                "file": cache_file.name,
                "error": error_msg
            })

    # Export issue records if requested
    if export_errors:
        try:
            export_path = Path(export_errors)
            # Export both categories of issues
            issues = {
                "papers_with_no_references": stats["papers_no_references"],
                "references_missing_doi": stats["references_missing_doi"]
            }
            with open(export_path, 'w') as f:
                json.dump(issues, f, indent=2)
        except Exception as e:
            stats["errors"].append(f"Failed to export errors to {export_errors}: {str(e)}")

    # Export invalid/failed records if requested
    if export_failed and stats["invalid_records"]:
        try:
            export_path = Path(export_failed)
            with open(export_path, 'w') as f:
                json.dump(stats["invalid_records"], f, indent=2)
        except Exception as e:
            stats["errors"].append(f"Failed to export failed records to {export_failed}: {str(e)}")

    return stats, len(stats["errors"])



def build_ascii_histogram(papers_by_year: Dict[int, int], max_width: int = 50) -> str:
    """
    Build an ASCII histogram of papers per year.
    
    Args:
        papers_by_year: Dict mapping year to paper count
        max_width: Maximum width of the histogram bar
        
    Returns:
        Formatted ASCII histogram string
    """
    if not papers_by_year:
        return "[dim]No data available[/dim]"

    sorted_years = sorted(papers_by_year.keys())
    max_count = max(papers_by_year.values()) if papers_by_year else 1

    lines = []
    for year in sorted_years:
        count = papers_by_year[year]
        bar_length = int((count / max_count) * max_width) if max_count > 0 else 0
        bar = "█" * bar_length
        lines.append(f"  {year} │ {bar} {count}")

    return "\n".join(lines)


def get_random_record(failed_only: bool = False) -> Optional[Dict[str, Any]]:
    """Get a random cached record from the cache directory and return it.
    
    Args:
        failed_only: If True, only return records with no references (failed records)
    
    Returns:
        A random cached record, or None if none found
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return None

    json_files = list(cache_dir.glob("*.json"))
    if not json_files:
        return None

    # If filtering for failed records, scan for ones without references
    if failed_only:
        failed_records = []
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                # Check if this is a failed record (no references)
                if isinstance(data, dict) and "message" in data:
                    references = data.get("message", {}).get("reference", [])
                    if not references:
                        failed_records.append(data)
            except Exception:
                continue

        if not failed_records:
            return None
        return random.choice(failed_records)

    # Pick a random file
    random_file = random.choice(json_files)

    try:
        with open(random_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        console = Console()
        console.print(f"[red]Error reading {random_file.name}: {e}[/red]")
        return None


def display_stats(stats: Dict[str, Any], export_path: Optional[str] = None, export_failed_path: Optional[str] = None) -> None:
    """Display cache statistics with colored output"""
    console = Console()

    # Create header
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]Crossref Cache Validation Report[/bold cyan]",
        border_style="cyan"
    ))
    console.print("\n")

    cache_dir = get_cache_dir()
    console.print(f"[dim]Cache directory:[/dim] {cache_dir}\n")

    # Create statistics table
    table = Table(title="Cache Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right")

    # Determine colors based on validity
    total_valid = stats["valid_files"]
    total_files = stats["total_files"]

    if total_files == 0:
        validity_color = "yellow"
        validity_text = "Empty"
    else:
        valid_percent = (total_valid / total_files) * 100
        if valid_percent == 100:
            validity_color = "green"
            validity_text = "✓ All Valid"
        elif valid_percent >= 90:
            validity_color = "yellow"
            validity_text = f"⚠ {valid_percent:.1f}% Valid"
        else:
            validity_color = "red"
            validity_text = f"✗ {valid_percent:.1f}% Valid"

    table.add_row("Total Cached Files", str(total_files))
    table.add_row(
        "Valid Files",
        Text(str(total_valid), style="green")
    )
    table.add_row(
        "Invalid Files",
        Text(str(stats["invalid_files"]), style="red" if stats["invalid_files"] > 0 else "green")
    )
    table.add_row(
        "Cache Status",
        Text(validity_text, style=validity_color)
    )

    table.add_row("[dim]─[/dim]" * 20, "")

    table.add_row(
        "Entries with References",
        Text(str(stats["entries_with_references"]), style="green")
    )
    table.add_row(
        "Entries without References",
        Text(str(stats["entries_without_references"]), style="yellow")
    )
    table.add_row(
        "Records without Year",
        Text(str(stats["records_without_year"]), style="dim")
    )
    table.add_row("Total Cache Size", f"{stats['total_size_mb']:.2f} MB")

    console.print(table)
    console.print("\n")

    # Display histogram
    if stats["papers_by_year"]:
        histogram = build_ascii_histogram(stats["papers_by_year"])
        console.print(Panel(
            histogram,
            title="[bold green]Papers Per Year[/bold green]",
            border_style="green",
            expand=False
        ))
        console.print("\n")

    # Display categorized issues in a single overview table
    if stats["papers_no_references"] or stats["references_missing_doi"]:
        issues_table = Table(title="📋 Issues Requiring Investigation", show_header=True, header_style="bold")
        issues_table.add_column("Issue Type", style="cyan")
        issues_table.add_column("Count", justify="right", style="yellow")
        issues_table.add_column("Description", style="dim")
        issues_table.add_column("Action", style="green")

        if stats["papers_no_references"]:
            issues_table.add_row(
                "[bold yellow]No References[/bold yellow]",
                str(len(stats["papers_no_references"])),
                "Papers where Crossref returned no references",
                "Verify if Crossref has data"
            )

        if stats["references_missing_doi"]:
            issues_table.add_row(
                "[bold cyan]Missing DOI[/bold cyan]",
                str(len(stats["references_missing_doi"])),
                "Journal/conference articles without DOI",
                "Lookup or enrich with DOI"
            )

        console.print()
        console.print(issues_table)
        console.print()

        if export_path:
            console.print(f"[green]✓ Exported detailed records to: {export_path}[/green]\n")
        else:
            console.print("[dim]Use -e/--error flag to export details for investigation[/dim]\n")

    # Display invalid/failed records info
    if stats["invalid_records"]:
        console.print(Panel(
            f"[red]{len(stats['invalid_records'])} invalid/malformed records[/red]",
            title="[bold red]Invalid Records[/bold red]",
            border_style="red",
            expand=False
        ))
        if export_failed_path:
            console.print(f"[green]✓ Exported to: {export_failed_path}[/green]\n")
        else:
            console.print("[dim]Use -f/--failed flag to export details[/dim]\n")

    # Display errors if any
    if stats["errors"]:
        error_panel = Panel(
            "\n".join([f"• {err}" for err in stats["errors"][:10]]),
            title="[bold red]Issues Found[/bold red]",
            border_style="red",
            expand=False
        )
        console.print(error_panel)
        if len(stats["errors"]) > 10:
            console.print(f"\n[dim]...and {len(stats['errors']) - 10} more issues[/dim]")
    else:
        console.print("[green]✓ No issues found![/green]\n")

    # Final summary
    if stats["total_files"] > 0:
        avg_size = stats["total_size_mb"] / stats["total_files"]
        console.print(
            f"[dim]Average entry size: {avg_size*1024:.2f} KB[/dim]"
        )

    console.print("\n")



def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Validate and inspect the Crossref cache with optional error export"
    )
    parser.add_argument(
        "-e", "--error",
        nargs="?",
        const="error.log",
        default=None,
        help="Export not found records to JSON file (default: error.log)"
    )
    parser.add_argument(
        "-f", "--failed",
        nargs="?",
        const="failed.log",
        default=None,
        help="Export invalid/failed records to JSON file (default: failed.log)"
    )
    parser.add_argument(
        "-r", "--random",
        action="store_true",
        help="Export a random cached record to stdout as JSON"
    )
    parser.add_argument(
        "-n", "--no-references",
        action="store_true",
        help="When used with -r, export a random record with no references"
    )

    args = parser.parse_args()
    console = Console()

    try:
        # If random mode, just get and print a random record
        if args.random:
            record = get_random_record(failed_only=args.no_references)
            if record:
                print(json.dumps(record, indent=2))
                return 0
            else:
                console.print("[yellow]No cached records found[/yellow]")
                return 1

        # Otherwise, run the normal validation
        stats, error_count = validate_cache(export_errors=args.error, export_failed=args.failed)
        display_stats(stats, export_path=args.error, export_failed_path=args.failed)

        # Exit with error code if there are issues
        if error_count > 0:
            return 1
        return 0

    except Exception as e:
        console.print(f"\n[red]Error during validation: {str(e)}[/red]\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
