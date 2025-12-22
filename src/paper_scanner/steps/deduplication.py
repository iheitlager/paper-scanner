"""
Deduplication step for paper scanner

Identifies and marks duplicate papers using multiple matching methods
Records audit trail in screening.deduplication for full traceability
"""

import sys
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from ..core.models import DeduplicationResult, Paper, ProcessingMetadata
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)

# Valid deduplication methods
VALID_METHODS = {"doi_exact", "title_author_fuzzy", "title_fuzzy"}


def _normalize_title(title: Optional[str]) -> str:
    """Normalize title for comparison"""
    if not title:
        return ""
    return " ".join(title.lower().split())


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
        # Skip the same paper
        if existing.id == paper.id:
            continue
            
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
        # Skip the same paper
        if existing.id == paper.id:
            continue
            
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

class DeduplicationStep(BaseStep):
    """Deduplication step that finds duplicate papers."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate deduplication step configuration.
        
        Args:
            config: Step configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Get the deduplication config (might be nested or flat)
        dedup_config = config.get("deduplication", config)
        
        # Check methods
        if "methods" in dedup_config:
            methods = dedup_config["methods"]
            if not isinstance(methods, list):
                errors.append("'methods' must be a list")
            else:
                for i, method in enumerate(methods):
                    if not isinstance(method, dict):
                        errors.append(f"Method {i} must be a dictionary")
                        continue
                    
                    method_name = method.get("method")
                    if not method_name:
                        errors.append(f"Method {i} missing 'method' field")
                    elif method_name not in VALID_METHODS:
                        errors.append(f"Method {i}: unknown method '{method_name}'. Valid: {VALID_METHODS}")
                    
                    if "priority" in method and not isinstance(method["priority"], int):
                        errors.append(f"Method {i} 'priority' must be an integer")
                    
                    if "threshold" in method:
                        threshold = method["threshold"]
                        if not isinstance(threshold, (int, float)):
                            errors.append(f"Method {i} 'threshold' must be a number")
                        elif not (0.0 <= threshold <= 1.0):
                            errors.append(f"Method {i} 'threshold' must be between 0.0 and 1.0")
        
        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute deduplication step
        
        Updates papers with:
        1. Simple flag: paper.duplicate_of = matching_paper
        2. Full audit trail: paper.screening.deduplication = DeduplicationResult(...)
        
        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't modify papers
            debug: Enable debug output
        
        Returns:
            Dictionary with deduplication results
        """
        
        step_start_time = time.time()
        
        # Get deduplication configuration
        dedup_config = config.get("deduplication")
        if dedup_config is None:
            dedup_config = config
                
        methods = dedup_config.get("methods", [
            {"method": "doi_exact", "priority": 1},
            {"method": "title_author_fuzzy", "priority": 2, "threshold": 0.90},
            {"method": "title_fuzzy", "priority": 3, "threshold": 0.95},
        ])
        
        # Sort methods by priority
        methods = sorted(methods, key=lambda x: x.get("priority", 999))
        
        results = {
            "step": "deduplication",
            "total_papers": self.db.count(primary_only=False),
            "duplicates_found": 0,
            "duplicates": [],
            "methods_used": [m.get("method") for m in methods]
        }
        
        if verbose:
            console.print(f"\n  [bold cyan]Deduplicating {self.db.count(primary_only=False)} papers[/bold cyan]")
            console.print(f"    [yellow]Methods:[/yellow] {', '.join([m.get('method') for m in methods])}")
        
        # Get all papers at the start - this gives us the original state
        all_papers = self.db.to_list(primary_only=False)
        
        # Track papers already processed
        processed_ids = set()
        
        for i, paper in enumerate(all_papers):
            # Skip if already marked as duplicate
            if paper.duplicate_of is not None:
                processed_ids.add(paper.id)
                continue
            
            duplicate_found = False
            
            # Show progress every 100 papers
            if verbose and (i + 1) % 100 == 0:
                import sys
                sys.stdout.write(f"\r    Processed {i + 1}/{len(all_papers)} papers... Found {results['duplicates_found']} duplicates so far")
                sys.stdout.flush()
            
            # Try each method in priority order
            for method_config in methods:
                method = method_config.get("method")
                threshold = method_config.get("threshold", 0.95)
                
                match_result = None
                matching_paper = None
                
                if method == "doi_exact":
                    # Use indexed lookup for O(1) performance
                    if paper.doi:
                        # Use the indexed lookup for O(1) performance
                        matching_papers = self.db.get_by_doi(paper.doi, primary_only=True)
                        if matching_papers:
                            matching_paper = matching_papers[0]
                            # If this paper is NOT the primary, it's a duplicate
                            if paper.id != matching_paper.id:
                                match_result = (matching_paper.id, 1.0)
                elif method == "title_author_fuzzy":
                    # For fuzzy matching, compare against papers processed so far (primary candidates)
                    # Only match against papers that came before in the list and haven't been marked as duplicates
                    candidate_primaries = [p for p in all_papers[:i] if p.duplicate_of is None]
                    match_result = _title_author_fuzzy_match(paper, candidate_primaries, threshold)
                    if match_result:
                        duplicate_id, similarity_score = match_result
                        matching_paper = self.db.get_by_id(duplicate_id)
                elif method == "title_fuzzy":
                    # For fuzzy matching, compare against papers processed so far (primary candidates)
                    # Only match against papers that came before in the list and haven't been marked as duplicates
                    candidate_primaries = [p for p in all_papers[:i] if p.duplicate_of is None]
                    match_result = _title_fuzzy_match(paper, candidate_primaries, threshold)
                    if match_result:
                        duplicate_id, similarity_score = match_result
                        matching_paper = self.db.get_by_id(duplicate_id)
                
                if match_result and matching_paper:
                    duplicate_id, similarity_score = match_result
                    
                    if not dry_run:
                        # 1. Set simple duplicate_of field
                        paper.duplicate_of = matching_paper
                        
                        # 2. Create full audit trail in screening model
                        paper.screening.deduplication = DeduplicationResult(
                            is_duplicate=True,
                            duplicate_of=matching_paper,
                            similarity_score=similarity_score,
                            method=method,
                            confidence=_get_confidence(method, similarity_score),
                            metadata=ProcessingMetadata(
                                timestamp=datetime.now(timezone.utc),
                                success=True
                            )
                        )
                        paper.screening.current_stage = "deduplication_complete"
                        
                        # Update the paper in the database
                        self.db.update(paper)
                    
                    results["duplicates_found"] += 1
                    results["duplicates"].append({
                        "paper_id": paper.id,
                        "paper_title": paper.title,
                        "duplicate_of_id": duplicate_id,
                        "duplicate_of_title": matching_paper.title,
                        "method": method,
                        "similarity_score": round(similarity_score, 3),
                        "confidence": round(_get_confidence(method, similarity_score), 3)
                    })
                    
                    duplicate_found = True
                    break
                
                if duplicate_found:
                    break
            
            # If not a duplicate, mark as non-duplicate in screening model
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
                    
                    # Update the paper in the database
                
                # Note: We don't maintain a separate unique_papers list anymore
                # Duplicates are tracked via the duplicate_of field in the database
        
        # Record processing time
        duration = time.time() - step_start_time
        if not dry_run:
            for paper in self.db.to_list(primary_only=False):
                if paper.screening.deduplication:
                    paper.screening.deduplication.metadata.duration_seconds = duration
        
        if verbose:
            # Clear the progress line and print final result
            import sys
            unique_count = self.db.count(primary_only=True)  # Count primary papers (non-duplicates)
            console.print(f"    [green]✓ Deduplication complete[/green] - Found [cyan]{results['duplicates_found']}[/cyan] duplicates, [cyan]{unique_count}[/cyan] unique papers")
        
        results["status"] = "ok"
        return results
