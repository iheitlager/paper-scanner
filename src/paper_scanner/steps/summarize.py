"""
Database summary step for paper scanner

Outputs database statistics and relevant facts
"""

from typing import Dict, Any, List, Tuple
from collections import Counter
from rich.console import Console
from rich.table import Table

from ..core.models import Paper
from ..core.enum import ScreeningDecision

# Initialize rich console
console = Console()


def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate summarize step configuration.
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check summary flag
    if "summary" in config and not isinstance(config["summary"], bool):
        errors.append("'summary' must be a boolean")
    
    # Check screening flag
    if "screening" in config and not isinstance(config["screening"], bool):
        errors.append("'screening' must be a boolean")
    
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


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute database summary step
    
    Args:
        config: Step configuration with options:
            - summary: bool (default: True) - Show summary statistics
            - screening: bool (default: False) - Show screening results
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
    
    if len(papers_db) == 0:
        results["statistics"] = {
            "total_papers": 0,
            "message": "No papers in database"
        }
        if verbose:
            console.print("\n  [yellow]Database Summary:[/yellow]")
            console.print("    [red]No papers in database yet[/red]")
        return results
    
    # Basic statistics
    total = len(papers_db)
    
    # Authors statistics
    all_authors = []
    for paper in papers_db:
        all_authors.extend(paper.authors)
    
    unique_authors = len(set(a.full_name for a in all_authors))
    
    # Years
    years_with_papers = [p.year for p in papers_db if p.year]
    year_range = f"{min(years_with_papers)}-{max(years_with_papers)}" if years_with_papers else "N/A"
    
    # Identifiers
    with_doi = sum(1 for p in papers_db if p.doi)
    with_abstract = sum(1 for p in papers_db if p.abstract)
    
    # Keywords
    all_keywords = []
    for paper in papers_db:
        all_keywords.extend(paper.keywords)
    unique_keywords = len(set(all_keywords))
    
    # Sources
    sources = Counter()
    for paper in papers_db:
        if paper.discovery and paper.discovery.source_database:
            sources[paper.discovery.source_database] += 1
    
    # Screening status
    screening_status = Counter()
    for paper in papers_db:
        screening_status[paper.screening.final_decision.value] += 1
    
    # Duplicates
    unique_papers = sum(1 for p in papers_db if p.duplicate_of is None)
    duplicate_papers = sum(1 for p in papers_db if p.duplicate_of is not None)
    
    # Paper types (from paper.paper_type field, not screening)
    paper_types = Counter()
    for paper in papers_db:
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
        "papers_with_keywords": sum(1 for p in papers_db if p.keywords),
        "unique_keywords": unique_keywords,
        "sources": dict(sources),
        "screening_status": dict((k, v) for k, v in screening_status.items()),
        "paper_types": dict(paper_types) if paper_types else None
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
        
        if sources:
            sources_str = str(dict(sources))
            console.print(f"    Sources: [dim]{sources_str}[/dim]")
        
        if screening_status:
            status_str = str(dict(screening_status))
            console.print(f"    Screening status: [dim]{status_str}[/dim]")
        
        if paper_types:
            types_str = str(dict(paper_types))
            console.print(f"    Paper types: [dim]{types_str}[/dim]")
    
    # Generate tables if requested
    if verbose and tabulate_configs:
        for tab_config in tabulate_configs:
            field = tab_config.get("field")
            duplicates = tab_config.get("duplicates", False)
            
            if not field:
                continue
            
            # Filter papers based on duplicates setting
            papers_to_tabulate = _filter_by_duplicates(papers_db, duplicates)
            
            # Generate table for this field
            table_data = _generate_field_table(papers_to_tabulate, field, len(papers_db))
            if table_data:
                console.print(f"\n  [bold yellow]Papers by {field.title()}:[/bold yellow]")
                console.print(table_data)
                results["tables"][field] = "generated"
    
    # Display screening results if requested
    if verbose and show_screening:
        console.print("\n  [bold yellow]Screening Results by Paper Type:[/bold yellow]")
        _display_screening_results(papers_db)
    
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
    Display screening results breakdown by paper_type
    
    Args:
        papers_db: List of papers to analyze
    """
    if not papers_db:
        console.print("\n  [red]No papers to display screening results[/red]")
        return
    
    # Group papers by paper_type and screening decision
    papers_by_type = {}
    
    for paper in papers_db:
        paper_type = paper.paper_type or "Unknown"
        decision = paper.screening.final_decision.value
        
        if paper_type not in papers_by_type:
            papers_by_type[paper_type] = {
                ScreeningDecision.INCLUDED.value: 0,
                ScreeningDecision.EXCLUDED.value: 0,
                ScreeningDecision.PENDING.value: 0,
                ScreeningDecision.MANUAL_REVIEW.value: 0,
                ScreeningDecision.UNCERTAIN.value: 0,
                "total": 0,
            }
        
        papers_by_type[paper_type][decision] += 1
        papers_by_type[paper_type]["total"] += 1
    
    # Create table
    table = Table(title="Screening Results by Paper Type")
    table.add_column("Paper Type", style="cyan")
    table.add_column("Included", justify="right", style="green")
    table.add_column("Excluded", justify="right", style="red")
    table.add_column("Pending", justify="right", style="yellow")
    table.add_column("Manual Review", justify="right", style="cyan")
    table.add_column("Uncertain", justify="right", style="magenta")
    table.add_column("Total", justify="right", style="bold")
    
    # Add rows for each paper type
    total_included = 0
    total_excluded = 0
    total_pending = 0
    total_manual_review = 0
    total_uncertain = 0
    total_papers = 0
    
    for paper_type in sorted(papers_by_type.keys()):
        counts = papers_by_type[paper_type]
        included = counts[ScreeningDecision.INCLUDED.value]
        excluded = counts[ScreeningDecision.EXCLUDED.value]
        pending = counts[ScreeningDecision.PENDING.value]
        manual_review = counts[ScreeningDecision.MANUAL_REVIEW.value]
        uncertain = counts[ScreeningDecision.UNCERTAIN.value]
        total = counts["total"]
        
        total_included += included
        total_excluded += excluded
        total_pending += pending
        total_manual_review += manual_review
        total_uncertain += uncertain
        total_papers += total
        
        table.add_row(
            paper_type,
            str(included),
            str(excluded),
            str(pending),
            str(manual_review),
            str(uncertain),
            str(total)
        )
    
    # Add total row
    table.add_row(
        "[bold]Total[/bold]",
        f"[bold green]{total_included}[/bold green]",
        f"[bold red]{total_excluded}[/bold red]",
        f"[bold yellow]{total_pending}[/bold yellow]",
        f"[bold cyan]{total_manual_review}[/bold cyan]",
        f"[bold magenta]{total_uncertain}[/bold magenta]",
        f"[bold]{total_papers}[/bold]"
    )
    
    console.print(table)
