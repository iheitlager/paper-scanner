"""
Database summary step for paper scanner

Outputs database statistics and relevant facts
"""
import sys
from collections import Counter
from typing import Any, List, Dict, TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.step_result import StepResult
from paper_scanner.core.database import PapersDatabase
from ..core.enum import ScreeningDecision
from ..core.models import Paper
from .base import BaseStep

if TYPE_CHECKING:
    from paper_scanner.core.step_executor import StepExecutor


# Initialize rich console
console = Console(file=sys.stderr)


# Class-based step interface (new architecture)
class ReportStep(BaseStep):
    """Wrapper for report step (legacy function-based)."""
    _report_types = {
        "summary": None,
        "source": None,
        "screening": None,
        "citations": None,
        "bibliography": None,
        "histogram": None,
        "debug": None,
        # "tabulate": None,
    }

    @classmethod
    def report_types(cls) -> List[str]:
        return list(cls._report_types.keys())

    @staticmethod
    def validate(config):
        """Delegate to module validate function."""

        errors = []

        for key in config:
            if key in ReportStep._report_types:
                if not isinstance(config[key], bool):
                    errors.append(f"'{key}' must be a boolean")
            elif key == "tabulate":
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
            else:
                errors.append(f"Unknown report key: '{key}'")

        return len(errors) == 0, errors

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        """
        Execute database report step

        Args:
            config: Step configuration with options:
                - summary: bool (default: True) - Show summary statistics
                - screening: bool (default: False) - Show screening results
                - citations: bool (default: False) - Show citations histogram
                - table_by_paper_type: bool (default: False) - DEPRECATED: Use tabulate instead
                - tabulate: dict or list of dicts with options:
                    - field: str - Field to tabulate (e.g., 'paper_type', 'journal', 'booktitle')
                    - duplicates: bool/str (default: False) - Include duplicates (False, True, or 'only')
            verbose: Enable verbose output
            dry_run: Don't actually process, just show what would happen
            debug: Enable debug output

        Returns:
            Dictionary with database statistics
        """
        if self.db.count(primary_only=False) == 0:
            self.callback("[yellow]No papers in database yet[/yellow]")
            return StepResult(
                status=StepStatus.SUCCESS
            )


        # Get configuration options
        show_summary = config.get("summary", False)
        show_screening = config.get("screening", False)
        show_citations = config.get("citations", False)
        show_bibliography = config.get("bibliography", False)
        show_histogram = config.get("histogram", False)
        show_source = config.get("source", False)
        show_debug = config.get("debug", False)
        show_dump_citations = config.get("dump_citations", False)

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

        reports = []


        # Display summary statistics if requested
        if verbose and show_summary:
            reports.append("summary")
            _display_summary_results(self.db)

        # Display screening results if requested
        if verbose and show_screening:
            reports.append("screening")
            _display_screening_results(self.db)

        # Display screening results if requested
        if verbose and show_source:
            reports.append("source")
            _display_source_results(self.db)

        # Display citations histogram if requested
        if verbose and show_citations:
            reports.append("citations")
            _display_citations_histogram(self.db)

        if verbose and show_bibliography:
            reports.append("bibliography")
            _display_bibliography(self.db)

        if verbose and show_histogram:
            reports.append("histogram")
            _display_histogram(self.db)

        if verbose and show_debug:
            reports.append("debug")
            _display_debug_info(self.db)

        if verbose and tabulate_configs:
            reports.append("tabulate")
            _display_tabulate_results(self.db, tabulate_configs)


        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Database summary completed. Reports generated: {', '.join(reports)}",
        )


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

