"""
Keyword-based screening step for paper filtering.

Performs automated keyword-based screening using configurable:
- Hard exclusion keywords (if found, paper is excluded)
- Inclusion keywords (must match minimum threshold)
- Field-specific matching (title, abstract, keywords)

Outputs screening results to paper.screening.keyword_screening with:
- passed: boolean indicating if paper passed screening
- score: number of inclusion keywords matched
- inclusion_keywords: matched inclusion keywords
- exclusion_keywords: matched exclusion keywords
- title_matches: number of matches in title
- abstract_matches: number of matches in abstract
- keywords_matches: number of matches in paper keywords field
- exclusion_reason: explanation if paper was excluded
- metadata: processing timestamp and duration
"""

import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from ..core.enum import ScreeningDecision
from ..core.models import KeywordScreening, Paper, ProcessingMetadata
from .base import BaseStep
from paper_scanner.core.enum import StepStatus

# Initialize rich console for colored output
console = Console(file=sys.stderr)


class KeywordScreeningStep(BaseStep):
    """Keyword-based screening step for filtering papers by inclusion/exclusion keywords."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate keyword_screening step configuration.
        
        Args:
            config: Step configuration
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check enabled flag
        if "enabled" in config and not isinstance(config["enabled"], bool):
            errors.append("'enabled' must be a boolean")
        
        # Check word_boundaries flag
        if "word_boundaries" in config and not isinstance(config["word_boundaries"], bool):
            errors.append("'word_boundaries' must be a boolean")
        
        # Check threshold
        if "threshold" in config:
            threshold = config["threshold"]
            if not isinstance(threshold, int):
                errors.append("'threshold' must be an integer")
            elif threshold < 0:
                errors.append("'threshold' must be non-negative")
        
        # Check exclusion_keywords
        if "exclusion_keywords" in config:
            exc_kw = config["exclusion_keywords"]
            if isinstance(exc_kw, dict):
                # Nested format: validate all values are lists/strings
                for key, val in exc_kw.items():
                    if isinstance(val, list):
                        for item in val:
                            if not isinstance(item, str):
                                errors.append(f"'exclusion_keywords.{key}' must contain strings")
                    elif not isinstance(val, str):
                        errors.append(f"'exclusion_keywords.{key}' must be a string or list of strings")
            elif isinstance(exc_kw, list):
                # Flat format
                for item in exc_kw:
                    if not isinstance(item, str):
                        errors.append("'exclusion_keywords' must contain strings")
            else:
                errors.append("'exclusion_keywords' must be a list or dictionary")
        
        # Check inclusion_keywords
        if "inclusion_keywords" in config:
            inc_kw = config["inclusion_keywords"]
            if isinstance(inc_kw, dict):
                # Nested format
                for key, val in inc_kw.items():
                    if isinstance(val, list):
                        for item in val:
                            if not isinstance(item, str):
                                errors.append(f"'inclusion_keywords.{key}' must contain strings")
                    elif not isinstance(val, str):
                        errors.append(f"'inclusion_keywords.{key}' must be a string or list of strings")
            elif isinstance(inc_kw, list):
                # Flat format
                for item in inc_kw:
                    if not isinstance(item, str):
                        errors.append("'inclusion_keywords' must contain strings")
            else:
                errors.append("'inclusion_keywords' must be a list or dictionary")
        
        return len(errors) == 0, errors


    # ============================================================================
    # STEP EXECUTION
    # ============================================================================

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute keyword screening step.
        
        Args:
            config: Step configuration (see _parse_keyword_config for structure)
            verbose: Enable verbose output
            dry_run: Don't actually modify papers
            debug: Enable debug output
            
        Returns:
            Dictionary with execution results
        """
        step_start_time = time.time()
        
        # Check if step is enabled
        if not config.get('enabled', True):
            return {
                "step": "keyword_screening",
                "status": "skipped",
                "reason": "disabled in configuration"
            }
        
        # Parse configuration
        hard_exclusions, inclusion_keywords, threshold = _parse_keyword_config(config)
        use_word_boundaries = config.get('word_boundaries', True)
        
        if verbose:
            console.print("  [bold cyan]Keyword Screening[/bold cyan]")
            console.print(f"    [dim]Hard exclusions: {len(hard_exclusions)} keywords[/dim]")
            console.print(f"    [dim]Inclusion keywords: {len(inclusion_keywords)} keywords[/dim]")
            console.print(f"    [dim]Threshold: {threshold}[/dim]")
            console.print(f"    [dim]Processing {self.db.count(primary_only=False)} papers...[/dim]")
        
        # Initialize results
        results = {
            "step": "keyword_screening",
            "total_papers": self.db.count(primary_only=False),
            "screened": 0,
            "passed": 0,
            "failed": 0,
            "score_distribution": {},
            "top_matched_keywords": {},
            "exclusion_reasons": {}
        }
        
        # Track matched keywords across all papers
        keyword_counts = {}
        
        # Process each paper
        all_papers = self.db.to_list(primary_only=False)
        for i, paper in enumerate(all_papers):
            # Show progress every 100 papers
            if verbose and (i + 1) % 100 == 0:
                import sys
                sys.stdout.write(f"\r    Processed {i + 1}/{len(all_papers)} papers... Passed: {results['passed']}, Failed: {results['failed']}")
                sys.stdout.flush()
            
            screening, passed, exclusion_reason = _screen_paper(
                paper,
                hard_exclusions,
                inclusion_keywords,
                inclusion_threshold=threshold,
                use_word_boundaries=use_word_boundaries,
                verbose=verbose
            )
            
            if not dry_run:
                paper.screening.keyword_screening = screening
                
                # Update screening decision if appropriate
                if not passed and paper.screening.final_decision == ScreeningDecision.PENDING:
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED
                    paper.screening.final_decision_at = datetime.now(timezone.utc)
                    paper.screening.final_decision_by = "automated:keyword_screening"
                
                # Update paper in database
                self.db.update(paper)
            
            results["screened"] += 1
            
            # Track statistics
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                if exclusion_reason:
                    results["exclusion_reasons"][exclusion_reason] = \
                        results["exclusion_reasons"].get(exclusion_reason, 0) + 1
            
            # Track score distribution
            score = screening.score
            if score not in results["score_distribution"]:
                results["score_distribution"][score] = 0
            results["score_distribution"][score] += 1
            
            # Track matched keywords
            for keyword in screening.inclusion_keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        # Get top matched keywords
        if keyword_counts:
            sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
            results["top_matched_keywords"] = dict(sorted_keywords[:10])
        
        duration = time.time() - step_start_time
        results["duration_seconds"] = duration
        
        if verbose:
            # Clear the progress line and print final result
            console.print(f"    [green]✓ Keyword screening complete[/green] - Passed: [cyan]{results['passed']}[/cyan], Failed: [cyan]{results['failed']}[/cyan]")

        results["status"] = StepStatus.SUCCESS
        return results
