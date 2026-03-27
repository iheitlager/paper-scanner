"""
Adaptive Rocchio Algorithm implementation for semantic classification.

Implements persistent centroid-based classification with incremental
centroid updates, enabling adaptive decision boundaries across iterations.
"""

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np


@dataclass
class ScreeningState:
    """Persistent state for the adaptive Rocchio screener.

    Stores centroids and metadata for incremental updates and
    decision boundary evolution across iterations.
    """

    # Centroids (the key persistent vectors)
    centroid_relevant: Optional[list] = None  # Stored as list for JSON serialization
    centroid_irrelevant: Optional[list] = None
    query_centroid: Optional[list] = None

    # Counts for incremental centroid computation
    count_relevant: int = 0
    count_irrelevant: int = 0

    # Rocchio weights
    alpha: float = 1.0  # Weight for original query
    beta: float = 0.75  # Weight for relevant centroid
    gamma: float = 0.15  # Weight for irrelevant centroid

    # Thresholds for decision making
    accept_threshold: float = 0.7
    reject_threshold: float = 0.3

    # Iteration tracking
    iteration: int = 0

    def to_dict(self) -> dict:
        """Convert state to dict for storage in executor.step_state."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScreeningState":
        """Create state from dict stored in executor.step_state."""
        return cls(**data)


class AdaptiveRocchioScreener:
    """
    Adaptive Rocchio-based classifier using persistent centroids.

    Maintains centroid vectors for relevant/irrelevant papers that
    evolve as new labeled papers are encountered. Computes dynamic
    decision boundaries based on weighted combination of:
    - Original research question embedding
    - Centroid of accepted papers
    - Centroid of rejected papers

    Formula:
        score = sim(doc, α·q + β·centroid_relevant - γ·centroid_irrelevant)

    where α, β, γ are Rocchio weights (typically 1.0, 0.75, 0.15).
    """

    def __init__(self, embedding_dim: int, state: Optional[ScreeningState] = None):
        """
        Initialize screener with optional loaded state.

        Args:
            embedding_dim: Dimension of embedding vectors
            state: Optional ScreeningState to restore from previous session
        """
        self.embedding_dim = embedding_dim
        self.state = state or ScreeningState()

        # Convert list centroids back to numpy arrays
        if self.state.centroid_relevant is not None:
            self.state.centroid_relevant = np.array(self.state.centroid_relevant)
        if self.state.centroid_irrelevant is not None:
            self.state.centroid_irrelevant = np.array(self.state.centroid_irrelevant)
        if self.state.query_centroid is not None:
            self.state.query_centroid = np.array(self.state.query_centroid)

    def initialize_from_research_question(self, research_question_embedding: np.ndarray) -> None:
        """
        Initialize query centroid from research question embedding.

        Args:
            research_question_embedding: Embedding vector of research question
        """
        if research_question_embedding.shape[0] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {research_question_embedding.shape[0]}"
            )
        self.state.query_centroid = research_question_embedding.copy()

    def bootstrap_from_seeds(
        self,
        accepted_embeddings: list[np.ndarray],
        rejected_embeddings: list[np.ndarray]
    ) -> None:
        """
        Bootstrap centroids from seed labeled papers.

        Computes initial centroid of relevant and irrelevant papers.
        This is typically called after keyword_screening provides initial labels.

        Args:
            accepted_embeddings: List of embedding vectors for accepted papers
            rejected_embeddings: List of embedding vectors for rejected papers
        """
        # Initialize relevant centroid
        if accepted_embeddings:
            self.state.centroid_relevant = np.mean(accepted_embeddings, axis=0)
            self.state.count_relevant = len(accepted_embeddings)

        # Initialize irrelevant centroid
        if rejected_embeddings:
            self.state.centroid_irrelevant = np.mean(rejected_embeddings, axis=0)
            self.state.count_irrelevant = len(rejected_embeddings)

    def classify(self, paper_embedding: np.ndarray) -> dict:
        """
        Classify a paper using Rocchio scoring.

        Computes similarity score against the dynamic decision boundary
        and routes to ACCEPT, REJECT, or UNCERTAIN.

        Args:
            paper_embedding: Embedding vector of the paper

        Returns:
            Dict with keys:
                - 'score': float [0, 1] - similarity score
                - 'decision': str - 'ACCEPT', 'REJECT', or 'UNCERTAIN'
                - 'centroid_relevant': bool - centroid from relevant seeds exists
                - 'centroid_irrelevant': bool - centroid from irrelevant seeds exists
        """
        if paper_embedding.shape[0] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {paper_embedding.shape[0]}"
            )

        # Build dynamic query vector
        query_vector = np.zeros(self.embedding_dim)

        if self.state.query_centroid is not None:
            query_vector += self.state.alpha * self.state.query_centroid

        if self.state.centroid_relevant is not None:
            query_vector += self.state.beta * self.state.centroid_relevant

        if self.state.centroid_irrelevant is not None:
            query_vector -= self.state.gamma * self.state.centroid_irrelevant

        # Normalize and compute similarity
        query_norm = np.linalg.norm(query_vector)
        doc_norm = np.linalg.norm(paper_embedding)

        if query_norm == 0 or doc_norm == 0:
            # Fallback: if no query vector, use simple similarity to relevant centroid
            if self.state.centroid_relevant is not None:
                score = np.dot(paper_embedding, self.state.centroid_relevant) / (
                    doc_norm * np.linalg.norm(self.state.centroid_relevant) + 1e-10
                )
            else:
                score = 0.5  # Neutral if no centroids at all
        else:
            score = np.dot(paper_embedding, query_vector) / (doc_norm * query_norm)

        # Normalize score to [0, 1] range
        score = (score + 1) / 2  # Convert from [-1, 1] to [0, 1]
        score = np.clip(score, 0, 1)

        # Make decision
        if score >= self.state.accept_threshold:
            decision = "ACCEPT"
        elif score <= self.state.reject_threshold:
            decision = "REJECT"
        else:
            decision = "UNCERTAIN"

        return {
            "score": float(score),
            "decision": decision,
            "centroid_relevant": self.state.centroid_relevant is not None,
            "centroid_irrelevant": self.state.centroid_irrelevant is not None,
        }

    def update_centroid(self, paper_embedding: np.ndarray, is_relevant: bool) -> None:
        """
        Incrementally update a centroid with a newly labeled paper.

        Uses the incremental centroid formula:
            centroid_new = centroid_old + (embedding - centroid_old) / (count + 1)

        This is O(embedding_dim) and can be called after each paper classification.

        Args:
            paper_embedding: Embedding vector of newly labeled paper
            is_relevant: True if paper is relevant (accepted), False if irrelevant (rejected)
        """
        if is_relevant:
            if self.state.centroid_relevant is None:
                self.state.centroid_relevant = paper_embedding.copy()
                self.state.count_relevant = 1
            else:
                self.state.count_relevant += 1
                self.state.centroid_relevant += (
                    (paper_embedding - self.state.centroid_relevant) / self.state.count_relevant
                )
        else:
            if self.state.centroid_irrelevant is None:
                self.state.centroid_irrelevant = paper_embedding.copy()
                self.state.count_irrelevant = 1
            else:
                self.state.count_irrelevant += 1
                self.state.centroid_irrelevant += (
                    (paper_embedding - self.state.centroid_irrelevant) / self.state.count_irrelevant
                )

    def next_iteration(self) -> None:
        """Mark the transition to the next snowballing iteration."""
        self.state.iteration += 1

    def get_state(self) -> ScreeningState:
        """Get the current state for storage in executor.step_state."""
        # Convert numpy arrays back to lists for JSON serialization
        state_copy = ScreeningState(
            centroid_relevant=self.state.centroid_relevant.tolist()
            if self.state.centroid_relevant is not None
            else None,
            centroid_irrelevant=self.state.centroid_irrelevant.tolist()
            if self.state.centroid_irrelevant is not None
            else None,
            query_centroid=self.state.query_centroid.tolist()
            if self.state.query_centroid is not None
            else None,
            count_relevant=self.state.count_relevant,
            count_irrelevant=self.state.count_irrelevant,
            alpha=self.state.alpha,
            beta=self.state.beta,
            gamma=self.state.gamma,
            accept_threshold=self.state.accept_threshold,
            reject_threshold=self.state.reject_threshold,
            iteration=self.state.iteration,
        )
        return state_copy