def _display_summary_results(db: PapersDatabase) -> None:
    """
    Display summary statistics of the papers database
    
    Args:
        papers_db: List of papers to analyze
    """
    # Basic statistics
    total = len(db)

    # Authors statistics
    all_authors = []
    for paper in db.to_list(primary_only=False):
        all_authors.extend(paper.authors)

    unique_authors = len(set(a.full_name for a in all_authors))

    # Years
    years_with_papers = [p.year for p in db.to_list(primary_only=False) if p.year]
    year_range = f"{min(years_with_papers)}-{max(years_with_papers)}" if years_with_papers else "N/A"

    # Identifiers
    with_doi = sum(1 for p in db.to_list(primary_only=False) if p.doi)
    with_abstract = sum(1 for p in db.to_list(primary_only=False) if p.abstract)

    # Keywords
    all_keywords = []
    for paper in db.to_list(primary_only=False):
        all_keywords.extend(paper.keywords)
    unique_keywords = len(set(all_keywords))

    # Sources
    sources = Counter()
    for paper in db.to_list(primary_only=False):
        if paper.discovery and paper.discovery.source_database:
            sources[paper.discovery.source_database] += 1

    # Screening status
    screening_status = Counter()
    for paper in db.to_list(primary_only=False):
        screening_status[paper.screening.final_decision.value] += 1

    # Duplicates
    unique_papers = sum(1 for p in db.to_list(primary_only=False) if p.duplicate_of is None)
    duplicate_papers = sum(1 for p in db.to_list(primary_only=False) if p.duplicate_of is not None)

    # Paper types (from paper.paper_type field, not screening)
    paper_types = Counter()
    for paper in db.to_list(primary_only=False):
        if paper.paper_type:
            paper_types[paper.paper_type] += 1

    console.print("\n[bold yellow]Database Summary:[/bold yellow]")
    console.print(f"    Total papers: [cyan]{total}[/cyan]")
    console.print(f"    Unique papers: [green]{unique_papers}[/green]")
    console.print(f"    Duplicate papers: [red]{duplicate_papers}[/red]")
    console.print(f"    Total authors: [cyan]{len(all_authors)}[/cyan]")
    console.print(f"    Unique authors: [green]{unique_authors}[/green]")
    console.print(f"    Year range: [cyan]{year_range}[/cyan]")
    console.print(f"    Papers with DOI: [cyan]{with_doi}[/cyan]")
    console.print(f"    Papers with abstract: [cyan]{with_abstract}[/cyan]")
    console.print(f"    Unique keywords: [cyan]{unique_keywords}[/cyan]")

def _display_tabulate_results(db: PapersDatabase, config: Dict[str, Any]) -> None:
    """
    Display tabulated results based on configuration
    Args:
        papers_db: List of papers to analyze
        config: Tabulate configuration dictionary
    
    Returns:

    """

    # Generate tables if requested
    for tab_config in config:
        field = tab_config.get("field")
        duplicates = tab_config.get("duplicates", False)

        if not field:
            continue

        # Filter papers based on duplicates setting
        papers_to_tabulate = _filter_by_duplicates(db, duplicates)

        # Generate table for this field
        table_data = _generate_field_table(papers_to_tabulate, field, db)
        if table_data:
            console.print(f"\n  [bold yellow]Papers by {field.title()}:[/bold yellow]")
            console.print(table_data)


