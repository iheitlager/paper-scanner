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

from paper_scanner.core.enum import StepStatus, ScreeningDecision
from ..core.models import DeduplicationResult, Paper, ProcessingMetadata
from ..core.step_result import StepResult
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

        # Compute normalized title (may already be stored in screening results)
        if existing.screening and existing.screening.deduplication and existing.screening.deduplication.normalized_title:
            existing_norm_title = existing.screening.deduplication.normalized_title
        else:
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

        # Compute normalized title (may already be stored in screening results)
        if existing.screening and existing.screening.deduplication and existing.screening.deduplication.normalized_title:
            existing_norm_title = existing.screening.deduplication.normalized_title
        else:
            existing_norm_title = _normalize_title(existing.title)
            
        similarity = SequenceMatcher(None, norm_title, existing_norm_title).ratio()

        if similarity >= threshold:
            return (existing.id, similarity)

    return None


class DeduplicationStep(BaseStep):
    """Deduplication step that finds duplicate papers."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate deduplication step configuration.
        
        Args:
            config: Step configuration with optional keys:
                - methods: list of dicts, each with:
                    - method: str - One of 'doi_exact', 'title_author_fuzzy', 'title_fuzzy'
                    - threshold: float [0-1] - Similarity threshold for fuzzy methods
                    - priority: int - Execution order (lower first)
                        
        Returns:
            Tuple of (is_valid, error_messages)
            
        Raises:
            Returns error list if:
            - methods is not a list of dicts
            - any method is not in VALID_METHODS
            - any threshold is not in [0, 1]
            - any priority is not an integer
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
        Execute multi-method deduplication step.
        
        Design Decisions:
        ==================
        - Three-tier matching strategy: DOI (exact) → title+author (fuzzy) → title-only (fuzzy)
        - DOI matching is O(1) with indexed lookup (most reliable when available)
        - Fuzzy matching uses difflib.SequenceMatcher for string similarity (0-1 scale)
        - Marks duplicates with paper.duplicate_of and creates full audit trail
        - Preserves first occurrence as primary, subsequent matches marked as duplicates
        - Idempotent: only processes papers with screening.deduplication = None
        
        Priority/Threshold Logic:
        ========================
        Papers are matched sequentially by method priority:
        1. DOI exact match (confidence=1.0)         → Perfect match, highest confidence
        2. Title+author fuzzy (default threshold 0.90) → Very similar paper from different source
        3. Title-only fuzzy (default threshold 0.95)   → Fallback for missing author data
        
        Higher thresholds are more conservative:
        - threshold=0.95 (strict):   Only obvious duplicates marked
        - threshold=0.85 (moderate): Balanced false positive/negative rate
        - threshold=0.75 (aggressive): Marks similar papers but risks false positives
        
        Update Chain:
        =============
        For each duplicate found:
        1. Sets paper.duplicate_of = matching_paper (simple flag)
        2. Creates screening.deduplication = DeduplicationResult(...) (audit trail)
        3. Sets screening.current_stage = 'deduplication_complete'
        4. Updates paper in database (if not dry_run)
        
        Args:
            config: Step configuration with optional keys:
                - methods: list - Deduplication methods to use (default: all three)
                    Each method dict has: method, threshold (optional), priority (optional)
            verbose: Enable verbose output
            dry_run: Don't modify papers
            debug: Enable debug output
        
        Returns:
            StepResult with status, message, and stats dict containing:
            - duplicates_found: Count of duplicate papers identified
            - unique_count: Count of unique papers (total - duplicates)
            - methods_used: List of deduplication methods applied
        """

        # Get deduplication configuration
        dedup_config = config.get("deduplication")
        if dedup_config is None:
            dedup_config = config

        methods = dedup_config.get("methods", [
            {"method": "doi_exact"},
            {"method": "title_author_fuzzy", "threshold": 0.90},
            {"method": "title_fuzzy", "threshold": 0.95},
        ])

        results = {
            "step": "deduplication",
            "total_papers": self.db.count(primary_only=False),
            "duplicates_found": 0,
            "duplicates": [],
            "methods_used": [m.get("method") for m in methods]
        }

        # Get all papers - both processed and unprocessed
        # Papers already marked as duplicate_of at import time need screening result set
        all_papers = self.db.all(primary_only=False)

        self.callback(
            f"Deduplicating {len(all_papers)} papers "
            f"Methods: {', '.join([m.get('method') for m in methods])}", debug=True)

        # Note: DOI duplicates are already resolved at import time via PapersDatabase.resolve_duplicates
        # This step now:
        # 1. Records deduplication results for papers already marked as duplicate_of at import
        # 2. Performs fuzzy matching for papers without DOI duplicates
        processed_ids = set()

        for i, paper in enumerate(all_papers):
            # If already marked as duplicate at import time, record the deduplication result
            if paper.is_duplicate and paper.screening.deduplication is None:
                # Record the import-time DOI duplicate detection
                if not dry_run:
                    paper.screening.deduplication = DeduplicationResult(
                        is_duplicate=True,
                        duplicate_of=paper.duplicate_of,
                        similarity_score=1.0,
                        method="doi_exact",
                        confidence=1.0,
                        normalized_title=paper.title.lower() if paper.title else None,
                        metadata=ProcessingMetadata()
                    )
                    self.db.update(paper)
                
                results["duplicates_found"] += 1
                results["duplicates"].append({
                    "paper_id": paper.id,
                    "duplicate_of_id": paper.duplicate_of.id,
                    "method": "doi_exact",
                    "confidence": 1.0
                })
                processed_ids.add(paper.id)
                continue

            # Skip if already has deduplication result
            if paper.screening.deduplication is not None:
                processed_ids.add(paper.id)
                continue

            # Try each method in priority order
            for method_config in methods:
                method = method_config.get("method")
                threshold = method_config.get("threshold", 0.95)

                match_result = None
                matching_paper = None
                confidence= 0.0
                similarity_score = 0.0

                if method == "doi_exact":
                    # Check if already marked as duplicate at import time via PapersDatabase.resolve_duplicates
                    # If paper.duplicate_of is set, it was detected as DOI duplicate during indexing
                    if paper.duplicate_of is not None:
                        matching_paper = paper.duplicate_of
                        match_result = (matching_paper.id, 1.0)
                        confidence = 1.0
                elif method == "title_author_fuzzy":
                    # For fuzzy matching, compare against papers processed so far (primary candidates)
                    # Only match against papers that came before in the list and haven't been marked as duplicates
                    candidate_primaries = [p for p in all_papers[:i] if p.duplicate_of is None]
                    match_result = _title_author_fuzzy_match(paper, candidate_primaries, threshold)
                    if match_result:
                        duplicate_id, similarity_score = match_result
                        matching_paper = self.db.get_by_id(duplicate_id)
                    confidence = min(1.0, similarity_score) if match_result else 1.0
                elif method == "title_fuzzy":
                    # For fuzzy matching, compare against papers processed so far (primary candidates)
                    # Only match against papers that came before in the list and haven't been marked as duplicates
                    candidate_primaries = [p for p in all_papers[:i] if p.duplicate_of is None]
                    match_result = _title_fuzzy_match(paper, candidate_primaries, threshold)
                    if match_result:
                        duplicate_id, similarity_score = match_result
                        matching_paper = self.db.get_by_id(duplicate_id)
                    confidence = min(1.0, similarity_score) if match_result else 1.0
                
                # Break out of methods loop once a match is found (use first matching method)
                if match_result and matching_paper:
                    break

            if match_result and matching_paper:
                results["duplicates_found"] += 1
                # Record the duplicate for the results
                results["duplicates"].append({
                    "paper_id": paper.id,
                    "duplicate_of_id": matching_paper.id,
                    "method": method,
                    "confidence": confidence,
                    "similarity_score": similarity_score
                })

            if not dry_run:
                if match_result and matching_paper:
                    # 1. Set simple duplicate_of field
                    paper.duplicate_of = matching_paper
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED_DUPLICATE
                    paper.screening.final_decision_by = "automated:deduplication"

                # 2. Create full audit trail in screening model
                paper.screening.deduplication = DeduplicationResult(
                    is_duplicate=bool(match_result),
                    duplicate_of=matching_paper if match_result else None,
                    similarity_score=similarity_score,
                    method=method if match_result else None,
                    confidence=confidence,
                    normalized_title=_normalize_title(paper.title),
                    metadata=ProcessingMetadata(
                        timestamp=datetime.now(timezone.utc),
                        success=True
                    )
                )
                paper.screening.current_stage = "deduplication_complete"

                # Update the paper in the database
                self.db.update(paper)

        unique_count = results["total_papers"] - results["duplicates_found"]
        results = StepResult(
            status=StepStatus.SUCCESS,
            message=f"Deduplication found {results['duplicates_found']} duplicates, {unique_count} unique papers",
            stats=results
        )
        return results
