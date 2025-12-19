"""
Database summary step for paper scanner

Outputs database statistics and relevant facts
"""
import sys
from typing import Dict, Any, List, Tuple
from collections import Counter
from rich.console import Console
from rich.table import Table

from ..core.models import Paper
from ..core.enum import ScreeningDecision
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


# Class-based step interface (new architecture)
class SummarizeStep(BaseStep):
    """Wrapper for summarize step (legacy function-based)."""
    
    @staticmethod
    def validate(config):
        """Delegate to module validate function."""

        errors = []
        
        # Check summary flag
        if "summary" in config and not isinstance(config["summary"], bool):
            errors.append("'summary' must be a boolean")
        
        # Check screening flag
        if "screening" in config and not isinstance(config["screening"], bool):
            errors.append("'screening' must be a boolean")
        
        # Check citations flag
        if "citations" in config and not isinstance(config["citations"], bool):
            errors.append("'citations' must be a boolean")

        # Check citations flag
        if "bibliography" in config and not isinstance(config["bibliography"], bool):
            errors.append("'bibliography' must be a boolean")

        # Check tabulate configuration
        if "tabulate" in config:
            tabulate = config["tabulate"]
            if isinstance(tabulate, dict):
                # Single tabulate config
                if "field" not in tabulate:
                    errors.append("'tabulate' dictionary must have 'field' key")
                elif not isinstance(tabulate["field"], str):
                    errors.append("'tabulate.field' must be a string")
                
                if "duplicates" in tabulate:
                    dup = tabulate["duplicates"]
                    if dup not in {False, True, "only"}:
                        errors.append(f"'tabulate.duplicates' must be False, True, or 'only', got {dup}")
            elif isinstance(tabulate, list):
                # Multiple tabulate configs
                for i, tab in enumerate(tabulate):
                    if not isinstance(tab, dict):
                        errors.append(f"'tabulate' list item {i} must be a dictionary")
                        continue
                    
                    if "field" not in tab:
                        errors.append(f"'tabulate' list item {i} must have 'field' key")
                    elif not isinstance(tab["field"], str):
                        errors.append(f"'tabulate' list item {i} 'field' must be a string")
                    
                    if "duplicates" in tab:
                        dup = tab["duplicates"]
                        if dup not in {False, True, "only"}:
                            errors.append(f"'tabulate' list item {i} 'duplicates' must be False, True, or 'only'")
            else:
                errors.append("'tabulate' must be a dictionary or list of dictionaries")
        
        return len(errors) == 0, errors

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        """
        Execute database summary step
        
        Args:
            config: Step configuration with options:
                - summary: bool (default: True) - Show summary statistics
                - screening: bool (default: False) - Show screening results
                - citations: bool (default: False) - Show citations histogram
                - table_by_paper_type: bool (default: False) - DEPRECATED: Use tabulate instead
                - tabulate: dict or list of dicts with options:
                    - field: str - Field to tabulate (e.g., 'paper_type', 'journal', 'booktitle')
                    - duplicates: bool/str (default: False) - Include duplicates (False, True, or 'only')
            papers_db: Current papers database
            verbose: Enable verbose output
            dry_run: Don't actually process, just show what would happen
        
        Returns:
            Dictionary with database statistics
        """
        
        # Get configuration options
        show_summary = config.get("summary", False)
        show_screening = config.get("screening", False)
        show_citations = config.get("citations", False)
        show_bibliography = config.get("bibliography", False)        

        # Support both old and new configuration format
        tabulate_configs = []
        
        # Check for new tabulate format (dict or list)
        if "tabulate" in config:
            tabulate_config = config["tabulate"]
            if isinstance(tabulate_config, dict):
                tabulate_configs = [tabulate_config]
            elif isinstance(tabulate_config, list):
                tabulate_configs = tabulate_config
        
        # Fallback to deprecated table_by_paper_type for backward compatibility
        if not tabulate_configs and config.get("table_by_paper_type", False):
            tabulate_configs = [{"field": "paper_type", "duplicates": False}]
        
        results = {
            "step": "database_summary",
            "timestamp": None,
            "statistics": {},
            "tables": {}
        }
        
        if self.db.count(primary_only=False) == 0:
            results["statistics"] = {
                "total_papers": 0,
                "message": "No papers in database"
            }
            if verbose:
                console.print("\n  [yellow]Database Summary:[/yellow]")
                console.print("    [red]No papers in database yet[/red]")
            return results
        
        # Basic statistics
        total = self.db.count(primary_only=False)
        
        # Authors statistics
        all_authors = []
        for paper in self.db.to_list(primary_only=False):
            all_authors.extend(paper.authors)
        
        unique_authors = len(set(a.full_name for a in all_authors))
        
        # Years
        years_with_papers = [p.year for p in self.db.to_list(primary_only=False) if p.year]
        year_range = f"{min(years_with_papers)}-{max(years_with_papers)}" if years_with_papers else "N/A"
        
        # Identifiers
        with_doi = sum(1 for p in self.db.to_list(primary_only=False) if p.doi)
        with_abstract = sum(1 for p in self.db.to_list(primary_only=False) if p.abstract)
        
        # Keywords
        all_keywords = []
        for paper in self.db.to_list(primary_only=False):
            all_keywords.extend(paper.keywords)
        unique_keywords = len(set(all_keywords))
        
        # Sources
        sources = Counter()
        for paper in self.db.to_list(primary_only=False):
            if paper.discovery and paper.discovery.source_database:
                sources[paper.discovery.source_database] += 1
        
        # Screening status
        screening_status = Counter()
        for paper in self.db.to_list(primary_only=False):
            screening_status[paper.screening.final_decision.value] += 1
        
        # Duplicates
        unique_papers = sum(1 for p in self.db.to_list(primary_only=False) if p.duplicate_of is None)
        duplicate_papers = sum(1 for p in self.db.to_list(primary_only=False) if p.duplicate_of is not None)
        
        # Paper types (from paper.paper_type field, not screening)
        paper_types = Counter()
        for paper in self.db.to_list(primary_only=False):
            if paper.paper_type:
                paper_types[paper.paper_type] += 1
        
        results["statistics"] = {
            "total_papers": total,
            "unique_papers": unique_papers,
            "duplicate_papers": duplicate_papers,
            "total_authors": len(all_authors),
            "unique_authors": unique_authors,
            "year_range": year_range,
            "papers_with_doi": with_doi,
            "papers_with_abstract": with_abstract,
            "papers_with_keywords": sum(1 for p in self.db.to_list(primary_only=False) if p.keywords),
            "unique_keywords": unique_keywords,
            "sources": dict(sources),
            "screening_status": dict((k, v) for k, v in screening_status.items()),
            "paper_types": dict(paper_types) if paper_types else None,
        }
        
        if verbose and show_summary:
            console.print("\n  [bold yellow]Database Summary:[/bold yellow]")
            console.print(f"    Total papers: [cyan]{total}[/cyan]")
            console.print(f"    Unique papers: [green]{unique_papers}[/green]")
            console.print(f"    Duplicate papers: [red]{duplicate_papers}[/red]")
            console.print(f"    Total authors: [cyan]{len(all_authors)}[/cyan]")
            console.print(f"    Unique authors: [green]{unique_authors}[/green]")
            console.print(f"    Year range: [cyan]{year_range}[/cyan]")
            console.print(f"    Papers with DOI: [cyan]{with_doi}[/cyan]")
            console.print(f"    Papers with abstract: [cyan]{with_abstract}[/cyan]")
            console.print(f"    Unique keywords: [cyan]{unique_keywords}[/cyan]")
        
        # Generate tables if requested
        if verbose and tabulate_configs:
            for tab_config in tabulate_configs:
                field = tab_config.get("field")
                duplicates = tab_config.get("duplicates", False)
                
                if not field:
                    continue
                
                # Filter papers based on duplicates setting
                all_papers = self.db.to_list(primary_only=False)
                papers_to_tabulate = _filter_by_duplicates(all_papers, duplicates)
                
                # Generate table for this field
                table_data = _generate_field_table(papers_to_tabulate, field, self.db.count(primary_only=False))
                if table_data:
                    console.print(f"\n  [bold yellow]Papers by {field.title()}:[/bold yellow]")
                    console.print(table_data)
                    results["tables"][field] = "generated"
        
        # Display screening results if requested
        if verbose and show_screening:
            _display_screening_results(self.db.to_list(primary_only=False))
        
        # Display citations histogram if requested
        if verbose and show_citations:
            _display_citations_histogram(self.db.to_list(primary_only=False))

        if verbose and show_bibliography:
            _display_bibliography(self.db.to_list(primary_only=False))
        

        results["status"] = "ok"
        return results