def _display_screening_results(db: PapersDatabase) -> None:
    """
    Display screening results breakdown by paper_type with stage progression
    
    Args:
        db: PapersDatabase instance to analyze
    """

    # Separate primary papers from duplicates
    primary_papers = [p for p in db.to_list(primary_only=False) if p.duplicate_of is None]
    duplicate_papers = [p for p in db.to_list(primary_only=False) if p.duplicate_of is not None]

    # Group primary papers by paper_type and track through screening stages
    papers_by_type = {}

    for paper in primary_papers:
        paper_type = paper.paper_type or "Unknown"

        if paper_type not in papers_by_type:
            papers_by_type[paper_type] = {
                "total": 0,
                "metadata_excluded": 0,
                "keyword_excluded": 0,
                "semantic_excluded": 0,
                "uncertain": 0,
                "manual_review": 0,
                "included": 0,
            }

        papers_by_type[paper_type]["total"] += 1

        # Track through screening stages
        final_decision = paper.screening.final_decision

        # Check metadata exclusion
        if paper.screening.metadata_screening and not paper.screening.metadata_screening.passed:
            papers_by_type[paper_type]["metadata_excluded"] += 1
        # Check keyword screening exclusion
        if paper.screening.keyword_screening and not paper.screening.keyword_screening.passed:
            papers_by_type[paper_type]["keyword_excluded"] += 1
        # Check semantic screening exclusion
        if paper.screening.semantic_screening and not paper.screening.semantic_screening.passed:
            papers_by_type[paper_type]["semantic_excluded"] += 1
        if final_decision == ScreeningDecision.UNCERTAIN:
            papers_by_type[paper_type]["uncertain"] += 1
        # Check manual review flag
        elif final_decision == ScreeningDecision.MANUAL_REVIEW:
            papers_by_type[paper_type]["manual_review"] += 1
        elif paper.is_included:
            papers_by_type[paper_type]["included"] += 1

    # Create comprehensive table
    table = Table(title="Screening Results Progression")
    table.add_column("Paper Type", style="cyan", width=18)
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Metadata\nExcluded", justify="right", style="yellow")
    table.add_column("Keyword\nExcluded", justify="right", style="yellow")
    table.add_column("Semantic\nExcluded", justify="right", style="yellow")
    table.add_column("Uncertain", justify="right", style="yellow")
    table.add_column("Manual\nReview", justify="right", style="blue")
    table.add_column("Included", justify="right", style="green")

    # Totals tracking
    total_primary = 0
    total_metadata_excl = 0
    total_kw_excl = 0
    total_sem_excl = 0
    total_uncertain = 0
    total_manual = 0
    total_included = 0

    # Add rows for each paper type
    for paper_type in sorted(papers_by_type.keys()):
        counts = papers_by_type[paper_type]

        total_primary += counts["total"]
        total_metadata_excl += counts["metadata_excluded"]
        total_kw_excl += counts["keyword_excluded"]
        total_sem_excl += counts["semantic_excluded"]
        total_uncertain += counts["uncertain"]
        total_manual += counts["manual_review"]
        total_included += counts["included"]

        table.add_row(
            paper_type,
            str(counts["total"]),
            str(counts["metadata_excluded"]),
            str(counts["keyword_excluded"]),
            str(counts["semantic_excluded"]),
            str(counts["uncertain"]),
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
        f"[bold yellow]{total_metadata_excl}[/bold yellow]",
        f"[bold yellow]{total_kw_excl}[/bold yellow]",
        f"[bold yellow]{total_sem_excl}[/bold yellow]",
        f"[bold yellow]{total_uncertain}[/bold yellow]",
        f"[bold blue]{total_manual}[/bold blue]",
        f"[bold green]{total_included}[/bold green]",
    )

    console.print(table)

    # Print summary statistics
    total_excluded = total_metadata_excl + total_kw_excl + total_sem_excl
    inclusion_rate = (total_included / total_primary * 100) if total_primary > 0 else 0

    console.print(f"\n  [dim]Total excluded: {total_excluded} ({total_excluded/total_primary*100:.1f}%)[/dim]" if total_primary > 0 else f"\n  [dim]Total excluded: {total_excluded}[/dim]")
    console.print(f"  [dim]Inclusion rate: {total_included}/{total_primary} ({inclusion_rate:.1f}%)[/dim]" if total_primary > 0 else f"  [dim]Inclusion rate: {total_included}/0[/dim]")
    if duplicate_papers:
        console.print(f"  [dim]Duplicate records: {len(duplicate_papers)}[/dim]")


