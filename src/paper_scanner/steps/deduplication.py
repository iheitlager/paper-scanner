"""
Deduplication step for paper scanner

Identifies and marks duplicate papers using multiple matching methods
Records audit trail in screening.deduplication for full traceability
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timezone
from rich.console import Console

from ..core.models import Paper, DeduplicationResult, ProcessingMetadata

# Initialize rich console
console = Console()


def _normalize_title(title: Optional[str]) -> str:
    """Normalize title for comparison"""
    if not title:
        return ""
    return " ".join(title.lower().split())


def _doi_exact_match(paper: Paper, existing_papers: List[Paper]) -> Optional[Tuple[str, float]]:
    """Check for exact DOI match - returns (paper_id, similarity_score)"""
    if not paper.doi:
        return None
    
    for existing in existing_papers:
        if existing.doi and existing.doi.lower() == paper.doi.lower():
            return (existing.id, 1.0)
    
    return None


def _title_author_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.90
) -> Optional[Tuple[str, float]]:
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
        
        if first_author != existing_first_author:
            continue
        
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()
        if similarity >= threshold:
            return (existing.id, similarity)
    
    return None


def _title_fuzzy_match(
    paper: Paper,
    existing_papers: List[Paper],
    threshold: float = 0.95
) -> Optional[Tuple[str, float]]:
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
            return (existing.id, similarity)
    
    return None


def _get_confidence(method: str, similarity_score: float) -> float:
    """Calculate confidence based on method and similarity score"""
    if method == "doi_exact":
        return 1.0  # 100% confident for DOI exact match
    elif method == "title_author_fuzzy":
        return min(1.0, similarity_score)  # Use similarity as confidence
    elif method == "title_fuzzy":
        return min(1.0, similarity_score)
    return 0.5


def execute(
    config: Dict[str, Any],
    papers_db: List[Paper],
    verbose: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute deduplication step
    
    Updates papers with:
    1. Simple flag: paper.duplicate_of = matching_paper
    2. Full audit trail: paper.screening.deduplication = DeduplicationResult(...)
    
    Args:
        config: Step configuration
        papers_db: Current papers database (modified in-place)
        verbose: Enable verbose output
        dry_run: Don't modify papers
    
    Returns:
        Dictionary with deduplication results
    """
    
    step_start_time = time.time()
    
    # Get deduplication configuration
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
            
            match_result = None
            
            if method == "doi_exact":
                match_result = _doi_exact_match(paper, unique_papers)
            elif method == "title_author_fuzzy":
                match_result = _title_author_fuzzy_match(paper, unique_papers, threshold)
            elif method == "title_fuzzy":
                match_result = _title_fuzzy_match(paper, unique_papers, threshold)
            
            if match_result:
                duplicate_id, similarity_score = match_result
                
                # Find the duplicate paper and link it
                for dup in unique_papers:
                    if dup.id == duplicate_id:
                        if not dry_run:
                            # 1. Set simple duplicate_of field
                            paper.duplicate_of = dup
                            
                            # 2. Create full audit trail in screening model
                            paper.screening.deduplication = DeduplicationResult(
                                is_duplicate=True,
                                duplicate_of=dup,
                                similarity_score=similarity_score,
                                method=method,
                                confidence=_get_confidence(method, similarity_score),
                                metadata=ProcessingMetadata(
                                    timestamp=datetime.now(timezone.utc),
                                    success=True
                                )
                            )
                            paper.screening.current_stage = "deduplication_complete"
                        
                        results["duplicates_found"] += 1
                        results["duplicates"].append({
                            "paper_id": paper.id,
                            "paper_title": paper.title,
                            "duplicate_of_id": duplicate_id,
                            "duplicate_of_title": dup.title,
                            "method": method,
                            "similarity_score": round(similarity_score, 3),
                            "confidence": round(_get_confidence(method, similarity_score), 3)
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
            if not dry_run:
                # Mark as non-duplicate in screening model
                paper.screening.deduplication = DeduplicationResult(
                    is_duplicate=False,
                    duplicate_of=None,
                    similarity_score=None,
                    method="none",
                    confidence=1.0,
                    metadata=ProcessingMetadata(
                        timestamp=datetime.now(timezone.utc),
                        success=True
                    )
                )
                paper.screening.current_stage = "deduplication_complete"
            
            unique_papers.append(paper)
    
    # Record processing time
    duration = time.time() - step_start_time
    if not dry_run:
        for paper in papers_db:
            if paper.screening.deduplication:
                paper.screening.deduplication.metadata.duration_seconds = duration
    
    if verbose:
        console.print(f"    [green]✓ Deduplication complete[/green]")
        console.print(f"    [cyan]Duplicates found:[/cyan] {results['duplicates_found']}")
        console.print(f"    [cyan]Unique papers:[/cyan] {len(unique_papers)}")
    
    return results