def _filter_by_duplicates(papers: List[Paper], duplicates: Any) -> List[Paper]:
    """
    Filter papers based on duplicates setting
    
    Args:
        papers: List of papers
        duplicates: False (exclude), True (include all), 'only' (only duplicates)
    
    Returns:
        Filtered list of papers
    """
    if duplicates == "only":
        return [p for p in papers if p.duplicate_of is not None]
    elif duplicates is True:
        return papers
    else:  # False or default
        return [p for p in papers if p.duplicate_of is None]


def _generate_field_table(papers_db: List[Paper], field: str, total_papers: int) -> Table:
    """
    Generate a table of papers grouped by a specified field
    
    Args:
        papers_db: List of papers to tabulate
        field: Field name to group by (e.g., 'paper_type', 'journal', 'booktitle')
        total_papers: Total papers in database (for percentage calculation)
    
    Returns:
        Rich Table with field statistics
    """
    
    # Group papers by field value
    papers_by_field = {}
    no_field = []
    
    for paper in papers_db:
        value = getattr(paper, field, None)
        
        if value:
            # Handle list fields
            if isinstance(value, list):
                value_str = f"{len(value)} items"
            else:
                value_str = str(value)
            
            if value_str not in papers_by_field:
                papers_by_field[value_str] = []
            papers_by_field[value_str].append(paper)
        else:
            no_field.append(paper)
    
    # Create table
    table = Table(title=f"Paper Statistics by {field.title()}")
    table.add_column(field.title(), style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("% of Total", justify="right", style="yellow")
    table.add_column("With DOI", justify="right", style="blue")
    table.add_column("With Abstract", justify="right", style="magenta")
    
    # Add rows for each field value
    for field_value in sorted(papers_by_field.keys()):
        papers = papers_by_field[field_value]
        count = len(papers)
        percentage = (count / total_papers * 100) if total_papers > 0 else 0
        with_doi = sum(1 for p in papers if p.doi)
        with_abstract = sum(1 for p in papers if p.abstract)
        
        table.add_row(
            field_value[:30],  # Truncate long values
            str(count),
            f"{percentage:.1f}%",
            str(with_doi),
            str(with_abstract)
        )
    
    # Add row for papers without field
    if no_field:
        count = len(no_field)
        percentage = (count / total_papers * 100) if total_papers > 0 else 0
        with_doi = sum(1 for p in no_field if p.doi)
        with_abstract = sum(1 for p in no_field if p.abstract)
        
        table.add_row(
            f"[dim]No {field.title()}[/dim]",
            str(count),
            f"{percentage:.1f}%",
            str(with_doi),
            str(with_abstract)
        )
    
    # Add total row
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{len(papers_db)}[/bold]",
        "[bold]100.0%[/bold]",
        f"[bold]{sum(1 for p in papers_db if p.doi)}[/bold]",
        f"[bold]{sum(1 for p in papers_db if p.abstract)}[/bold]"
    )
    
    return table


