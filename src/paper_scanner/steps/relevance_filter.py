"""
Relevance filtering step (threshold gate).

Pure data step — no LLM calls. Reads relevance scores from
Screening.relevance_scoring (populated by RelevanceScoringStep)
and applies configurable thresholds to include/exclude/flag papers.

Configuration options:
  - relevance_threshold: float [0-1] (default: 0.5)
  - confidence_threshold: float [0-1] (default: 0.7)
  - require_both: bool — require both thresholds met (default: true)
  - action: "exclude" or "flag_for_review" (default: "exclude")

Example YAML:
  - step: "Relevance Filter"
    builtin.relevance_filter:
      relevance_threshold: 0.6
      confidence_threshold: 0.7
      require_both: true
      action: "exclude"
"""

import logging
from typing import Any, Dict, List, Tuple

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.core.step_result import StepResult

from .base import BaseStep

logger = logging.getLogger(__name__)


class RelevanceFilterStep(BaseStep):
    """Threshold-based relevance filter — no LLM calls."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []

        for key in ("relevance_threshold", "confidence_threshold"):
            if key in config:
                val = config[key]
                if not isinstance(val, (int, float)):
                    errors.append(f"'{key}' must be a number")
                elif not (0 <= val <= 1):
                    errors.append(f"'{key}' must be between 0 and 1")

        if "require_both" in config and not isinstance(config["require_both"], bool):
            errors.append("'require_both' must be a boolean")

        if "action" in config and config["action"] not in ("exclude", "flag_for_review"):
            errors.append("'action' must be 'exclude' or 'flag_for_review'")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        relevance_threshold = config.get("relevance_threshold", 0.5)
        confidence_threshold = config.get("confidence_threshold", 0.7)
        require_both = config.get("require_both", True)
        action = config.get("action", "exclude")

        def predicate(p: Paper) -> bool:
            return (
                p.screening.relevance_scoring is not None
                and not p.is_excluded
            )

        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        stats = {
            "total_papers": paper_count,
            "passed": 0,
            "filtered": 0,
            "flagged": 0,
            "missing_scores": 0,
        }

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers with relevance scores to filter",
                step="relevance_filter",
                stats=stats,
            )

        for paper in all_papers:
            scoring = paper.screening.relevance_scoring

            relevance_ok = scoring.relevance >= relevance_threshold
            confidence_ok = scoring.confidence >= confidence_threshold

            if require_both:
                passes = relevance_ok and confidence_ok
            else:
                passes = relevance_ok or confidence_ok

            if passes:
                stats["passed"] += 1
            else:
                if not dry_run:
                    if action == "exclude":
                        paper.screening.final_decision = ScreeningDecision.EXCLUDED
                        paper.screening.final_decision_by = "automated:relevance_filter"
                        stats["filtered"] += 1
                    else:
                        paper.screening.final_decision = ScreeningDecision.MANUAL_REVIEW
                        paper.screening.final_decision_by = "automated:relevance_filter"
                        stats["flagged"] += 1

                    paper.screening.current_stage = "relevance_filter_complete"
                    self.db.update(paper)
                else:
                    if action == "exclude":
                        stats["filtered"] += 1
                    else:
                        stats["flagged"] += 1

        return StepResult(
            status=StepStatus.SUCCESS,
            message=(
                f"Relevance filter: {stats['passed']} passed, "
                f"{stats['filtered']} excluded, {stats['flagged']} flagged"
            ),
            step="relevance_filter",
            stats=stats,
        )
