"""
Deduplication step for paper scanner

Identifies and marks duplicate papers using multiple matching methods
"""

from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher
from rich.console import Console

from ..core.models import Paper

# Initialize rich console
console = Console()


def _normalize_title(title: Optional[str]) -> str:
    """Normalize title for comparison"""
    if not title:
        return ""
    # Convert to lowercase, remove extra whitespace
    return " ".join(title.lower().split())


def _doi_exact_match(paper: Paper, existing_papers: List[Paper]) -> Optional[str]:
    """Check for exact DOI match"""
    if not paper.doi:
        return None
    
    for existing in existing_papers:
        if existing.doi and existing.doi.lower() == paper.doi.lower():
            return existing.id
    
    return None


def _title_author_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.90
) -> Optional[str]:
    """Check for fuzzy title + first author match"""
    if not paper.title or not paper.authors:
        return None
    
    norm_title = _normalize_title(paper.title)
    if not paper.authors[0]:
        return None
    
    first_author = paper.authors[0].family_name.lower()
    
    for existing in existing_papers:
        if not existing.title or not existing.authors:
            continue
        
        existing_norm_title = _normalize_title(existing.title)
        existing_first_author = existing.authors[0].family_name.lower()
        
        # Check if first authors match
        if first_author != existing_first_author:
            continue
        
        # Check title similarity
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()
        if similarity >= threshold:
            return existing.id
    
    return None


def _title_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.95
) -> Optional[str]:
    """Check for fuzzy title-only match"""
    if not paper.title:
        return None
    
    norm_title = _normalize_title(paper.title)
    
    for existing in existing_papers:
        if not existing.title:
            continue
        
        existing_norm_title = _normalize_title(existing.title)
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()
        
        if similarity >= threshold:
            return existing.id
    
    return None


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute deduplication step
    
    Args:
        config: Step configuration (includes deduplication methods and thresholds)
        papers_db: Current papers database (will be modified in-place to mark duplicates)
        verbose: Enable verbose output
        dry_run: Don't actually modify papers
    
    Returns:
        Dictionary with deduplication results
    """
    
    # Get deduplication configuration - supports nested "deduplication" key
    # Can be called as:
    #   builtin.deduplication:
    #     enabled: true
    #     methods: [...]
    # OR
    #   builtin.deduplication:
    #     deduplication:
    #       enabled: true
    #       methods: [...]
    
    dedup_config = config.get("deduplication")
    if dedup_config is None:
        dedup_config = config
    
    # Check if deduplication is enabled (default: true)
    enabled = dedup_config.get("enabled", True)
    if not enabled:
        return {
            "step": "deduplication",
            "total_papers": len(papers_db),
            "duplicates_found": 0,
            "duplicates": [],
            "methods_used": [],
            "status": "skipped"
        }
    
    methods = dedup_config.get("methods", [
        {"method": "doi_exact", "priority": 1},
        {"method": "title_author_fuzzy", "priority": 2, "threshold": 0.90},
        {"method": "title_fuzzy", "priority": 3, "threshold": 0.95},
    ])
    
    # Sort methods by priority
    methods = sorted(methods, key=lambda x: x.get("priority", 999))
    
    results = {
        "step": "deduplication",
        "total_papers": len(papers_db),
        "duplicates_found": 0,
        "duplicates": [],
        "methods_used": [m.get("method") for m in methods]
    }
    
    if verbose:
        console.print(f"\n  [bold cyan]Deduplicating {len(papers_db)} papers[/bold cyan]")
        console.print(f"    [yellow]Methods:[/yellow] {', '.join([m.get('method') for m in methods])}")
    
    # Track which papers we've already identified as unique
    unique_papers = []
    
    for i, paper in enumerate(papers_db):
        # Skip if already marked as duplicate
        if paper.duplicate_of is not None:
            continue
        
        duplicate_found = False
        
        # Try each method in priority order
        for method_config in methods:
            method = method_config.get("method")
            threshold = method_config.get("threshold", 0.95)
            
            duplicate_id = None
            
            if method == "doi_exact":
                duplicate_id = _doi_exact_match(paper, unique_papers)
            elif method == "title_author_fuzzy":
                duplicate_id = _title_author_fuzzy_match(paper, unique_papers, threshold)
            elif method == "title_fuzzy":
                duplicate_id = _title_fuzzy_match(paper, unique_papers, threshold)
            
            if duplicate_id:
                # Find the duplicate paper and link it
                for dup in unique_papers:
                    if dup.id == duplicate_id:
                        if not dry_run:
                            paper.duplicate_of = dup
                        
                        results["duplicates_found"] += 1
                        results["duplicates"].append({
                            "paper_id": paper.id,
                            "paper_title": paper.title,
                            "duplicate_of_id": duplicate_id,
                            "duplicate_of_title": dup.title,
                            "method": method
                        })
                        
                        if verbose:
                            console.print(f"    [yellow]Duplicate found:[/yellow] {paper.title[:60]}...")
                            console.print(f"      [cyan]Method:[/cyan] {method}, [cyan]Linked to:[/cyan] {dup.title[:60]}...")
                        
                        duplicate_found = True
                        break
            
            if duplicate_found:
                break
        
        # If not a duplicate, add to unique papers
        if not duplicate_found:
            unique_papers.append(paper)
    
    if verbose:
        console.print(f"    [green]✓ Deduplication complete[/green]")
        console.print(f"    [cyan]Duplicates found:[/cyan] {results['duplicates_found']}")
        console.print(f"    [cyan]Unique papers:[/cyan] {len(unique_papers)}")
    
    return results
