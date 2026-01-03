"""
LLM-based paper classification step.

Uses Claude to classify papers based on research dimensions defined in general_config.
Classifies papers according to enumerated research dimensions and updates the
SemanticScreening model with classification results.

Configuration options:
  - model: Claude model to use (default: claude-opus-4-20250514)
  - thresholds: dict with keys:
      - auto_include: float [0-1] - Classification confidence >= this triggers INCLUDED
      - manual_review: float [0-1] - Confidence in [manual_review, auto_include) triggers MANUAL_REVIEW
      - auto_exclude: float [0-1] - Confidence < this triggers EXCLUDED

Environment:
  - ANTHROPIC_API_KEY: Anthropic API key (loaded via dotenv at CLI startup)

Example YAML:
  - step: "LLM Classification"
    builtin.llm_classification:
      model: "claude-opus-4-20250514"
      thresholds:
        auto_include: 0.75
        manual_review: 0.55
        auto_exclude: 0.55
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import Paper, ProcessingMetadata, SemanticScreening
from paper_scanner.core.step_result import StepResult
from paper_scanner.models.anthropic import ClaudeHandler

from .base import BaseStep

# Suppress verbose logging
logging.getLogger("anthropic").setLevel(logging.WARNING)


class LLMClassificationStep(BaseStep):
    """LLM-based paper classification using Claude."""

    SYSTEM_PROMPT_TEMPLATE = """You are an expert academic paper classifier. 
Your task is to classify research papers based on predefined research dimensions.

You will be provided with:
1. A research question describing the study scope
2. Research dimensions (classification categories)
3. Paper details (title, abstract, keywords)

For each paper, you must:
1. Determine which research dimensions apply (binary classification)
2. Assign a dominance score (0.0 = not addressed, 0.5 = addressed, 1.0 = dominant)
3. Provide a brief reasoning explaining which dimensions are covered and which are dominant

Output ONLY valid JSON with this structure:
{{
    "classifications": {{
        "dimension_name": {{
            "applies": true/false,
            "dominance": 0.0 or 0.5 or 1.0,
            "reasoning": "Brief explanation"
        }}
    }},
    "overall_decision": "include/exclude/review",
    "summary": "Overall classification summary"
}}

Scoring guide:
- 1.0: Dimension is a PRIMARY FOCUS or explicitly dominant in the paper
- 0.5: Dimension is ADDRESSED or discussed but not dominant
- 0.0: Dimension is NOT addressed or not relevant to this paper

