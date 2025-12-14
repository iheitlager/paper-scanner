"""
Dump DB step for paper scanner

Prints database contents and index statistics for debugging and inspection.
"""

import sys
from typing import Dict, Any, List, Tuple
from rich.console import Console
from rich.table import Table

from ..core.database import PapersDatabase

# Initialize rich console
console = Console(file=sys.stderr)


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate dump_db step configuration.
    
    Args:
        config: Step configuration (no parameters required)
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    # dump_db has no required parameters
    return (True, [])


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute dump_db step - print database contents and index statistics.
    
    Args:
        config: Step configuration (unused)
        papers_db: Current papers database
        verbose: Enable verbose output (unused)
        dry_run: Dry run mode (unused)
    
    Returns:
        Execution result with database statistics
    """
    
    all_papers = papers_db.all(primary_only=False)
    
    # Print records table
    console.print("[bold blue]Database Records[/bold blue]")
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("DOI", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Title", style="green")
    table.add_column("D", style="red", justify="center", no_wrap=True)

    for paper in all_papers:
        doi_display = paper.doi if paper.doi else "—"
        type_display = paper.paper_type if paper.paper_type else "—"
        title = paper.title if paper.title else "—"
        title_display = title[:60] + "..." if len(title) > 60 else title
        duplicate = '+' if paper.duplicate_of is not None else ' '
        table.add_row(doi_display, type_display, title_display, duplicate)
    
    console.print(table)
    console.print(f"Total records: {len(all_papers)}\n")
    
    # Print index statistics
    console.print("[bold blue]Index Statistics[/bold blue]")
    
    stats_table = Table(show_header=True, header_style="bold")
    stats_table.add_column("Index", style="cyan")
    stats_table.add_column("Size", style="yellow")
    
    stats_table.add_row("papers (all records)", str(len(papers_db.papers)))
    stats_table.add_row("_doi_index (unique DOIs)", str(len(papers_db._doi_index)))
    stats_table.add_row("_cite_key_index (unique keys)", str(len(papers_db._cite_key_index)))
    stats_table.add_row("_id_index (unique IDs)", str(len(papers_db._id_index)))
    
    console.print(stats_table)
    
    return {
        "status": "success",
        "records_printed": len(all_papers),
        "index_sizes": {
            "papers": len(papers_db.papers),
            "_doi_index": len(papers_db._doi_index),
            "_cite_key_index": len(papers_db._cite_key_index),
            "_id_index": len(papers_db._id_index),
        }
    }