def _display_screening_results(papers_db: List[Paper]) -> None:
    """
    Display screening results breakdown by paper_type with stage progression
    
    Args:
        papers_db: List of papers to analyze
    """
    if not papers_db:
        console.print("\n  [red]No papers to display screening results[/red]")
        return
    
    # Separate primary papers from duplicates
    primary_papers = [p for p in papers_db if p.duplicate_of is None]
    duplicate_papers = [p for p in papers_db if p.duplicate_of is not None]
    
    # Group primary papers by paper_type and track through screening stages
    papers_by_type = {}
    
    for paper in primary_papers:
        paper_type = paper.paper_type or "Unknown"
        
        if paper_type not in papers_by_type:
            papers_by_type[paper_type] = {
                "total": 0,
                "categorization_excluded": 0,
                "keyword_excluded": 0,
                "semantic_excluded": 0,
                "manual_review": 0,
                "included": 0,
            }
        
        papers_by_type[paper_type]["total"] += 1
        
        # Track through screening stages
        final_decision = paper.screening.final_decision.value
        
        # Check categorization exclusion
        if paper.screening.categorization and not paper.screening.categorization.is_peer_reviewed:
            papers_by_type[paper_type]["categorization_excluded"] += 1
        # Check keyword screening exclusion
        elif paper.screening.keyword_screening and not paper.screening.keyword_screening.passed:
            papers_by_type[paper_type]["keyword_excluded"] += 1
        # Check semantic screening exclusion
        elif paper.screening.semantic_screening and not paper.screening.semantic_screening.passed:
            papers_by_type[paper_type]["semantic_excluded"] += 1
        # Check manual review flag
        elif final_decision == ScreeningDecision.MANUAL_REVIEW.value:
            papers_by_type[paper_type]["manual_review"] += 1
        # Included
        elif final_decision == ScreeningDecision.INCLUDED.value:
            papers_by_type[paper_type]["included"] += 1
    
    # Create comprehensive table
    table = Table(title="Screening Results Progression")
    table.add_column("Paper Type", style="cyan", width=18)
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Categorization\nExcluded", justify="right", style="yellow")
    table.add_column("Keyword\nExcluded", justify="right", style="yellow")
    table.add_column("Semantic\nExcluded", justify="right", style="yellow")
    table.add_column("Manual\nReview", justify="right", style="blue")
    table.add_column("Included", justify="right", style="green")
    
    # Totals tracking
    total_primary = 0
    total_cat_excl = 0
    total_kw_excl = 0
    total_sem_excl = 0
    total_manual = 0
    total_included = 0
    
    # Add rows for each paper type
    for paper_type in sorted(papers_by_type.keys()):
        counts = papers_by_type[paper_type]
        
        total_primary += counts["total"]
        total_cat_excl += counts["categorization_excluded"]
        total_kw_excl += counts["keyword_excluded"]
        total_sem_excl += counts["semantic_excluded"]
        total_manual += counts["manual_review"]
        total_included += counts["included"]
        
        table.add_row(
            paper_type,
            str(counts["total"]),
            str(counts["categorization_excluded"]),
            str(counts["keyword_excluded"]),
            str(counts["semantic_excluded"]),
            str(counts["manual_review"]),
            str(counts["included"]),
        )
    
    # Add duplicates row if any exist
    if duplicate_papers:
        table.add_row(
            "[dim]Duplicates[/dim]",
            f"[dim]{len(duplicate_papers)}[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
        )
    
    # Add total row (only counting primary papers in screening totals)
    total_all = total_primary + len(duplicate_papers)
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_all}[/bold]",
        f"[bold yellow]{total_cat_excl}[/bold yellow]",
        f"[bold yellow]{total_kw_excl}[/bold yellow]",
        f"[bold yellow]{total_sem_excl}[/bold yellow]",
        f"[bold blue]{total_manual}[/bold blue]",
        f"[bold green]{total_included}[/bold green]",
    )
    
    console.print(table)
    
    # Print summary statistics
    total_excluded = total_cat_excl + total_kw_excl + total_sem_excl
    inclusion_rate = (total_included / total_primary * 100) if total_primary > 0 else 0
    
    console.print(f"\n  [dim]Total excluded: {total_excluded} ({total_excluded/total_primary*100:.1f}%)[/dim]" if total_primary > 0 else f"\n  [dim]Total excluded: {total_excluded}[/dim]")
    console.print(f"  [dim]Inclusion rate: {total_included}/{total_primary} ({inclusion_rate:.1f}%)[/dim]" if total_primary > 0 else f"  [dim]Inclusion rate: {total_included}/0[/dim]")
    if duplicate_papers:
        console.print(f"  [dim]Duplicate records: {len(duplicate_papers)}[/dim]")


