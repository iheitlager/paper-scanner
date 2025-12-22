"""
Dump DB step for paper scanner

Prints database contents and index statistics for debugging and inspection.
"""

import sys
from typing import Any, Dict, List, Tuple

from rich.console import Console
from rich.table import Table

from .base import BaseStep
from paper_scanner.core.enum import StepStatus

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
        errors: List[str] = []
        
        # Check that either 'papers' or 'citations' is provided
        has_papers = "papers" in config
        has_citations = "citations" in config
        
        if not has_papers and not has_citations:
            errors.append("Either 'papers' or 'citations' must be specified")

        return len(errors) == 0, errors

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
            config: Step configuration with optional:
                - papers: If present, print all papers
                - citations: If present, print all citations
            verbose: Enable verbose output (unused)
            dry_run: Dry run mode (unused)
            debug: Enable debug output
        
        Returns:
            Execution result with database statistics
        """

        if not verbose and not debug:
            return {"status": "skipped", "message": "verbose mode not enabled"}
        
        self.print_papers = "papers" in config
        self.print_citations = "citations" in config

        result = {}

        if self.print_papers:
            printed_papers = self._print_papers()
            result["printed_papers"] = printed_papers
        
        if self.print_citations:
            printed_citations = self._print_citations()
            result["printed_citations"] = printed_citations

        # Print index statistics
        stats_table = Table(show_header=True, header_style="bold", title="Index Statistics")
        stats_table.add_column("Index", style="cyan")
        stats_table.add_column("Size", style="yellow")

        stats_table.add_row("papers (all records)", str(self.db.count()))
        stats_table.add_row("_doi_index (unique DOIs)", str(len(self.db._doi_index)))
        stats_table.add_row("_cite_key_index (unique keys)", str(len(self.db._cite_key_index)))
        stats_table.add_row("_id_index (unique IDs)", str(len(self.db._id_index)))

        console.print(stats_table)

        result["index_sizes"] =  {
                "papers": len(self.db.papers),
                "_doi_index": len(self.db._doi_index),
                "_cite_key_index": len(self.db._cite_key_index),
                "_id_index": len(self.db._id_index),
            }

        result["status"] = StepStatus.SUCCESS
        return result


    def _print_papers(self) -> int:
        """
        Print all papers from the database in a formatted table.
        Retrieves all papers from the database (including duplicates) and displays them
        in a rich-formatted table with columns for DOI, Type, Title, and duplicate status.
        Titles longer than 60 characters are truncated with ellipsis. Missing values are
        displayed as em-dashes (—). Duplicate papers are marked with a '+' symbol.

        Returns:
            int: The total number of papers in the database.
        """
        # Display database records in a formatted table with paper details
        all_papers = self.db.all(primary_only=False)
                
        table = Table(show_header=True, header_style="bold", title="Database Records")
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

        return len(all_papers)

    def _print_citations(self) -> int:
        """
        Print all citations from all papers in the database in a formatted table.
        Retrieves all papers and iterates through their citations, displaying them
        in a rich-formatted table with columns for DOI, Authors, Title, Year, Journal,
        and resolution status. Titles longer than 40 characters are truncated with
        ellipsis. Missing values are displayed as em-dashes (—). Resolved citations
        are marked with a '+' symbol.
        
        Returns:
            int: The total number of citations across all papers.
        """
        all_papers = self.db.all(primary_only=False)
        
        table = Table(show_header=True, header_style="bold", title="All Citations")
        table.add_column("DOI", style="cyan", no_wrap=True)
        table.add_column("Year", style="blue", justify="center")
        table.add_column("R", style="red", justify="center", no_wrap=True)

        total_citations = 0
        
        for paper in all_papers:
            for citation in paper.citations:
                total_citations += 1
                
                doi_display = citation.doi if citation.doi else "—"
                
                # Format authors: "Smith, Jones" or "Smith et al."
                
                year_display = str(citation.year) if citation.year else "—"
                
                resolved = '+' if citation.resolved_paper is not None else ' '
                
                table.add_row(doi_display, year_display,resolved)

        console.print(table)
        console.print(f"Total citations: {total_citations}\n")

        return total_citations