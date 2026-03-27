"""
Semantic screening step for paper scanner

Performs semantic similarity screening using embeddings.
Compares papers to the research question and makes inclusion decisions
based on semantic relevance.

Outputs semantic screening results to screening.semantic_screening with:
- passed: boolean flag for pass/fail
- similarity_score: cosine similarity to research question (0-1)
- threshold: threshold used for decision
- llm_decision: INCLUDED, EXCLUDED, or MANUAL_REVIEW
- llm_confidence: confidence score
- llm_reasoning: explanation of decision
- metadata: processing timestamp and duration
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np
from scipy.spatial.distance import cosine

from paper_scanner.core.enum import StepStatus

from ..core.enum import ScreeningDecision
from ..core.exceptions import ConfigurationError, StepFatalError
from ..core.models import Paper, ProcessingMetadata, SemanticScreening
from ..core.step_result import StepResult
from .base import BaseStep

# Suppress verbose logging from transformers/sentence-transformers
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


# Class-based step interface (new architecture)
class SemanticScreeningStep(BaseStep):
    """Wrapper for semantic_screening step (legacy function-based)."""

    @staticmethod
    def validate(config):
        """
        Validate semantic_screening step configuration.

        Args:
            config: Step configuration with optional keys:
                - model: str - Sentence transformer model ID (e.g., 'all-mpnet-base-v2')
                - thresholds: dict with keys:
                    - auto_include: float [0-1] - Score >= this triggers INCLUDED
                    - manual_review: float [0-1] - Score in [manual_review, auto_include) triggers MANUAL_REVIEW
                    - auto_exclude: float [0-1] - Score < this triggers EXCLUDED

        Returns:
            Tuple of (is_valid, error_messages)

        Raises:
            Returns error list if:
            - model is not a string
            - thresholds is not a dict
            - any threshold is not a number between 0-1
        """
        errors = []

        # Check model
        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        # Check thresholds
        if "thresholds" in config:
            thresholds = config["thresholds"]
            if not isinstance(thresholds, dict):
                errors.append("'thresholds' must be a dictionary")
            else:
                # Validate threshold values
                for threshold_name in ("auto_include", "manual_review", "auto_exclude"):
                    if threshold_name in thresholds:
                        val = thresholds[threshold_name]
                        if not isinstance(val, (int, float)):
                            errors.append(f"'thresholds.{threshold_name}' must be a number")
                        elif not (0 <= val <= 1):
                            errors.append(f"'thresholds.{threshold_name}' must be between 0 and 1")

        return len(errors) == 0, errors

    def execute(self, config, verbose=False, dry_run=False, debug=False):
        """
        Execute semantic screening step using embedding-based relevance scoring.

        Design Decisions:
        ==================
        - Embedding-based approach captures semantic meaning beyond keywords
        - Uses sentence-transformers for efficient encoding (all-mpnet-base-v2 default)
        - Cosine similarity (0-1 scale) measures relevance to research question
        - Three-tier decision logic: INCLUDED → MANUAL_REVIEW → EXCLUDED

        Priority Logic:
        ===============
        Papers are classified based on similarity score:
        1. Score >= auto_include (default 0.65)     → INCLUDED
        2. Score >= manual_review (default 0.55)    → MANUAL_REVIEW (border cases)
        3. Score < manual_review                     → EXCLUDED

        Note: Unlike keyword_screening, semantic screening doesn't combine with other
        signals - the embedding-based score is the sole decision criterion, as it
        captures holistic relevance.

        Args:
            config: Step configuration with options:
                - model: str (default: "all-mpnet-base-v2") - Sentence transformer model
                - thresholds: dict with keys:
                    - auto_include: float (default: 0.65) - Score >= this → INCLUDED
                    - manual_review: float (default: 0.55) - Threshold for manual review
                    - auto_exclude: float (default: 0.55) - Score < this → EXCLUDED
            verbose: Enable verbose output
            dry_run: Don't actually modify papers
            debug: Enable debug output

        Returns:
            Dictionary with execution results
        """

        research_question = self.general_config.get("research_question", "")
        if not research_question:
            raise ConfigurationError("research_question must be set in project configuration")

        # Get model and thresholds
        model_name = config.get("model", "all-mpnet-base-v2")
        thresholds = config.get("thresholds", {})
        auto_include = thresholds.get("auto_include", 0.65)
        manual_review = thresholds.get("manual_review", 0.55)
        auto_exclude = thresholds.get("auto_exclude", 0.55)

        results = {
            "step": "semantic_screening",
            "total_papers": self.db.count(primary_only=False),
            "screened": 0,
            "included": 0,
            "excluded": 0,
            "manual_review": 0,
            "model": model_name,
            "thresholds": {
                "auto_include": auto_include,
                "manual_review": manual_review,
                "auto_exclude": auto_exclude,
            },
        }

        self.callback(
            f"Model: '{model_name}'\n"
            f" Research question: '{research_question[:80]}...'", debug=True
        )

        # Initialize screener
        try:
            screener = _SemanticScreener(
                research_question=research_question,
                model_name=model_name,
                auto_include_threshold=auto_include,
                manual_review_threshold=manual_review,
                auto_exclude_threshold=auto_exclude,
            )
        except ImportError as e:
            raise StepFatalError(f"Required package {model_name} not installed", e)

        # Screen each paper
        all_papers = self.db.find(
            predicate=lambda p: not p.is_excluded and not p.is_included and not p.screening.semantic_screening,
            primary_only=True
        )
        for i, paper in enumerate(all_papers):

            try:
                semantic_screening, should_include, exclusion_reason = screener.screen_paper(paper)

                if not dry_run:
                    # Set semantic screening in screening model
                    paper.screening.semantic_screening = semantic_screening

                    # Update final decision if not already decided
                    if paper.screening.final_decision in (ScreeningDecision.PENDING, ScreeningDecision.UNCERTAIN):
                        paper.screening.final_decision = semantic_screening.decision
                        paper.screening.final_decision_by = "automated:semantic_screening"

                    paper.screening.current_stage = "semantic_screening_complete"
                    # Update paper in database
                    self.db.update(paper)

                results["screened"] += 1

                if semantic_screening.decision == ScreeningDecision.INCLUDED:
                    results["included"] += 1
                elif semantic_screening.decision == ScreeningDecision.EXCLUDED:
                    results["excluded"] += 1
                elif semantic_screening.decision == ScreeningDecision.MANUAL_REVIEW:
                    results["manual_review"] += 1

            except Exception as e:
                self.cascade(f"[red]✗ Error screening paper {paper.cite_key}: {e}[/red]")

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Semantic screening completed: Included {results['included']}, Excluded {results['excluded']}, Manual Review {results['manual_review']}",
            step="semantic_screening",
            stats=results
        )


class _SemanticScreener:
    """Internal semantic screener using embeddings."""

    def __init__(
        self,
        research_question: str,
        model_name: str = "all-mpnet-base-v2",
        auto_include_threshold: float = 0.65,
        manual_review_threshold: float = 0.55,
        auto_exclude_threshold: float = 0.55,
    ):
        """Initialize semantic screener with research question and similarity thresholds.

        The screener embeds the research question once and reuses that embedding to
        compute similarity for each paper, providing O(1) per-paper screening after
        initial model load.

        Args:
            research_question: The research question text to embed (used as reference)
            model_name: Sentence transformer model ID (e.g., 'all-mpnet-base-v2')
            auto_include_threshold: Similarity score >= this → INCLUDED (should be >= manual_review)
            manual_review_threshold: Papers in [manual_review, auto_include) → MANUAL_REVIEW
            auto_exclude_threshold: Similarity score < this → EXCLUDED (should be <= manual_review)
        """
        self.research_question = research_question
        self.model_name = model_name
        self.auto_include_threshold = auto_include_threshold
        self.manual_review_threshold = manual_review_threshold
        self.auto_exclude_threshold = auto_exclude_threshold

        self.embedding_model = None
        self.rq_embedding = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load embedding model."""
        if self.embedding_model is None:
            if SentenceTransformer is None:
                raise ImportError("sentence-transformers package required for semantic screening")
            # Disable progress bars and verbose output during model download
            import warnings
            warnings.filterwarnings("ignore")
            self.embedding_model = SentenceTransformer(
                self.model_name,
                cache_folder=None,
            )
        return self.embedding_model

    def _get_research_question_embedding(self) -> np.ndarray:
        """Get or compute research question embedding."""
        if self.rq_embedding is None:
            model = self._load_model()
            self.rq_embedding = model.encode(
                self.research_question,
                convert_to_numpy=True,
                show_progress_bar=False
            )
        return self.rq_embedding

    def _compute_paper_embedding(self, title: Optional[str], abstract: Optional[str]) -> np.ndarray:
        """Compute embedding for paper (title + abstract)."""
        model = self._load_model()

        # Combine title and abstract
        title_text = (title or "").strip()
        abstract_text = (abstract or "").strip()
        combined_text = f"{title_text} {abstract_text}".strip()

        if not combined_text:
            combined_text = "No title or abstract"

        return model.encode(combined_text, convert_to_numpy=True, show_progress_bar=False)

    def _compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between embeddings."""
        # Flatten if needed
        if embedding1.ndim > 1:
            embedding1 = embedding1.flatten()
        if embedding2.ndim > 1:
            embedding2 = embedding2.flatten()

        # Cosine similarity = 1 - cosine_distance
        distance = cosine(embedding1, embedding2)
        similarity = 1.0 - distance

        # Clamp to [0, 1]
        return float(max(0.0, min(1.0, similarity)))

    def screen_paper(self, paper: Paper) -> Tuple[SemanticScreening, bool, Optional[str]]:
        """Screen a single paper based on semantic similarity to research question.

        Computes cosine similarity between paper (title + abstract combined) and
        the research question embeddings. Uses similarity thresholds to make
        INCLUDED/EXCLUDED/MANUAL_REVIEW decision.

        Similarity Score Examples (with defaults auto_include=0.65, manual_review=0.55):
        - 0.80: "Cloud computing security frameworks" vs RQ about cloud security → INCLUDED
        - 0.62: "Digital transformation in supply chains" vs RQ about IT adoption → MANUAL_REVIEW
        - 0.35: "Classical philosophy in ancient Greece" vs RQ about IT innovation → EXCLUDED

        Returns:
            Tuple of:
            - SemanticScreening: Result object with score, decision, reasoning
            - should_include: Boolean flag for upstream processing
            - exclusion_reason: Human-readable reason if excluded/manual review
        """
        step_start_time = time.time()

        # Get embeddings
        rq_embedding = self._get_research_question_embedding()
        paper_embedding = self._compute_paper_embedding(paper.title, paper.abstract)

        # Compute similarity
        similarity_score = self._compute_similarity(rq_embedding, paper_embedding)

        # Classify
        should_include = True
        exclusion_reason = None
        decision = ScreeningDecision.PENDING
        reasoning = None

        if similarity_score >= self.auto_include_threshold:
            decision = ScreeningDecision.INCLUDED
            reasoning = f"High semantic similarity ({similarity_score:.4f}) to research question"
        elif similarity_score >= self.manual_review_threshold:
            decision = ScreeningDecision.MANUAL_REVIEW
            reasoning = f"Borderline semantic similarity ({similarity_score:.4f}): manual review recommended"
            should_include = True
        else:
            decision = ScreeningDecision.EXCLUDED
            reasoning = f"Low semantic similarity ({similarity_score:.4f}) to research question"
            should_include = False
            exclusion_reason = reasoning

        duration = time.time() - step_start_time

        # Create result
        semantic_screening = SemanticScreening(
            passed=should_include,
            similarity_score=similarity_score,
            threshold=self.auto_include_threshold,
            decision=decision,
            confidence=similarity_score,
            reason=reasoning,
            metadata=ProcessingMetadata(
                timestamp=datetime.now(timezone.utc),
                duration_seconds=duration,
                model_name=self.model_name,
                success=True
            )
        )

        return semantic_screening, should_include, exclusion_reason