# ============================================================================
# KEYWORD MATCHING UTILITIES
# ============================================================================

def _normalize_text(text: Optional[str]) -> str:
    """
    Normalize text for keyword matching.
    
    Args:
        text: Text to normalize
        
    Returns:
        Lowercase, whitespace-trimmed text
    """
    if not text:
        return ""
    return text.lower().strip()


def _check_keyword_match(
    text: str,
    keywords: List[str],
    use_word_boundaries: bool = True
) -> Tuple[List[str], int]:
    """
    Check which keywords match in text.
    
    Args:
        text: Text to search in (should be normalized)
        keywords: List of keywords to check
        use_word_boundaries: If True, use word boundary matching to avoid partial matches
        
    Returns:
        Tuple of (matched_keywords, match_count)
    """
    matched = []
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        if use_word_boundaries:
            # Use word boundary matching to avoid partial matches
            # e.g., "supply" shouldn't match "supplier"
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(pattern, text):
                matched.append(keyword)
        else:
            # Simple substring matching
            if keyword_lower in text:
                matched.append(keyword)
    
    return matched, len(matched)


def _get_field_matches(
    paper: Paper,
    keywords: List[str],
    use_word_boundaries: bool = True
) -> Tuple[int, int, int, List[str]]:
    """
    Count keyword matches in different paper fields.
    
    Args:
        paper: Paper to check
        keywords: Keywords to match
        use_word_boundaries: If True, use word boundary matching
        
    Returns:
        Tuple of (title_matches, abstract_matches, keywords_matches, all_matched_keywords)
    """
    title_matches = 0
    abstract_matches = 0
    keywords_matches = 0
    all_matched = set()
    
    # Title matches
    if paper.title:
        title_text = _normalize_text(paper.title)
        matched, count = _check_keyword_match(title_text, keywords, use_word_boundaries)
        title_matches = count
        all_matched.update(matched)
    
    # Abstract matches
    if paper.abstract:
        abstract_text = _normalize_text(paper.abstract)
        matched, count = _check_keyword_match(abstract_text, keywords, use_word_boundaries)
        abstract_matches = count
        all_matched.update(matched)
    
    # Keywords field matches (if available)
    if hasattr(paper, 'keywords') and paper.keywords:
        keywords_text = _normalize_text(
            " ".join(paper.keywords) if isinstance(paper.keywords, list) else paper.keywords
        )
        matched, count = _check_keyword_match(keywords_text, keywords, use_word_boundaries)
        keywords_matches = count
        all_matched.update(matched)
    
    return title_matches, abstract_matches, keywords_matches, list(all_matched)


# ============================================================================
# SCREENING LOGIC
# ============================================================================

