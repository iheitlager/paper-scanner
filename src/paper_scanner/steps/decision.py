"""
Deterministic final decision step.

Pure data step -- no LLM calls. Combines screening signals from earlier steps
(relevance_scoring, keyword_screening, metadata_screening) into a final
include/exclude/manual_review decision using configurable threshold rules.

This fills the gap where only the expensive llm_classification step could
set final_decision = INCLUDED. See GitHub issue #61.

Configuration options:
  - include_when: dict of field conditions that must ALL be met to INCLUDE
  - exclude_when: dict of field conditions that must ALL be met to EXCLUDE
  - otherwise: "manual_review" or "pending" (default: "manual_review")

Supported fields:
  - relevance_score: float from relevance_scoring step
  - confidence: float from relevance_scoring step
  - keyword_passed: bool from keyword_screening step
  - metadata_passed: bool from metadata_screening step

Condition format: ">= 0.6", "< 0.3", "== true", "!= false"

Example YAML:
  - step: "Final decision"
    builtin.decision:
      include_when:
        relevance_score: ">= 0.6"
        confidence: ">= 0.7"
      exclude_when:
        relevance_score: "< 0.3"
      otherwise: "manual_review"
"""

import logging
import operator
import re
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.core.step_result import StepResult

from .base import BaseStep

logger = logging.getLogger(__name__)

VALID_FIELDS = {
    "relevance_score",
    "confidence",
    "keyword_passed",
    "metadata_passed",
}

OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

CONDITION_RE = re.compile(r"^(>=|<=|>|<|==|!=)\s*(.+)$")


def _parse_condition(expr: str) -> Tuple[Any, Any]:
    """Parse a condition string like '>= 0.6' into (operator_fn, value)."""
    m = CONDITION_RE.match(expr.strip())
    if not m:
        raise ValueError(f"Invalid condition: {expr!r}")

    op_str, val_str = m.group(1), m.group(2).strip()
    op_fn = OPERATORS[op_str]

    if val_str.lower() in ("true", "false"):
        return op_fn, val_str.lower() == "true"

    return op_fn, float(val_str)


def _validate_condition(field: str, expr: str) -> List[str]:
    """Validate a single condition, return list of errors."""
    errors = []

    if field not in VALID_FIELDS:
        errors.append(f"Unknown field '{field}'; valid fields: {sorted(VALID_FIELDS)}")
        return errors

    try:
        _parse_condition(expr)
    except ValueError as e:
        errors.append(str(e))

    return errors


def _get_field_value(paper: Paper, field: str) -> Optional[Any]:
    """Extract a screening field value from a paper."""
    scoring = paper.screening.relevance_scoring
    keyword = paper.screening.keyword_screening
    metadata = paper.screening.metadata_screening

    if field == "relevance_score":
        return scoring.relevance if scoring else None
    elif field == "confidence":
        return scoring.confidence if scoring else None
    elif field == "keyword_passed":
        return keyword.passed if keyword else None
    elif field == "metadata_passed":
        return metadata.passed if metadata else None

    return None


def _evaluate_conditions(paper: Paper, conditions: Dict[str, str]) -> Optional[bool]:
    """Evaluate all conditions against a paper.

    Returns True if all conditions pass, False if any fail,
    None if a required field is missing.
    """
    for field, expr in conditions.items():
        value = _get_field_value(paper, field)
        if value is None:
            return None

        op_fn, threshold = _parse_condition(expr)
        if not op_fn(value, threshold):
            return False

    return True


class DecisionStep(BaseStep):
    """Deterministic final decision based on combined screening signals."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: list[str] = []

        if "include_when" not in config and "exclude_when" not in config:
            errors.append("At least one of 'include_when' or 'exclude_when' is required")
            return False, errors

        for block_key in ("include_when", "exclude_when"):
            block = config.get(block_key)
            if block is None:
                continue
            if not isinstance(block, dict):
                errors.append(f"'{block_key}' must be a mapping of field: condition")
                continue
            for field, expr in block.items():
                if not isinstance(expr, str):
                    errors.append(f"'{block_key}.{field}' condition must be a string, got {type(expr).__name__}")
                else:
                    errors.extend(_validate_condition(field, expr))

        otherwise = config.get("otherwise", "manual_review")
        if otherwise not in ("manual_review", "pending"):
            errors.append("'otherwise' must be 'manual_review' or 'pending'")

        return len(errors) == 0, errors

    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        include_when = step_config.get("include_when", {})
        exclude_when = step_config.get("exclude_when", {})
        otherwise = step_config.get("otherwise", "manual_review")

        otherwise_decision = (
            ScreeningDecision.MANUAL_REVIEW
            if otherwise == "manual_review"
            else ScreeningDecision.PENDING
        )

        def predicate(p: Paper) -> bool:
            # is_excluded covers papers excluded by other mechanisms (e.g.
            # deduplication) that should not be re-evaluated here.
            return (
                p.screening.final_decision
                in (ScreeningDecision.PENDING, ScreeningDecision.UNCERTAIN)
                and not p.is_excluded
            )

        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        stats = {
            "total_papers": paper_count,
            "included": 0,
            "excluded": 0,
            "manual_review": 0,
            "pending": 0,
            "skipped_missing": 0,
        }

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers pending decision",
                step="decision",
                stats=stats,
            )

        for paper in all_papers:
            decision = None

            # Try include conditions first
            if include_when:
                include_result = _evaluate_conditions(paper, include_when)
                if include_result is None:
                    # Missing data for include fields — skip entirely since we
                    # cannot make any determination without the primary signal
                    logger.debug("Paper %s: skipped (missing include data)", paper.cite_key)
                    stats["skipped_missing"] += 1
                    continue
                if include_result is True:
                    decision = ScreeningDecision.INCLUDED

            # Try exclude conditions (only if not already included)
            if decision is None and exclude_when:
                exclude_result = _evaluate_conditions(paper, exclude_when)
                if exclude_result is True:
                    decision = ScreeningDecision.EXCLUDED
                # Missing exclude data is non-fatal: fall through to otherwise
                # (the paper already failed include, so route to fallback)

            # Apply fallback if neither matched
            if decision is None:
                decision = otherwise_decision

            # Persist
            if not dry_run:
                paper.screening.final_decision = decision
                paper.screening.final_decision_by = "automated:decision"
                paper.screening.current_stage = "decision_complete"
                self.db.update(paper)

            if decision == ScreeningDecision.INCLUDED:
                stats["included"] += 1
            elif decision == ScreeningDecision.EXCLUDED:
                stats["excluded"] += 1
            elif decision == ScreeningDecision.MANUAL_REVIEW:
                stats["manual_review"] += 1
            else:
                stats["pending"] += 1

            logger.debug("Paper %s: %s", paper.cite_key, decision.value)

        return StepResult(
            status=StepStatus.SUCCESS,
            message=(
                f"Decision: {stats['included']} included, "
                f"{stats['excluded']} excluded, "
                f"{stats['manual_review']} manual review, "
                f"{stats['skipped_missing']} skipped (missing data)"
            ),
            step="decision",
            stats=stats,
        )