def _display_citations_histogram(papers_db: List[Paper]) -> None:
    """
    Display a histogram of citation counts ordered by number of citations (descending)
    
    Shows how many papers have each citation count, ordered from most cited to least.
    
    Args:
        papers_db: List of papers to analyze
    """
    if not papers_db:
        console.print("\n  [red]No papers to display citation statistics[/red]")
        return
    
    # Filter to primary papers only
    primary_papers = [p for p in papers_db if p.duplicate_of is None]
    
    if not primary_papers:
        console.print("\n  [red]No primary papers to analyze[/red]")
        return
    
    # Count papers by citation count
    citation_counts = {}
    for paper in primary_papers:
        # Count the number of citations (citations is a list)
        citations = len(paper.cited_by_papers) if paper.cited_by_papers else 0
        if citations not in citation_counts:
            citation_counts[citations] = 0
        citation_counts[citations] += 1
    
    # Sort by citation count (descending)
    sorted_counts = sorted(citation_counts.items(), key=lambda x: x[0], reverse=True)
    
    # Create table
    table = Table(title="Citation Distribution")
    table.add_column("Citations", style="cyan", justify="right")
    table.add_column("Number of Papers", style="green", justify="right")
    table.add_column("Percentage", style="yellow", justify="right")
    table.add_column("Visual", style="blue")
    
    total_papers = len(primary_papers)
    max_count = max(count for _, count in sorted_counts) if sorted_counts else 1
    
    # Add rows
    for citations, count in sorted_counts:
        percentage = (count / total_papers * 100) if total_papers > 0 else 0
        bar_width = int((count / max_count) * 30) if max_count > 0 else 0
        bar = "█" * bar_width
        
        table.add_row(
            str(citations),
            str(count),
            f"{percentage:.1f}%",
            bar
        )
    
    console.print(table)
    
    # Print summary stats
    total_citations = sum(cit * count for cit, count in sorted_counts)
    avg_citations = (total_citations / total_papers) if total_papers > 0 else 0
    max_citations = max(cit for cit, _ in sorted_counts) if sorted_counts else 0
    
    console.print(f"\n  [dim]Total citations: {total_citations}[/dim]")
    console.print(f"  [dim]Average citations per paper: {avg_citations:.2f}[/dim]")
    console.print(f"  [dim]Maximum citations: {max_citations}[/dim]")


