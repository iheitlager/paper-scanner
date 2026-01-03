"""
Rocchio-based classifier using research dimensions as separate centroids.

Classifies papers based on semantic similarity to each research dimension.
Each dimension becomes its own centroid in embedding space, enabling multi-dimensional
classification with dominant dimension identification.

Classification decisions:
  - EXCLUDED: No dimensions exceed similarity threshold
  - INCLUDED: Exactly one dimension above threshold (clear dominant dimension)
  - MANUAL_REVIEW: Multiple dimensions above threshold (uncertain which is dominant)

Updates SemanticScreening with:
  - classification_vector: Similarity scores for each dimension
  - classification_labels: List of applicable dimensions
  - classification: "excluded" | "included" | "uncertain"
  - decision: ScreeningDecision enum value
  - confidence: Normalized confidence score

Configuration options:
  - model: Sentence transformer model ID (default: "all-mpnet-base-v2")
    Options: "specter2", "sciBERT", "all-mpnet-base-v2", "all-MiniLM-L6-v2"
  
  - dimension_threshold: float [0-1] - Similarity threshold for dimension applicability
    (default: 0.5)
  
  - initialize_from_research_question: bool - Initialize centroids from research question
    if no training data available (default: true)

Example YAML:
  - step: "Rocchio Classification"
    builtin.rocchio_classifier:
      model: "all-mpnet-base-v2"
      dimension_threshold: 0.5
      initialize_from_research_question: true
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import Paper, ProcessingMetadata, SemanticScreening
from paper_scanner.core.step_result import StepResult

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

import numpy as np


class RocchioClassifierStep(BaseStep):
    """
    Rocchio-based classifier using research dimensions as separate centroids.

    Each research dimension is treated as a separate centroid in embedding space.
    Papers are classified based on their semantic similarity to each dimension.

    Classification outcomes:
    - EXCLUDED: Paper not relevant to any dimension (no similarities above threshold)
    - INCLUDED: Paper clearly relevant to exactly one dimension
    - MANUAL_REVIEW: Paper relevant to multiple dimensions (needs human decision on dominance)
    """

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate rocchio_classifier configuration.

        Args:
            config: Step configuration with optional keys:
                - model: str - Sentence transformer model ID (default: "all-mpnet-base-v2")
                - dimension_threshold: float [0-1] - Similarity threshold (default: 0.5)
                - initialize_from_research_question: bool - Use RQ for initialization (default: true)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate model
        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        # Validate dimension_threshold
        if "dimension_threshold" in config:
            threshold = config["dimension_threshold"]
            if not isinstance(threshold, (int, float)):
                errors.append("'dimension_threshold' must be a number")
            elif not (0 <= threshold <= 1):
                errors.append("'dimension_threshold' must be between 0 and 1")

        # Validate initialize_from_research_question
        if "initialize_from_research_question" in config:
            if not isinstance(config["initialize_from_research_question"], bool):
                errors.append("'initialize_from_research_question' must be a boolean")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict:
        """
        Execute Rocchio classification step.

        Args:
            config: Step configuration with:
                - model: Sentence transformer model (default: "all-mpnet-base-v2")
                - dimension_threshold: Similarity threshold (default: 0.5)
                - initialize_from_research_question: bool (default: true)
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

        # Get configuration parameters
        model_name = config.get("model", "all-mpnet-base-v2")
        dimension_threshold = config.get("dimension_threshold", 0.5)
        initialize_from_rq = config.get("initialize_from_research_question", True)

        results = {
            "step": "rocchio_classifier",
            "total_papers": self.db.count(primary_only=False),
            "classified": 0,
            "included": 0,
            "excluded": 0,
            "manual_review": 0,
            "model": model_name,
            "dimension_threshold": dimension_threshold,
            "dimensions": len(research_dimensions),
        }

        self.callback(
            f"Model: '{model_name}'\n"
            f"Research question: '{research_question[:80]}...'\n"
            f"Dimensions: {len(research_dimensions)}\n"
            f"Threshold: {dimension_threshold}",
            debug=True,
        )

        # Initialize classifier
        try:
            classifier = _RocchioClassifier(
                research_question=research_question,
                research_dimensions=research_dimensions,
                model_name=model_name,
                initialize_from_rq=initialize_from_rq,
            )
        except Exception as e:
            raise StepFatalError(f"Failed to initialize Rocchio classifier: {e}", e)

        def predicate(p: Paper) -> bool:
            """Classify papers that haven't been decided yet."""
            return p.screening.final_decision not in [
                ScreeningDecision.INCLUDED,
                ScreeningDecision.EXCLUDED,
            ]

        # Classify papers
        all_papers = self.db.find(predicate=predicate, primary_only=True)
        paper_count = len(all_papers)

        if paper_count == 0:
            return StepResult(
                status=StepStatus.SUCCESS,
                message="No papers to classify",
                step="rocchio_classifier",
                stats=results,
            )

        for i, paper in enumerate(all_papers, 1):
            if i % 10 == 1:
                self.callback(f"Classifying paper {i}/{paper_count}: {paper.cite_key}")

            semantic_screening, raw_data = classifier.classify_paper(
                paper, dimension_threshold=dimension_threshold
            )

            if not dry_run:
                # Set semantic screening in screening model
                paper.screening.semantic_screening = semantic_screening

                # Update final decision if not already decided
                if paper.screening.final_decision in (
                    ScreeningDecision.PENDING,
                    ScreeningDecision.UNCERTAIN,
                ):
                    paper.screening.final_decision = semantic_screening.decision
                    paper.screening.final_decision_by = "automated:rocchio_classifier"

                paper.screening.current_stage = "rocchio_classifier_complete"

                # Update paper in database
                self.db.update(paper)

            results["classified"] += 1

            if semantic_screening.decision == ScreeningDecision.INCLUDED:
                results["included"] += 1
            elif semantic_screening.decision == ScreeningDecision.EXCLUDED:
                results["excluded"] += 1
            elif semantic_screening.decision == ScreeningDecision.MANUAL_REVIEW:
                results["manual_review"] += 1

        return StepResult(
            status=StepStatus.SUCCESS,
            message=f"Rocchio classification completed: Included {results['included']}, Excluded {results['excluded']}, Manual Review {results['manual_review']}",
            step="rocchio_classifier",
            stats=results,
        )