def _display_source_results(db: PapersDatabase) -> None:
    """
    Display results breakdown by source_database  with stage progression
    
    Args:
        db: PapersDatabase instance to analyze
    """

    # Separate primary papers from duplicates
    primary_papers = db.to_list(primary_only=True)
    duplicate_papers = [p for p in db.to_list(primary_only=False) if p.is_duplicate]

    # Group primary papers by paper_type and track through screening stages
    papers_by_type = {}

    for paper in primary_papers:
        source_type = paper.discovery.source_database or "Unknown"
        
        if source_type not in papers_by_type:
            papers_by_type[source_type] = {
                "total": 0,
                "metadata_excluded": 0,
                "keyword_excluded": 0,
                "semantic_excluded": 0,
                "uncertain": 0,
                "manual_review": 0,
                "included": 0,
                "keyword_detail_included": 0,
                "keyword_detail_excluded": 0,
                "keyword_detail_manual": 0,
            }

        papers_by_type[source_type]["total"] += 1

        # Track through screening stages
        final_decision = paper.screening.final_decision

        # Check metadata exclusion
        if paper.screening.metadata_screening and not paper.screening.metadata_screening.passed:
            papers_by_type[source_type]["metadata_excluded"] += 1
        # Check keyword screening exclusion
        if paper.screening.keyword_screening and not paper.screening.keyword_screening.passed:
            papers_by_type[source_type]["keyword_excluded"] += 1
        # Check semantic screening exclusion
        if paper.screening.semantic_screening and not paper.screening.semantic_screening.passed:
            papers_by_type[source_type]["semantic_excluded"] += 1
        if final_decision == ScreeningDecision.UNCERTAIN:
            papers_by_type[source_type]["uncertain"] += 1
        # Check manual review flag
        elif final_decision == ScreeningDecision.MANUAL_REVIEW:
            papers_by_type[source_type]["manual_review"] += 1
        # Included
        elif paper.is_included:
            papers_by_type[source_type]["included"] += 1

        # Keyword screening detail
        if paper.screening.keyword_screening:
            if paper.screening.keyword_screening.screening_decision == ScreeningDecision.INCLUDED:
                papers_by_type[source_type]["keyword_detail_included"] += 1
            elif paper.screening.keyword_screening.screening_decision == ScreeningDecision.EXCLUDED:
                papers_by_type[source_type]["keyword_detail_excluded"] += 1
            elif paper.screening.keyword_screening.screening_decision == ScreeningDecision.MANUAL_REVIEW:
                papers_by_type[source_type]["keyword_detail_manual"] += 1


    # Create comprehensive table
    table = Table(title="Screening Results Progression")
    table.add_column("Paper Type", style="cyan", width=18)
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Metadata\nExcluded", justify="right", style="yellow")
    table.add_column("Keyword\nExcluded", justify="right", style="yellow")
    table.add_column("Keyword\nDetail\nIncluded", justify="right", style="blue")
    table.add_column("Keyword\nDetail\nExcluded", justify="right", style="blue")
    table.add_column("Keyword\nDetail\nManual", justify="right", style="blue")
    table.add_column("Semantic\nExcluded", justify="right", style="yellow")
    table.add_column("Uncertain", justify="right", style="yellow")
    table.add_column("Manual\nReview", justify="right", style="blue")
    table.add_column("Included", justify="right", style="green")

    # Totals tracking
    total_primary = 0
    total_metadata_excl = 0
    total_kw_excl = 0
    total_kw_detail_incl = 0
    total_kw_detail_excl = 0
    total_kw_detail_manual = 0
    total_sem_excl = 0
    total_uncertain = 0
    total_manual = 0
    total_included = 0

    # Add rows for each paper type
    for paper_type in sorted(papers_by_type.keys()):
        counts = papers_by_type[paper_type]

        total_primary += counts["total"]
        total_metadata_excl += counts["metadata_excluded"]
        total_kw_excl += counts["keyword_excluded"]
        total_kw_detail_incl += counts["keyword_detail_included"]
        total_kw_detail_excl += counts["keyword_detail_excluded"]
        total_kw_detail_manual += counts["keyword_detail_manual"]
        total_sem_excl += counts["semantic_excluded"]
        total_uncertain += counts["uncertain"]
        total_manual += counts["manual_review"]
        total_included += counts["included"]

        table.add_row(
            paper_type,
            str(counts["total"]),
            str(counts["metadata_excluded"]),
            str(counts["keyword_excluded"]),
            str(counts["keyword_detail_included"]),
            str(counts["keyword_detail_excluded"]),
            str(counts["keyword_detail_manual"]),
            str(counts["semantic_excluded"]),
            str(counts["uncertain"]),
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
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
        )

    # Add total row (only counting primary papers in screening totals)
    total_all = total_primary + len(duplicate_papers)
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_all}[/bold]",
        f"[bold yellow]{total_metadata_excl}[/bold yellow]",
        f"[bold yellow]{total_kw_excl}[/bold yellow]",
        f"[bold blue]{total_kw_detail_incl}[/bold blue]",
        f"[bold blue]{total_kw_detail_excl}[/bold blue]",
        f"[bold blue]{total_kw_detail_manual}[/bold blue]",
        f"[bold yellow]{total_sem_excl}[/bold yellow]",
        f"[bold yellow]{total_uncertain}[/bold yellow]",
        f"[bold blue]{total_manual}[/bold blue]",
        f"[bold green]{total_included}[/bold green]",
    )

    console.print(table)

    # Print summary statistics
    total_excluded = total_metadata_excl + total_kw_excl + total_sem_excl
    inclusion_rate = (total_included / total_primary * 100) if total_primary > 0 else 0

    console.print(f"\n  [dim]Total excluded: {total_excluded} ({total_excluded/total_primary*100:.1f}%)[/dim]" if total_primary > 0 else f"\n  [dim]Total excluded: {total_excluded}[/dim]")
    console.print(f"  [dim]Inclusion rate: {total_included}/{total_primary} ({inclusion_rate:.1f}%)[/dim]" if total_primary > 0 else f"  [dim]Inclusion rate: {total_included}/0[/dim]")
    if duplicate_papers:
        console.print(f"  [dim]Duplicate records: {len(duplicate_papers)}[/dim]")

