"""
Semantic Classification Step using Adaptive Rocchio Algorithm

Implements adaptive semantic screening with persistent centroid-based classification.
Unlike static semantic screening, this step maintains centroids of accepted/rejected papers
that evolve across iterations, enabling adaptive decision boundaries.

State is stored in executor.step_state to persist between steps within a session.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from paper_scanner.core.enum import ScreeningDecision, StepStatus
from paper_scanner.core.exceptions import ConfigurationError, StepFatalError
from paper_scanner.core.models import ProcessingMetadata, SemanticScreening
from paper_scanner.core.rocchio import AdaptiveRocchioScreener, ScreeningState
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


class SemanticClassificationStep(BaseStep):
    """
    Semantic classification step using Adaptive Rocchio Algorithm.

    Maintains persistent centroid vectors for accepted/rejected papers that evolve
    as more papers are labeled. Enables adaptive decision boundaries across iterations.

    State is stored in executor.step_state, persisting between steps within a session
    but clearing on explicit reset().
    """

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, list]:
        """
        Validate semantic_classification step configuration.

        Args:
            config: Step configuration with optional keys:
                - model: str - Sentence transformer model ID (e.g., 'specter2')
                - rocchio_weights: dict with keys 'alpha', 'beta', 'gamma'
                - thresholds: dict with keys 'accept', 'reject'
                - initialize_from_keyword_screening: bool - Bootstrap from keyword labels

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check model
        if "model" in config and not isinstance(config["model"], str):
            errors.append("'model' must be a string")

        # Check rocchio_weights
        if "rocchio_weights" in config:
            weights = config["rocchio_weights"]
            if not isinstance(weights, dict):
                errors.append("'rocchio_weights' must be a dictionary")
            else:
                for weight_name in ("alpha", "beta", "gamma"):
                    if weight_name in weights:
                        val = weights[weight_name]
                        if not isinstance(val, (int, float)):
                            errors.append(
                                f"'rocchio_weights.{weight_name}' must be a number"
                            )
                        elif val < 0:
                            errors.append(
                                f"'rocchio_weights.{weight_name}' must be non-negative"
                            )

        # Check thresholds
        if "thresholds" in config:
            thresholds = config["thresholds"]
            if not isinstance(thresholds, dict):
                errors.append("'thresholds' must be a dictionary")
            else:
                for threshold_name in ("accept", "reject"):
                    if threshold_name in thresholds:
                        val = thresholds[threshold_name]
                        if not isinstance(val, (int, float)):
                            errors.append(f"'thresholds.{threshold_name}' must be a number")
                        elif not (0 <= val <= 1):
                            errors.append(
                                f"'thresholds.{threshold_name}' must be between 0 and 1"
                            )

        # Check initialize_from_keyword_screening
        if "initialize_from_keyword_screening" in config:
            if not isinstance(config["initialize_from_keyword_screening"], bool):
                errors.append("'initialize_from_keyword_screening' must be a boolean")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> StepResult:
        """
        Execute semantic classification using Adaptive Rocchio.

        Flow:
        1. Load or create ScreeningState from executor.step_state
        2. Initialize embedder model
        3. Embed research question (if not already done)
        4. Optionally bootstrap centroids from keyword_screening results
        5. Classify papers iteratively, updating centroids
        6. Store updated state back to executor.step_state

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't modify papers
            debug: Enable debug output

        Returns:
            StepResult with status, message, and stats
        """

        research_question = self.general_config.get("research_question", "")
        if not research_question:
            raise ConfigurationError(
                "research_question must be set in project configuration"
            )

        # Get configuration
        model_name = config.get("model", "specter2")
        rocchio_weights = config.get("rocchio_weights", {})
        thresholds = config.get("thresholds", {})
        initialize_from_keyword = config.get("initialize_from_keyword_screening", True)

        alpha = rocchio_weights.get("alpha", 1.0)
        beta = rocchio_weights.get("beta", 0.75)
        gamma = rocchio_weights.get("gamma", 0.15)
        accept_threshold = thresholds.get("accept", 0.7)
        reject_threshold = thresholds.get("reject", 0.3)

        results = {
            "step": "semantic_classification",
            "total_papers": self.db.count(primary_only=False),
            "classified": 0,
            "accepted": 0,
            "rejected": 0,
            "uncertain": 0,
            "model": model_name,
            "rocchio_weights": {"alpha": alpha, "beta": beta, "gamma": gamma},
            "thresholds": {"accept": accept_threshold, "reject": reject_threshold},
            "centroids_initialized": False,
        }

        self.callback(
            f"Model: '{model_name}'\n"
            f"Research question: '{research_question[:80]}...'",
            debug=True
        )

        # Initialize embedder
        try:
            embedder = SentenceTransformer(model_name)
        except ImportError as e:
            raise StepFatalError(f"Required package not installed: {e}", e)
        except Exception as e:
            raise StepFatalError(f"Failed to load model '{model_name}': {e}", e)

        embedding_dim = embedder.get_sentence_embedding_dimension()

        # Load or create screening state from executor.step_state
        state_key = "semantic_classification_rocchio_state"
        if state_key in self.executor.step_state:
            state_dict = self.executor.step_state[state_key]
            state = ScreeningState.from_dict(state_dict)
            self.callback("Loaded existing Rocchio state from executor", debug=True)
        else:
            state = ScreeningState(
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                accept_threshold=accept_threshold,
                reject_threshold=reject_threshold,
            )
            self.callback("Created new Rocchio state", debug=True)

        # Initialize screener
        screener = AdaptiveRocchioScreener(embedding_dim, state)

        # Embed research question (if not already done)
        if screener.state.query_centroid is None:
            self.callback("Embedding research question...", debug=True)
            rq_embedding = embedder.encode(research_question, convert_to_numpy=True)
            screener.initialize_from_research_question(rq_embedding)
            self.callback(f"Research question embedding shape: {rq_embedding.shape}", debug=True)

        # Optionally bootstrap from keyword_screening results
        if (
            initialize_from_keyword
            and screener.state.count_relevant == 0
            and screener.state.count_irrelevant == 0
        ):
            self.callback("Bootstrapping centroids from keyword_screening results...", debug=True)
            accepted_embeddings = []
            rejected_embeddings = []

            all_papers = self.db.all(primary_only=True)
            for paper in all_papers:
                if paper.screening.keyword_screening:
                    if paper.screening.keyword_screening.passed:
                        # This paper passed keyword screening (accepted)
                        abstract = paper.abstract or paper.title or ""
                        if abstract:
                            emb = embedder.encode(abstract, convert_to_numpy=True)
                            accepted_embeddings.append(emb)
                    else:
                        # This paper failed keyword screening (rejected)
                        abstract = paper.abstract or paper.title or ""
                        if abstract:
                            emb = embedder.encode(abstract, convert_to_numpy=True)
                            rejected_embeddings.append(emb)

            if accepted_embeddings or rejected_embeddings:
                screener.bootstrap_from_seeds(accepted_embeddings, rejected_embeddings)
                self.callback(
                    f"Bootstrapped with {len(accepted_embeddings)} accepted, "
                    f"{len(rejected_embeddings)} rejected papers",
                    debug=True
                )
                results["centroids_initialized"] = True
            else:
                self.callback(
                    "No keyword_screening results found for bootstrapping. "
                    "Using research question embedding only.",
                    debug=True
                )

        # Classify papers
        all_papers = self.db.find(
            predicate=lambda p: not p.screening.semantic_screening,
            primary_only=True
        )

        self.callback(f"Classifying {len(all_papers)} papers...", debug=True)

        for i, paper in enumerate(all_papers):
            try:
                # Get abstract or title for embedding
                text = paper.abstract or paper.title or ""
                if not text:
                    self.callback(f"Skipping {paper.cite_key}: no abstract or title", debug=True)
                    continue

                # Embed and classify
                embedding = embedder.encode(text, convert_to_numpy=True)
                classification = screener.classify(embedding)

                # Create SemanticScreening result
                decision_map = {
                    "ACCEPT": ScreeningDecision.INCLUDED,
                    "REJECT": ScreeningDecision.EXCLUDED,
                    "UNCERTAIN": ScreeningDecision.UNCERTAIN,
                }

                semantic_screening = SemanticScreening(
                    passed=classification["decision"] in ("ACCEPT", "UNCERTAIN"),
                    similarity_score=classification["score"],
                    threshold=(
                        accept_threshold
                        if classification["decision"] == "ACCEPT"
                        else reject_threshold
                    ),
                    decision=decision_map[classification["decision"]],
                    confidence=classification["score"],
                    reason=(
                        f"Rocchio score: {classification['score']:.3f}. "
                        f"Accept threshold: {accept_threshold}, Reject threshold: {reject_threshold}"
                    ),
                    metadata=ProcessingMetadata(
                        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        duration=0,
                    ),
                )

                if not dry_run:
                    # Update paper with semantic screening result
                    paper.screening.semantic_screening = semantic_screening

                    # Update final decision if not already decided
                    if paper.screening.final_decision == ScreeningDecision.PENDING:
                        paper.screening.final_decision = semantic_screening.decision
                        paper.screening.final_decision_by = "automated:semantic_classification"

                    paper.screening.current_stage = "semantic_classification_complete"
                    self.db.update(paper)

                # Update centroid if paper has been manually labeled
                # (This would be integrated with a user feedback mechanism)

                results["classified"] += 1
                if classification["decision"] == "ACCEPT":
                    results["accepted"] += 1
                elif classification["decision"] == "REJECT":
                    results["rejected"] += 1
                else:
                    results["uncertain"] += 1

                if verbose and (i + 1) % 10 == 0:
                    self.callback(f"Classified {i + 1}/{len(all_papers)} papers", debug=False)

            except Exception as e:
                self.callback(f"[red]✗ Error classifying paper {paper.cite_key}: {e}[/red]")

        # Save state back to executor for next iteration
        if not dry_run:
            updated_state = screener.get_state()
            self.executor.step_state[state_key] = updated_state.to_dict()
            self.callback(
                f"Saved Rocchio state: iteration={updated_state.iteration}, "
                f"relevant_count={updated_state.count_relevant}, "
                f"irrelevant_count={updated_state.count_irrelevant}",
                debug=True
            )

        return StepResult(
            status=StepStatus.SUCCESS,
            message=(
                f"Semantic classification completed: "
                f"Accepted {results['accepted']}, "
                f"Rejected {results['rejected']}, "
                f"Uncertain {results['uncertain']}"
            ),
            step="semantic_classification",
            stats=results
        )