Be strict and only score dimensions that clearly apply to the paper."""

    @staticmethod
    def validate(config: Dict) -> Tuple[bool, List[str]]:
        """
        Validate LLM classification configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check model (optional)
        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        # Check thresholds (optional)
        if "thresholds" in config:
            thresholds = config["thresholds"]
            if not isinstance(thresholds, dict):
                errors.append("'thresholds' must be a dictionary")
            else:
                for threshold_name in ("auto_include", "manual_review", "auto_exclude"):
                    if threshold_name in thresholds:
                        val = thresholds[threshold_name]
                        if not isinstance(val, (int, float)):
                            errors.append(f"'thresholds.{threshold_name}' must be a number")
                        elif not (0 <= val <= 1):
                            errors.append(f"'thresholds.{threshold_name}' must be between 0 and 1")

        return len(errors) == 0, errors

    def execute(self, config: Dict, verbose: bool = False, dry_run: bool = False, debug: bool = False) -> Dict:
        """
        Execute LLM classification step.

        Args:
            config: Step configuration with options:
                - model: str (default: "claude-opus-4-20250514")
                - thresholds: dict with auto_include, manual_review, auto_exclude
            verbose: Enable verbose output
            dry_run: Don't actually modify papers
            debug: Enable debug output

        Returns:
            StepResult with execution results
        """
        # Get research question and dimensions from general config
        research_question = self.general_config.get("research_question", "")
        research_dimensions = self.general_config.get("research_dimensions", [])

        if not research_question:
            raise ConfigurationError("research_question must be set in project configuration")

        if not research_dimensions:
            raise ConfigurationError("research_dimensions must be set in project configuration")

        # Get model and thresholds
        model_name = config.get("model", "claude-opus-4-20250514")
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY environment variable is not set")

        thresholds = config.get("thresholds", {})
        auto_include = thresholds.get("auto_include", 0.75)
        manual_review = thresholds.get("manual_review", 0.55)
        auto_exclude = thresholds.get("auto_exclude", 0.55)

        results = {
            "step": "llm_classification",
            "total_papers": self.db.count(primary_only=False),
            "classified": 0,
            "included": 0,
            "excluded": 0,
            "manual_review": 0,
            "model": model_name,
            "thresholds": {
                "auto_include": auto_include,
                "manual_review": manual_review,
                "auto_exclude": auto_exclude,
            },
            "research_dimensions": len(research_dimensions),
            "total_cost": 0.0,
            "total_tokens": 0,
        }

        self.callback(
            f"Model: '{model_name}'\n"
            f"Research question: '{research_question[:80]}...'\n"
            f"Dimensions: {len(research_dimensions)}",
            debug=True,
        )

        # Initialize classifier
        try:
            classifier = _LLMClassifier(
                research_question=research_question,
                research_dimensions=research_dimensions,
                model_name=model_name,
                api_key=api_key,
                auto_include_threshold=auto_include,
                manual_review_threshold=manual_review,
                auto_exclude_threshold=auto_exclude,
            )
        except Exception as e:
            raise StepFatalError(f"Failed to initialize LLM classifier: {e}", e)

        def predicate(p: Paper) -> bool:
            """Predicate to select papers needing classification."""
            return p.screening.final_decision not in [ScreeningDecision.INCLUDED, ScreeningDecision.EXCLUDED]

        # Classify papers
        all_papers = self.db.find(predicate=predicate, primary_only=True)

        paper_count = len(all_papers)

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers to classify",
                step="llm_classification",
                stats=results,
            )

        for i, paper in enumerate(all_papers, 1):
            if i % 10 == 1:
                self.callback(f"Classifying paper {i}/{paper_count}: {paper.cite_key}")

            semantic_screening, raw_data = classifier.classify_paper(paper)

            if not dry_run:
                # Set semantic screening in screening model
                paper.screening.semantic_screening = semantic_screening

                # Update final decision if not already decided
                if paper.screening.final_decision in (ScreeningDecision.PENDING, ScreeningDecision.UNCERTAIN):
                    paper.screening.final_decision = semantic_screening.decision
                    paper.screening.final_decision_by = "automated:llm_classification"

                paper.screening.current_stage = "llm_classification_complete"

                # Update paper in database
                self.db.update(paper)

            results["classified"] += 1

            if semantic_screening.decision == ScreeningDecision.INCLUDED:
                results["included"] += 1
            elif semantic_screening.decision == ScreeningDecision.EXCLUDED:
                results["excluded"] += 1
            elif semantic_screening.decision == ScreeningDecision.MANUAL_REVIEW:
                results["manual_review"] += 1

            # Track tokens and cost
            if raw_data.get("token_usage"):
                results["total_tokens"] += raw_data["token_usage"].get("output_tokens", 0)
                # Haiku costs roughly $0.80 per million input tokens, $2.40 per million output tokens
                results["total_cost"] += (raw_data["token_usage"].get("output_tokens", 0) / 1_000_000) * 2.40

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"LLM classification completed: Included {results['included']}, Excluded {results['excluded']}, Manual Review {results['manual_review']}",
            step="llm_classification",
            stats=results,
        )