def _display_debug_info(db: PapersDatabase) -> None:
    """
    Display results breakdown by source_database  with stage progression
    
    Args:
        db: PapersDatabase instance to analyze
    """

    # Separate primary papers from duplicates
    primary_papers = db.to_list(primary_only=True)
    duplicate_papers = [p for p in db.to_list(primary_only=False) if p.is_duplicate]

    # Group primary papers by paper_type and track through screening stages
    papers_by_type = {}

    for paper in primary_papers:
        source_type = paper.discovery.source_database or "Unknown"
        
        if source_type not in papers_by_type:
            papers_by_type[source_type] = {
                "total": 0,
            }


        papers_by_type[source_type]["total"] += 1

        # Keyword screening detail
        if paper.screening.keyword_screening:
            papers_by_type[source_type][paper.screening.keyword_screening.screening_decision] = papers_by_type[source_type].get(paper.screening.keyword_screening.screening_decision, 0) + 1


    screening_decisions = set()
    for decision in papers_by_type.values():
        screening_decisions.update(decision.keys())

    screening_decisions.discard("total")
    screening_decisions = sorted(screening_decisions, key=lambda x: x.value)

    totals = {decision: 0 for decision in screening_decisions}
    totals["total"] = 0

    # Create comprehensive table
    table = Table(title="Screening Results Progression")
    table.add_column("Paper Type", style="cyan", width=18)
    table.add_column("Total", justify="right", style="bold")
    for decision in screening_decisions:
        table.add_column(f"{decision.name.replace('_', ' ')}", justify="right", style="yellow")

    # Add rows for each paper type
    for paper_type in sorted(papers_by_type.keys()):
        counts = papers_by_type[paper_type]
        totals["total"] += counts["total"]
        for decision in screening_decisions:
            totals[decision] += counts.get(decision, 0)

        table.add_row(
            paper_type,
            str(counts["total"]),
            *[str(counts.get(decision, 0)) for decision in screening_decisions],
        )

    # Add duplicates row if any exist
    if duplicate_papers:
        table.add_row(
            "[dim]Duplicates[/dim]",
            f"[dim]{len(duplicate_papers)}[/dim]",
            *["[dim]-[/dim]" for _ in screening_decisions],
        )

    # Add total row (only counting primary papers in screening totals)
    total_all = totals['total'] + len(duplicate_papers)
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_all}[/bold]",
        *[f"[bold yellow]{totals[decision]}[/bold yellow]" for decision in screening_decisions]
    )

    console.print(table)