def _screen_paper(
    paper: Paper,
    hard_exclusions: List[str],
    inclusion_keywords: List[str],
    inclusion_threshold: int = 1,
    use_word_boundaries: bool = True,
    verbose: bool = False
) -> Tuple[KeywordScreening, bool, Optional[str]]:
    """
    Perform keyword-based screening on a single paper.
    
    Args:
        paper: Paper to screen
        hard_exclusions: Keywords that cause immediate exclusion
        inclusion_keywords: Keywords that support inclusion
        inclusion_threshold: Minimum number of inclusion keywords needed to pass
        use_word_boundaries: If True, use word boundary matching
        verbose: Enable verbose output
        
    Returns:
        Tuple of (screening_result, passed, exclusion_reason)
    """
    step_start_time = time.time()
    
    # Combine title and abstract for evaluation
    combined_text = _normalize_text(
        f"{paper.title or ''} {paper.abstract or ''}"
    )
    
    # Check hard exclusions
    excluded_kw, excluded_count = _check_keyword_match(
        combined_text, hard_exclusions, use_word_boundaries
    )
    
    if excluded_count > 0:
        duration = time.time() - step_start_time
        return (
            KeywordScreening(
                passed=False,
                score=0,
                inclusion_keywords=[],
                exclusion_keywords=excluded_kw,
                title_matches=0,
                abstract_matches=0,
                keywords_matches=0,
                exclusion_reason=f"Hard exclusion keywords detected: {', '.join(excluded_kw)}",
                metadata=ProcessingMetadata(
                    processed_at=datetime.now(timezone.utc),
                    duration_seconds=duration
                )
            ),
            False,
            f"Hard exclusion keywords: {', '.join(excluded_kw)}"
        )
    
    # Check inclusion keywords
    title_matches, abstract_matches, keywords_matches, all_matched = _get_field_matches(
        paper, inclusion_keywords, use_word_boundaries
    )
    total_matches = len(all_matched)
    
    # Determine if paper passed
    passed = total_matches >= inclusion_threshold
    exclusion_reason = None
    
    if not passed:
        if total_matches == 0:
            exclusion_reason = "No inclusion keywords found"
        else:
            exclusion_reason = f"Found {total_matches}/{inclusion_threshold} required keywords"
    
    duration = time.time() - step_start_time
    
    return (
        KeywordScreening(
            passed=passed,
            score=total_matches,
            inclusion_keywords=all_matched,
            exclusion_keywords=excluded_kw,
            title_matches=title_matches,
            abstract_matches=abstract_matches,
            keywords_matches=keywords_matches,
            exclusion_reason=exclusion_reason if not passed else None,
            metadata=ProcessingMetadata(
                processed_at=datetime.now(timezone.utc),
                duration_seconds=duration
            )
        ),
        passed,
        exclusion_reason
    )


# ============================================================================
# CONFIGURATION PARSING
# ============================================================================

def _parse_keyword_config(config: Dict[str, Any]) -> Tuple[List[str], List[str], int]:
    """
    Parse keyword configuration from YAML.
    
    Config structure:
    ```yaml
    builtin.keyword_screening:
      enabled: true
      hard_exclusions:  # List of keywords - any match = exclude
        - "medical"
        - "healthcare"
        - "patient"
      inclusion_keywords:  # List of keywords - need threshold matches
        - "digital innovation"
        - "firm"
        - "supplier"
      threshold: 2  # Minimum inclusion keywords to match (default: 1)
      word_boundaries: true  # Use word boundary matching (default: true)
    ```
    
    Or nested structure:
    ```yaml
    builtin.keyword_screening:
      enabled: true
      hard_exclusions:
        domains:
          - "medical"
          - "healthcare"
        other:
          - "agriculture"
      inclusion_keywords:
        innovation:
          - "digital innovation"
          - "innovation"
        organization:
          - "firm"
          - "company"
      threshold: 2
    ```
    
    Args:
        config: Step configuration
        
    Returns:
        Tuple of (hard_exclusions, inclusion_keywords, threshold)
    """
    hard_exclusions = []
    inclusion_keywords = []
    threshold = config.get('threshold', 1)
    
    # Parse hard exclusions
    hard_exc_config = config.get('hard_exclusions', [])
    if isinstance(hard_exc_config, dict):
        # Nested structure - flatten all values
        for key, values in hard_exc_config.items():
            if isinstance(values, list):
                hard_exclusions.extend(values)
    elif isinstance(hard_exc_config, list):
        hard_exclusions = hard_exc_config
    
    # Parse inclusion keywords
    incl_kw_config = config.get('inclusion_keywords', [])
    if isinstance(incl_kw_config, dict):
        # Nested structure - flatten all values
        for key, values in incl_kw_config.items():
            if isinstance(values, list):
                inclusion_keywords.extend(values)
    elif isinstance(incl_kw_config, list):
        inclusion_keywords = incl_kw_config
    
    # Normalize to lowercase for matching
    hard_exclusions = [kw.lower() for kw in hard_exclusions if kw]
    inclusion_keywords = [kw.lower() for kw in inclusion_keywords if kw]
    
    return hard_exclusions, inclusion_keywords, threshold