def _display_bibliography(papers_db: List[Paper]) -> None:
    """
    Display a histogram of citation counts ordered by number of citations (descending)
    
    Shows how many papers have each citation count, ordered from most cited to least.
    
    Args:
        papers_db: List of papers to analyze
    """
    if not papers_db:
        console.print("\n  [red]No papers to display citation statistics[/red]")
        return
    
    # Filter to primary papers only
    primary_papers = [p for p in papers_db if p.duplicate_of is None]
    
    if not primary_papers:
        console.print("\n  [red]No primary papers to analyze[/red]")
        return
    
    # Count papers by citation count
    keywords = 0
    abstracts = 0
    keyword_abstracts = 0
    for paper in primary_papers:
        if paper.keywords:
            keywords += 1
        if paper.abstract:
            abstracts += 1
        if paper.keywords and paper.abstract:
            keyword_abstracts += 1

    
    # Create table
    table = Table(title="Citation Distribution")
    table.add_column("Papers", style="cyan", justify="right")
    table.add_column("With Keywords", style="green", justify="right")
    table.add_column("With Abstract", style="yellow", justify="right")
    table.add_column("With Both", style="blue")
    
    table.add_row(
        str(len(primary_papers)),
        str(keywords),
        str(abstracts),
        str(keyword_abstracts)
    )
    console.print(table)