def _display_citations_histogram(db: PapersDatabase) -> None:
    """
    Display a histogram of citation counts ordered by number of citations (descending)
    
    Shows how many papers have each citation count, ordered from most cited to least.
    
    Args:
        papers_db: List of papers to analyze
    """
    # Filter to primary papers only
    primary_papers = db.to_list(primary_only=True)


    # Print index statistics
    stats_table = Table(show_header=True, header_style="bold", title="Index Statistics")
    stats_table.add_column("Index", style="cyan")
    stats_table.add_column("Size", style="yellow")

    stats_table.add_row("papers (all records)", str(db.count()))
    stats_table.add_row("_doi_index (unique DOIs)", str(len(db._doi_index)))
    stats_table.add_row("_cite_key_index (unique keys)", str(len(db._cite_key_index)))
    stats_table.add_row("_id_index (unique IDs)", str(len(db._id_index)))

    console.print(stats_table)

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
    table = Table(title="Incoming Citation Distribution")
    table.add_column("Citations", style="cyan", justify="right")
    table.add_column("Number of Papers", style="green", justify="right")
    table.add_column("Percentage", style="yellow", justify="right")
    table.add_column("Histogram", style="blue")

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
    console.print(f"  [dim]Average resolved incoming citations per paper: {avg_citations:.2f}[/dim]")
    console.print(f"  [dim]Maximum citations: {max_citations}[/dim]")

    # Print citation resolution statistics
    total_papers = {}
    total_citations = {}
    total_doi = {}
    total_resolved = {}

    for paper in db.to_list(primary_only=False):
        iteration = paper.discovery.iteration
        total_papers[iteration] = total_papers.get(iteration, 0) + 1
        for citation in paper.citations:
            total_citations[iteration] = total_citations.get(iteration, 0) + 1
            if citation.doi:
                total_doi[iteration] = total_doi.get(iteration, 0) +  1
            if citation.resolved_paper is not None:
                total_resolved[iteration] = total_resolved.get(iteration, 0) + 1

    table = Table(show_header=True, header_style="bold", title="Citation stats")
    table.add_column("Iteration", style="bold")
    table.add_column("Papers", style="cyan", no_wrap=True)
    table.add_column("Citations", style="blue", justify="center")
    table.add_column("With doi", style="red", justify="center", no_wrap=True)
    table.add_column("Resolved", style="green", justify="center", no_wrap=True)

    for i in range(max(total_papers.keys()) + 1):
        table.add_row(
            str(i),
            str(total_papers.get(i, 0)),
            str(total_citations.get(i, 0)),
            str(total_doi.get(i, 0)),
            str(total_resolved.get(i, 0)),
        )
    table.add_row(
        "Total",
        str(sum(total_papers.values())),
        str(sum(total_citations.values())),
        str(sum(total_doi.values())),
        str(sum(total_resolved.values())),
    )

    console.print(table)


