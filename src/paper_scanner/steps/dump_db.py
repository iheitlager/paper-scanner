"""
Dump DB step for paper scanner

Prints database contents and index statistics for debugging and inspection.
"""

import sys
from typing import Any, Dict, List, Tuple

from rich.console import Console
from rich.table import Table

from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


class DumpDbStep(BaseStep):
    """Dump DB step that prints database contents and statistics."""

    @staticmethod
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
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute dump_db step - print database contents and index statistics.
        
        Args:
            config: Step configuration (unused)
            verbose: Enable verbose output (unused)
            dry_run: Dry run mode (unused)
            debug: Enable debug output
        
        Returns:
            Execution result with database statistics
        """
        
        all_papers = self.db.all(primary_only=False)
        
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
        
        stats_table.add_row("papers (all records)", str(len(self.db.papers)))
        stats_table.add_row("_doi_index (unique DOIs)", str(len(self.db._doi_index)))
        stats_table.add_row("_cite_key_index (unique keys)", str(len(self.db._cite_key_index)))
        stats_table.add_row("_id_index (unique IDs)", str(len(self.db._id_index)))
        
        console.print(stats_table)
        
        return {
            "status": "success",
            "records_printed": len(all_papers),
            "index_sizes": {
                "papers": len(self.db.papers),
                "_doi_index": len(self.db._doi_index),
                "_cite_key_index": len(self.db._cite_key_index),
                "_id_index": len(self.db._id_index),
            }
        }