class _LLMClassifier:
    """Internal LLM classifier using Claude."""

    def __init__(
        self,
        research_question: str,
        research_dimensions: List[str],
        model_name: str = "claude-opus-4-20250514",
        api_key: Optional[str] = None,
        auto_include_threshold: float = 0.75,
        manual_review_threshold: float = 0.55,
        auto_exclude_threshold: float = 0.55,
    ):
        """Initialize the LLM classifier."""
        self.research_question = research_question
        self.research_dimensions = research_dimensions
        self.model_name = model_name
        self.auto_include_threshold = auto_include_threshold
        self.manual_review_threshold = manual_review_threshold
        self.auto_exclude_threshold = auto_exclude_threshold

        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.claude = ClaudeHandler(api_key=api_key, model=model_name)

    def _format_paper_text(self, paper: Paper) -> str:
        """Format paper details for LLM input."""
        lines = []

        if paper.title:
            lines.append(f"TITLE: {paper.title}")

        if paper.abstract:
            lines.append(f"ABSTRACT: {paper.abstract}")

        if paper.keywords:
            keywords_str = ", ".join(paper.keywords) if isinstance(paper.keywords, list) else str(paper.keywords)
            lines.append(f"KEYWORDS: {keywords_str}")

        if paper.year:
            lines.append(f"YEAR: {paper.year}")

        if paper.authors and len(paper.authors) > 0:
            author_names = [a.full_name if hasattr(a, "full_name") else str(a) for a in paper.authors[:5]]
            authors_str = ", ".join(author_names)
            if len(paper.authors) > 5:
                authors_str += f", and {len(paper.authors) - 5} more"
            lines.append(f"AUTHORS: {authors_str}")

        return "\n".join(lines)

    def _build_prompt(self, paper: Paper) -> str:
        """Build the classification prompt for a single paper."""
        dimensions_text = "\n".join(f"- {i + 1}. {dim}" for i, dim in enumerate(self.research_dimensions))

        paper_text = self._format_paper_text(paper)

        prompt = f"""RESEARCH QUESTION:
{self.research_question}

RESEARCH DIMENSIONS (Classification Categories):
{dimensions_text}

PAPER TO CLASSIFY:
{paper_text}

Please classify this paper according to the research dimensions listed above."""

        return prompt

    def classify_paper(self, paper: Paper, max_tokens: int = 1024) -> Tuple[SemanticScreening, Dict]:
        """
        Classify a single paper.

        Returns:
            Tuple of (SemanticScreening model, raw classification dict)
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Build prompt
            prompt = self._build_prompt(paper)

            # Call Claude
            parsed_response, token_usage = self.claude.call(
                text=prompt,
                system_prompt=LLMClassificationStep.SYSTEM_PROMPT_TEMPLATE,
                max_tokens=max_tokens,
            )

            if not parsed_response:
                raise ValueError("Claude API returned no response")

            # Extract classification results
            classifications = parsed_response.get("classifications", {})
            overall_decision_str = parsed_response.get("overall_decision", "review").lower()
            summary = parsed_response.get("summary", "")

            # Build classification vector and labels
            # Vector uses: 0.0 (not addressed), 0.5 (addressed), 1.0 (dominant)
            classification_vector = []
            classification_labels = []
            applies_count = 0
            dominant_count = 0

            for dimension in self.research_dimensions:
                if dimension in classifications:
                    dim_data = classifications[dimension]
                    # Use dominance score if available, otherwise fall back to confidence
                    dominance = float(dim_data.get("dominance", dim_data.get("confidence", 0.0)))
                    applies = dim_data.get("applies", False)

                    # Normalize dominance to be one of: 0.0, 0.5, 1.0
                    if dominance >= 0.75:
                        dominance = 1.0
                        dominant_count += 1
                    elif dominance >= 0.25:
                        dominance = 0.5
                    else:
                        dominance = 0.0

                    classification_vector.append(dominance)

                    if applies or dominance > 0.0:
                        classification_labels.append(dimension)
                        applies_count += 1
                else:
                    classification_vector.append(0.0)

            # Determine decision based on average dominance score
            avg_confidence = sum(classification_vector) / len(classification_vector) if classification_vector else 0.0

            if overall_decision_str == "include" or avg_confidence >= self.auto_include_threshold:
                decision = ScreeningDecision.INCLUDED
            elif overall_decision_str == "exclude" or avg_confidence < self.auto_exclude_threshold:
                decision = ScreeningDecision.EXCLUDED
            else:
                decision = ScreeningDecision.MANUAL_REVIEW

            # Create SemanticScreening result
            metadata = ProcessingMetadata(
                timestamp=start_time,
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                model_name=self.model_name,
                tokens_used=token_usage.get("output_tokens", 0),
                success=True,
            )

            screening_result = SemanticScreening(
                passed=decision != ScreeningDecision.EXCLUDED,
                similarity_score=avg_confidence,
                threshold=self.auto_include_threshold,
                classification_vector=classification_vector,
                classification_labels=classification_labels,
                classification=overall_decision_str,
                decision=decision,
                confidence=avg_confidence,
                reason=summary,
                metadata=metadata,
            )

            raw_data = {
                "classifications": classifications,
                "overall_decision": overall_decision_str,
                "summary": summary,
                "classification_vector": classification_vector,
                "classification_labels": classification_labels,
                "applies_count": applies_count,
                "dominant_count": dominant_count,
                "dimension_count": len(self.research_dimensions),
                "token_usage": token_usage,
            }

            return screening_result, raw_data

        except Exception as e:
            # Return a failed classification
            metadata = ProcessingMetadata(
                timestamp=start_time,
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                model_name=self.model_name,
                success=False,
                error=str(e),
            )

            screening_result = SemanticScreening(
                passed=False,
                similarity_score=0.0,
                threshold=self.auto_include_threshold,
                classification_vector=[],
                classification_labels=[],
                classification="error",
                decision=ScreeningDecision.MANUAL_REVIEW,
                confidence=0.0,
                reason=f"Classification error: {e}",
                metadata=metadata,
            )

            return screening_result, {"error": str(e), "token_usage": {}}
