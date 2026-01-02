"""
Metadata-based screening step for paper filtering.

Performs attribute-based screening using configurable tri-state logic:
- Hard INCLUDE: Must have these values (when explicitly listed)
- Hard EXCLUDE: Must NOT have these values, or exclude everything except (NOT: syntax)
- OMITTED: No requirement (leave aside)

Outputs screening results to paper.screening.metadata_screening with:
- paper_type: Detected or validated paper type
- language: Paper language (ISO code)
- quality_tier: Quality tier assessment
- is_peer_reviewed: Peer review status
- exclusion_reason: Explanation if paper was excluded
- metadata: Processing timestamp and duration
"""

import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.enum import (
    PaperType,
    QualityTier,
    ScreeningDecision,
    StepStatus,
)
from paper_scanner.core.models import MetadataScreening, Paper, ProcessingMetadata
from paper_scanner.core.step_result import StepResult
from .base import BaseStep

# Initialize rich console for colored output
console = Console(file=sys.stderr)


class MetadataScreeningStep(BaseStep):
    """Metadata-based screening step for filtering papers by attributes."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate metadata_screening step configuration.
        
        Args:
            config: Step configuration with optional keys:
                - enabled: bool - Whether screening is enabled (default: true)
                - exclude: dict - Fields and values to exclude with keys:
                    - language: list[str] - Language codes to exclude (e.g., ["de", "fr"])
                    - paper_types: list[str|dict] - Paper types to exclude
                        Can be plain string or dict with "NOT": value for exclude-everything-except
                    - quality_tier: list[str] - Quality tiers to exclude
                    - is_peer_reviewed: list[bool] - Peer review status to exclude
            
        Returns:
            Tuple of (is_valid, error_messages)
            
        Raises:
            Returns error list if:
            - Any exclude field is not a list
            - Any list item is not string or {"NOT": value} dict
            - enabled is not boolean
        """
        errors = []

        # Check enabled flag
        if "enabled" in config and not isinstance(config["enabled"], bool):
            errors.append("'enabled' must be a boolean")

        # Check exclude section
        if "exclude" in config:
            exclude = config["exclude"]
            if not isinstance(exclude, dict):
                errors.append("'exclude' must be a dictionary")
            else:
                # Validate each field in exclude
                for field, criteria in exclude.items():
                    if not isinstance(criteria, list):
                        errors.append(f"'exclude.{field}' must be a list")
                    else:
                        # Each criterion can be string or dict (for NOT: syntax)
                        for i, criterion in enumerate(criteria):
                            if isinstance(criterion, str):
                                # Plain string is OK
                                pass
                            elif isinstance(criterion, dict):
                                # Dict format like {"NOT": "value"}
                                if "NOT" not in criterion:
                                    errors.append(
                                        f"'exclude.{field}[{i}]': dict must have 'NOT' key"
                                    )
                            else:
                                errors.append(
                                    f"'exclude.{field}[{i}]': must be string or dict"
                                )

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """
        Execute metadata-based screening step using tri-state logic.
        
        Design Decisions:
        ==================
        - Tri-state inclusion logic: Must match include rules, must NOT match exclude rules
        - Supports negation: {"NOT": "value"} inverts the match (exclude all EXCEPT value)
        - Language and paper type are most common filters
        - Quality tier assessment based on peer review status and source ranking
        - Missing metadata treated as passing (don't exclude without info)
        
        Priority Logic:
        ===============
        Papers are screened in this order:
        1. Check if paper_types field matches exclude rules → EXCLUDED if match
        2. Check if language matches exclude rules → EXCLUDED if match
        3. Check if quality_tier matches exclude rules → EXCLUDED if match
        4. Check if is_peer_reviewed status matches exclude rules → EXCLUDED if match
        5. If no exclusions match → INCLUDED
        
        Negation (NOT) Syntax:
        ======================
        The {"NOT": "value"} syntax inverts logic - exclude everything EXCEPT the value:
        
        exclude:
          paper_types:
            - {"NOT": "OPINION"}  # Means: exclude everything except OPINION papers
        
        This is useful for inclusive filters (e.g., only include conference papers).

        Args:
            config: Step configuration with optional keys:
                - enabled: bool (default: true) - Whether to run this screening
                - exclude: dict - Fields and values that trigger exclusion
            verbose: Enable verbose output
            dry_run: Don't actually modify papers
            debug: Enable debug output
            
        Returns:
            StepResult with execution statistics including:
            - screened: Papers processed
            - passed: Papers included
            - failed: Papers excluded
            - exclusion_reasons: Dict with counts of exclusion reasons
        """
        # Parse configuration
        exclude_logic = self._extract_exclude_logic(config.get("exclude", {}))
        exclude_no_doi = config.get("exclude_no_doi", True)

        self.callback(
            "Metadata Screening"
            f" * Fields being screened: {len(exclude_logic)}"
            f" * Processing {self.db.count(primary_only=False)} papers...", debug=True
        )

        # Initialize results
        results = {
            "total_papers": self.db.count(primary_only=True),
            "screened": 0,
            "passed": 0,
            "failed": 0,
            "exclusion_reasons": {},
        }

        # Process each non duplicate paper, this is idempotent
        all_papers = self.db.find(
            predicate=lambda p: not p.is_excluded and not p.is_included and not p.screening.metadata_screening,
            primary_only=True
        )

        for i, paper in enumerate(all_papers):
            screening, passed, exclusion_reason = self._screen_paper(
                paper, exclude_logic
            )

            if not dry_run:
                paper.screening.metadata_screening = screening
                paper.screening.current_stage="metadata_screening_complete"

                # Update screening decision if appropriate
                if not passed and paper.screening.final_decision in (ScreeningDecision.PENDING, ScreeningDecision.UNCERTAIN):
                    paper.screening.final_decision = ScreeningDecision.EXCLUDED
                    paper.screening.final_decision_by = "automated:metadata_screening"

                # Update paper in database
                # TODO: this is only for SQL, not in-memory
                self.db.update(paper)

            results["screened"] += 1

            # Track statistics
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
                if exclusion_reason:
                    results["exclusion_reasons"][exclusion_reason] = (
                        results["exclusion_reasons"].get(exclusion_reason, 0) + 1
                    )

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Screened {results['screened']} papers: "
            f"{results['passed']} passed, {results['failed']} failed",
            stats=results,
            details=self._format_details(results),
        )

    def _screen_paper(
        self,
        paper: Paper,
        exclude_logic: Dict[str, Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[MetadataScreening, bool, Optional[str]]:
        """
        Screen paper against metadata exclude criteria.
        
        Returns:
            (MetadataScreening model, should_include, exclusion_reason)
        """
        start_time = datetime.now(timezone.utc)
        exclusion_reason = None

        # Check each field in exclude logic
        for field, field_logic in exclude_logic.items():
            if field == "doi_not_set":
                # string handling trick to stay within structure
                paper_value = paper.doi or "None" 
            elif field == "language":
                paper_value = paper.language or "en"
            elif field == "paper_types":
                paper_value = paper.paper_type.value if paper.paper_type else None
            elif field == "quality_tier":
                paper_value = paper.screening.metadata_screening.quality_tier.value if paper.screening.metadata_screening else None
            else:
                continue

            if not paper_value:
                continue

            # Check hard excludes first
            for hard_exclude in field_logic.get("hard_excludes", []):
                if self._value_matches(paper_value, hard_exclude):
                    exclusion_reason = f"{field}: {paper_value} (hard excluded)"
                    break

            # Check exclude_all_except
            if not exclusion_reason and field_logic.get("exclude_all_except"):
                allowed_value = field_logic["exclude_all_except"]
                if not self._value_matches(paper_value, allowed_value):
                    exclusion_reason = (
                        f"{field}: '{paper_value}' (only '{allowed_value}' allowed)"
                    )

            # Stop checking if excluded
            if exclusion_reason:
                break

        # Determine paper_type and peer review status
        paper_type = paper.paper_type or PaperType.JOURNAL_ARTICLE
        is_peer_reviewed = paper_type == PaperType.JOURNAL_ARTICLE

        # Get quality tier
        quality_tier = QualityTier.UNKNOWN
        if paper.screening.metadata_screening:
            quality_tier = paper.screening.metadata_screening.quality_tier

        # Build screening model
        duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        metadata_screening = MetadataScreening(
            passed=exclusion_reason is None,
            paper_type=paper_type,
            language=paper.language or "en",
            quality_tier=quality_tier,
            is_peer_reviewed=is_peer_reviewed,
            exclusion_reason=exclusion_reason,
            metadata=ProcessingMetadata(
                duration_seconds=duration_seconds,
                success=True,
            ),
        )

        should_include = exclusion_reason is None
        return metadata_screening, should_include, exclusion_reason

    def _extract_exclude_logic(
        self, exclude_config: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract exclude logic from config into structured format.
        
        Returns:
        {
            "field_name": {
                "exclude_all_except": "value" or None,
                "hard_excludes": ["value1", "value2"]
            }
        }
        """
        logic = {}

        for field, criteria in exclude_config.items():
            exclude_all_except = None
            hard_excludes = []
            if isinstance(criteria, bool):
                # Special case for doi_not_set
                if field == "doi_not_set":
                    hard_excludes.append("None" if criteria else "set")
            else:
                for criterion in criteria:
                    # Parse NOT operator (works with both dict and string formats)
                    not_value = self._parse_not_operator(criterion)
                    if not_value:
                        exclude_all_except = not_value
                    else:
                        # Hard exclude: add the value
                        if isinstance(criterion, dict):
                            # Skip dict entries that aren't NOT
                            pass
                        elif isinstance(criterion, str):
                            hard_excludes.append(criterion)

            logic[field] = {
                "exclude_all_except": exclude_all_except,
                "hard_excludes": hard_excludes,
            }

        return logic

    @staticmethod
    def _parse_not_operator(criterion: Any) -> Optional[str]:
        """Parse NOT operator from criterion (dict or string format)
        
        Returns the value after NOT or None if not present
        """
        if isinstance(criterion, dict):
            return criterion.get("NOT")
        elif isinstance(criterion, str) and criterion.startswith("NOT:"):
            return criterion.replace("NOT:", "").strip()
        return None

    @staticmethod
    def _value_matches(paper_value: str, criterion: str) -> bool:
        """Check if paper value matches exclusion criterion"""
        return criterion.lower() in paper_value.lower()

    @staticmethod
    def _format_details(results: Dict[str, Any]) -> str:
        """Format detailed results as markdown"""
        lines = [
            "## Metadata Screening Results\n",
            f"- **Total Papers**: {results['total_papers']}",
            f"- **Screened**: {results['screened']}",
            f"- **Passed**: {results['passed']}",
            f"- **Failed**: {results['failed']}",
        ]

        if results.get("exclusion_reasons"):
            lines.append("\n### Exclusion Reasons\n")
            for reason, count in sorted(
                results["exclusion_reasons"].items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {reason}: {count} papers")

        return "\n".join(lines)
