"""
Database summary step for paper scanner

Outputs database statistics and relevant facts
"""

from typing import Dict, Any, List
from collections import Counter
from rich.console import Console
from rich.table import Table

from ..core.models import Paper
from ..core.enum import ScreeningDecision

# Initialize rich console
console = Console()


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute database summary step
    
    Args:
        config: Step configuration
        papers_db: Current papers database
        verbose: Enable verbose output
        dry_run: Don't actually process, just show what would happen
    
    Returns:
        Dictionary with database statistics
    """
    
    results = {
        "step": "database_summary",
        "timestamp": None,
        "statistics": {}
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
    
    # Paper types
    paper_types = Counter()
    for paper in papers_db:
        if paper.screening.categorization:
            paper_types[paper.screening.categorization.paper_type.value] += 1
    
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
    
    if verbose:
        print("\n  Database Summary:")
        print(f"    Total papers: {total}")
        print(f"    Unique papers: {unique_papers}")
        print(f"    Duplicate papers: {duplicate_papers}")
        print(f"    Total authors: {len(all_authors)}")
        print(f"    Unique authors: {unique_authors}")
        print(f"    Year range: {year_range}")
        print(f"    Papers with DOI: {with_doi}")
        print(f"    Papers with abstract: {with_abstract}")
        print(f"    Unique keywords: {unique_keywords}")
        
        if sources:
            print(f"    Sources: {dict(sources)}")
        
        if screening_status:
            print(f"    Screening status: {dict(screening_status)}")
    
    return results