def _display_bibliography(db: PapersDatabase) -> None:
    """
    Display a histogram of citation counts ordered by number of citations (descending)
    
    Shows how many papers have each citation count, ordered from most cited to least.
    
    Args:
        papers_db: List of papers to analyze
    """
    # Filter to primary papers only
    primary_papers = db.to_list(primary_only=False)


    # Count papers by citation count
    keywords = 0
    abstracts = 0
    keyword_abstracts = 0
    pdf = 0
    doi = 0
    for paper in primary_papers:
        if paper.keywords:
            keywords += 1
        if paper.abstract:
            abstracts += 1
        if paper.keywords and paper.abstract:
            keyword_abstracts += 1
        if paper.pdf_info and paper.pdf_info.file_path:
            pdf += 1
        if paper.doi:
            doi += 1


    # Create table
    table = Table(title="Citation Distribution")
    table.add_column("Papers", style="cyan", justify="right")
    table.add_column("With Keywords", style="green", justify="right")
    table.add_column("With Abstract", style="yellow", justify="right")
    table.add_column("With Both", style="blue")
    table.add_column("With PDF", style="blue")
    table.add_column("With DOI", style="magenta")

    table.add_row(
        str(len(primary_papers)),
        str(keywords),
        str(abstracts),
        str(keyword_abstracts),
        str(pdf),
        str(doi)
    )
    console.print(table)


def _display_histogram(db: PapersDatabase) -> None:
    """
    Display a histogram of included papers by discovery iteration and publication year.
    
    Shows only papers that passed screening (included = True), grouped by:
    - Discovery iteration (0 = initial, 1+ = snowballing iterations)
    - Publication year
    
    Args:
        db: PapersDatabase instance
    """
    # Get all included papers (screening passed)
    all_papers = db.to_list(primary_only=False)
    included_papers = [p for p in all_papers if p.is_included]
    
    if not included_papers:
        console.print("[yellow]No included papers found[/yellow]")
        return
    
    # Build histogram: iteration -> year -> count
    histogram: Dict[int, Dict[int, int]] = {}
    
    for paper in included_papers:
        iteration = paper.discovery.iteration if paper.discovery else 0
        year = paper.year
        
        if year is None:
            year = 0  # Unknown year
        
        if iteration not in histogram:
            histogram[iteration] = {}
        
        if year not in histogram[iteration]:
            histogram[iteration][year] = 0
        
        histogram[iteration][year] += 1
    
    # Create table
    table = Table(title="Included Papers by Discovery Iteration and Year")
    table.add_column("Iteration", style="cyan", justify="right")
    table.add_column("Year", style="green", justify="right")
    table.add_column("Count", style="yellow", justify="right")
    table.add_column("% of Total", style="blue", justify="right")
    table.add_column("Distribution", style="magenta")
    
    total_included = len(included_papers)
    
    # Find max count for bar width normalization
    max_count = max(
        count 
        for year_dict in histogram.values() 
        for count in year_dict.values()
    ) if histogram else 1
    
    # Sort iterations and years, display with grouping
    for iteration in sorted(histogram.keys(), reverse=True):
        years = sorted(histogram[iteration].keys(), reverse=True)
        for year in years:
            count = histogram[iteration][year]
            percentage = (count / total_included * 100) if total_included > 0 else 0
            
            # Create bar visualization
            bar_width = int((count / max_count) * 30) if max_count > 0 else 0
            bar = "█" * bar_width
            
            year_str = str(year) if year > 0 else "[dim]Unknown[/dim]"
            iteration_str = str(iteration) if iteration == 0 else f"{iteration} (snowball)"
            
            table.add_row(
                iteration_str,
                year_str,
                str(count),
                f"{percentage:.1f}%",
                bar
            )
    
    # Add total row
    table.add_row(
        "[bold]Total[/bold]",
        "",
        f"[bold]{total_included}[/bold]",
        "[bold]100.0%[/bold]",
        ""
    )
    
    console.print(table)