class _RocchioClassifier:
    """Internal Rocchio classifier using dimension centroids."""

    def __init__(
        self,
        research_question: str,
        research_dimensions: List[str],
        model_name: str = "all-mpnet-base-v2",
        initialize_from_rq: bool = True,
    ):
        """
        Initialize Rocchio classifier.

        Args:
            research_question: Research question for context
            research_dimensions: List of dimension names (each becomes a centroid)
            model_name: Sentence transformer model to use
            initialize_from_rq: Initialize centroids from research question
        """
        self.research_question = research_question
        self.research_dimensions = research_dimensions
        self.model_name = model_name
        self.initialize_from_rq = initialize_from_rq

        # Load embedding model
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers not available. "
                "Install with: pip install sentence-transformers"
            )

        try:
            self.embedder = SentenceTransformer(model_name)
        except Exception as e:
            raise StepFatalError(f"Failed to load embedding model '{model_name}': {e}", e)

        # Initialize dimension centroids
        self.dimension_centroids: Dict[str, Optional[List[float]]] = {
            dim: None for dim in research_dimensions
        }
        self.dimension_paper_counts: Dict[str, int] = {dim: 0 for dim in research_dimensions}

        self._initialize_embedding()

    def _initialize_embedding(self):
        """Initialize centroids from research question + dimension name."""
        for dimension in self.research_dimensions:
            text = f"{dimension}."
            if self.initialize_from_rq:
                text = f"{self.research_question}. {text}"
            embedding = self.compute_embedding(text)
            self.dimension_centroids[dimension] = embedding

    def compute_embedding(self, text: str) -> List[float]:
        """
        Compute embedding for text.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        if not text or not text.strip():
            # Return zero vector if text is empty (768 dimensions)
            return [0.0] * 768

        embedding = self.embedder.encode(text, convert_to_numpy=True).tolist()
        return embedding

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score [0-1]
        """
        if not vec1 or not vec2:
            return 0.0

        vec1_arr = np.array(vec1)
        vec2_arr = np.array(vec2)

        mag1 = np.linalg.norm(vec1_arr)
        mag2 = np.linalg.norm(vec2_arr)

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return float(np.dot(vec1_arr, vec2_arr) / (mag1 * mag2))

    def classify_paper(
        self,
        paper: Paper,
        dimension_threshold: float = 0.5,
    ) -> Tuple[SemanticScreening, Dict]:
        """
        Classify a paper using dimension centroids.

        Args:
            paper: Paper to classify
            dimension_threshold: Similarity threshold for dimension applicability

        Returns:
            Tuple of (SemanticScreening, raw_data dict)
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get paper text
            paper_text = f"{paper.title or ''} {paper.abstract or ''}".strip()
            if not paper_text:
                paper_text = paper.title or ""

            # Compute paper embedding
            paper_embedding = self.compute_embedding(paper_text)

            # Compute similarity to each dimension centroid
            dimension_similarities: Dict[str, float] = {}
            for dimension in self.research_dimensions:
                centroid = self.dimension_centroids[dimension]
                if centroid is not None:
                    similarity = self._cosine_similarity(paper_embedding, centroid)
                    dimension_similarities[dimension] = similarity
                else:
                    dimension_similarities[dimension] = 0.0

            # Determine which dimensions apply
            applicable_dimensions = [
                dim
                for dim, sim in dimension_similarities.items()
                if sim >= dimension_threshold
            ]

            # Determine dominant dimension
            dominant_dimension = None
            max_similarity = 0.0
            if applicable_dimensions:
                dominant_dimension = max(
                    applicable_dimensions, key=lambda d: dimension_similarities[d]
                )
                max_similarity = dimension_similarities[dominant_dimension]

            # Make classification decision
            if len(applicable_dimensions) == 0:
                # No dimensions apply
                decision = ScreeningDecision.EXCLUDED
                classification = "excluded"
                confidence = min(1.0, 1.0 - max(dimension_similarities.values()))
                passed = False
            elif len(applicable_dimensions) == 1:
                # Exactly one dimension applies
                decision = ScreeningDecision.INCLUDED
                classification = "included"
                confidence = min(1.0, max_similarity)
                passed = True
            else:
                # Multiple dimensions apply
                decision = ScreeningDecision.MANUAL_REVIEW
                classification = "uncertain"
                confidence = min(1.0, max_similarity)
                passed = False

            # Build classification vector
            classification_vector = [
                dimension_similarities.get(dim, 0.0) for dim in self.research_dimensions
            ]

            # Metadata
            metadata = ProcessingMetadata(
                timestamp=start_time,
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                model_name=self.model_name,
                success=True,
            )

            # Create SemanticScreening result
            screening_result = SemanticScreening(
                passed=passed,
                similarity_score=max_similarity,
                threshold=dimension_threshold,
                classification_vector=classification_vector,
                classification_labels=applicable_dimensions,
                classification=classification,
                decision=decision,
                confidence=confidence,
                reason=f"Rocchio: {dominant_dimension or 'none'} (sim={max_similarity:.3f})",
                metadata=metadata,
            )

            # Raw data for debugging
            raw_data = {
                "dimension_similarities": dimension_similarities,
                "applicable_dimensions": applicable_dimensions,
                "dominant_dimension": dominant_dimension,
                "max_similarity": max_similarity,
            }

            return screening_result, raw_data

        except Exception as e:
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
                threshold=0.5,
                classification_vector=[],
                classification_labels=[],
                classification="error",
                decision=ScreeningDecision.MANUAL_REVIEW,
                confidence=0.0,
                reason=f"Classification error: {e}",
                metadata=metadata,
            )

            return screening_result, {"error": str(e)}
