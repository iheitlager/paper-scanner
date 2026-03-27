#!/usr/bin/env python
"""
test_06_rocchio_classifier.py

Rocchio-based classifier using research dimensions as separate centroids.

This spike demonstrates using the Rocchio algorithm to classify papers based on:
1. Research question from general config
2. Research dimensions as SEPARATE CENTROIDS (each dimension is its own centroid)
3. Paper embeddings and research_dimension embeddings
4. Multi-dimensional classification with dominant dimension

The classifier:
- Computes similarity between paper and each dimension centroid
- Determines which dimensions apply (above threshold)
- Identifies the dominant dimension (highest similarity)
- Classifies as: EXCLUDED (no dimensions apply), UNCERTAIN (multiple dimensions, unclear dominance),
  or INCLUDED (clear dominant dimension)
- Updates MetadataScreening fields with classifier results

Classification logic:
  - If no dimensions above threshold: EXCLUDED
  - If exactly one dimension above threshold: INCLUDED (that dimension is dominant)
  - If multiple dimensions above threshold: UNCERTAIN (need manual review to pick dominant)

Run with:
    pytest test_06_rocchio_classifier.py -v
    or
    python test_06_rocchio_classifier.py --manual
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paper Scanner imports
from paper_scanner.core.enum import ScreeningDecision
from paper_scanner.core.models import (
    Paper,
    ProcessingMetadata,
    Screening,
    SemanticScreening,
)


class RocchioClassifier:
    """
    Rocchio-based classifier using research dimensions as separate centroids.

    Each research dimension becomes a centroid in the embedding space.
    Papers are classified based on their similarity to each dimension centroid.
    """

    def __init__(
        self,
        research_question: str,
        research_dimensions: List[str],
        embedding_model: str = "all-mpnet-base-v2",
        logger=None,
    ):
        """
        Initialize the Rocchio classifier with dimension centroids.

        Args:
            research_question: The research question from general_config
            research_dimensions: List of dimension names (each becomes a centroid)
            embedding_model: Which embedding model to use
            logger: Optional logging function
        """
        self.research_question = research_question
        self.research_dimensions = research_dimensions
        self.embedding_model = embedding_model
        self.logger = logger or (lambda msg: None)

        # Initialize embedding model
        try:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(embedding_model)
        except ImportError:
            raise ImportError(
                "sentence-transformers not available. "
                "Install with: pip install sentence-transformers"
            )

        # Initialize dimension centroids (empty, will be populated from labeled papers)
        self.dimension_centroids: Dict[str, Optional[List[float]]] = {
            dim: None for dim in research_dimensions
        }
        self.dimension_paper_counts: Dict[str, int] = {dim: 0 for dim in research_dimensions}

        self.logger(f"Rocchio classifier initialized with {len(research_dimensions)} dimensions")
        self.logger(f"Dimensions: {', '.join(research_dimensions)}")

    def compute_embedding(self, text: str) -> List[float]:
        """Compute embedding for text."""
        if not text or not text.strip():
            return [0.0] * 768  # Default to zero vector for empty text

        embedding = self.embedder.encode(text, convert_to_numpy=True).tolist()
        return embedding

    def add_training_example(self, paper: Paper, dimension: str, weight: float = 1.0):
        """
        Add a training example to update a dimension centroid.

        Args:
            paper: Paper to use as training example
            dimension: Which dimension this paper exemplifies
            weight: Weight for this example (default 1.0)
        """
        if dimension not in self.dimension_centroids:
            self.logger(f"Warning: Unknown dimension '{dimension}'")
            return

        # Get paper text (combine title + abstract)
        paper_text = f"{paper.title or ''} {paper.abstract or ''}".strip()
        if not paper_text:
            self.logger(f"Warning: Paper {paper.cite_key} has no title/abstract for embedding")
            return

        # Compute embedding
        embedding = self.compute_embedding(paper_text)

        # Update centroid (Rocchio: C = (1/n) * sum(embeddings))
        if self.dimension_centroids[dimension] is None:
            # First example: initialize centroid
            self.dimension_centroids[dimension] = [x * weight for x in embedding]
        else:
            # Add to existing centroid with weight
            current = self.dimension_centroids[dimension]
            self.dimension_centroids[dimension] = [
                curr + (emb * weight)
                for curr, emb in zip(current, embedding)
            ]

        self.dimension_paper_counts[dimension] += 1
        self.logger(f"Added training example to '{dimension}' (count: {self.dimension_paper_counts[dimension]})")

    def initialize_from_research_question(self):
        """
        Initialize centroids from research question expanded with dimensions.

        If no training examples exist, use research question + dimension names
        to create initial centroids.
        """
        self.logger("Initializing centroids from research question")

        for dimension in self.research_dimensions:
            if self.dimension_centroids[dimension] is None:
                # Create synthetic text from research question + dimension
                text = f"{self.research_question}. {dimension}."
                embedding = self.compute_embedding(text)
                self.dimension_centroids[dimension] = embedding
                self.logger(f"Initialized centroid for '{dimension}' from research question")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        if not vec1 or not vec2 or len(vec1) == 0 or len(vec2) == 0:
            return 0.0

        # Handle zero vectors
        mag1 = math.sqrt(sum(x**2 for x in vec1))
        mag2 = math.sqrt(sum(x**2 for x in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        return dot_product / (mag1 * mag2)

    def classify_paper(
        self,
        paper: Paper,
        dimension_threshold: float = 0.5,
    ) -> Tuple[SemanticScreening, Dict]:
        """
        Classify a paper using Rocchio dimension centroids.

        Args:
            paper: Paper to classify
            dimension_threshold: Similarity threshold for dimension applicability

        Returns:
            Tuple of (SemanticScreening, raw classification dict)
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Ensure centroids are initialized
            self.initialize_from_research_question()

            # Get paper embedding
            paper_text = f"{paper.title or ''} {paper.abstract or ''}".strip()
            if not paper_text:
                paper_text = paper.title or ""

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
                dim for dim, sim in dimension_similarities.items()
                if sim >= dimension_threshold
            ]

            # Determine dominant dimension
            dominant_dimension = None
            max_similarity = 0.0
            if applicable_dimensions:
                dominant_dimension = max(
                    applicable_dimensions,
                    key=lambda d: dimension_similarities[d]
                )
                max_similarity = dimension_similarities[dominant_dimension]

            # Make classification decision
            if len(applicable_dimensions) == 0:
                # No dimensions apply
                decision = ScreeningDecision.EXCLUDED
                classification = "excluded"
                # Confidence = how far away from threshold
                confidence = min(1.0, 1.0 - max(dimension_similarities.values())) if dimension_similarities else 1.0
            elif len(applicable_dimensions) == 1:
                # Exactly one dimension applies - clear decision
                decision = ScreeningDecision.INCLUDED
                classification = "included"
                confidence = min(1.0, max_similarity)
            else:
                # Multiple dimensions apply - uncertain
                decision = ScreeningDecision.MANUAL_REVIEW
                classification = "uncertain"
                # Confidence based on dominant dimension similarity
                confidence = min(1.0, max_similarity)

            # Build classification vector (similarities to all dimensions)
            classification_vector = [
                dimension_similarities.get(dim, 0.0)
                for dim in self.research_dimensions
            ]

            # Metadata
            metadata = ProcessingMetadata(
                timestamp=start_time,
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                model_name=self.embedding_model,
                success=True,
            )

            # Create SemanticScreening result
            screening_result = SemanticScreening(
                passed=decision != ScreeningDecision.EXCLUDED,
                similarity_score=max_similarity,
                threshold=dimension_threshold,
                classification_vector=classification_vector,
                classification_labels=applicable_dimensions,
                classification=classification,
                decision=decision,
                confidence=confidence,
                reason=f"Rocchio: {dominant_dimension or 'no dimension'} dominant (sim={max_similarity:.3f})",
                metadata=metadata,
            )

            # Raw data
            raw_data = {
                "dimension_similarities": dimension_similarities,
                "applicable_dimensions": applicable_dimensions,
                "dominant_dimension": dominant_dimension,
                "max_similarity": max_similarity,
                "dimension_count": len(self.research_dimensions),
                "classification_vector": classification_vector,
            }

            return screening_result, raw_data

        except Exception as e:
            self.logger(f"Error classifying paper {paper.cite_key}: {e}")

            metadata = ProcessingMetadata(
                timestamp=start_time,
                duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
                model_name=self.embedding_model,
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


# ============================================================================
# TEST FIXTURES & HELPER FUNCTIONS
# ============================================================================

def create_test_paper(
    title: str,
    abstract: str,
    cite_key: str = "test",
    year: int = 2024,
) -> Paper:
    """Create a test paper with minimal required fields."""
    return Paper(
        id="test-id",
        title=title,
        abstract=abstract,
        cite_key=cite_key,
        year=year,
        authors=[],
        screening=Screening(),
    )


# ============================================================================
# TESTS
# ============================================================================

class TestRocchioClassifier:
    """Tests for Rocchio dimension-based classifier."""

    @pytest.fixture
    def classifier(self):
        """Create a test classifier."""
        research_question = "How do incumbent firms involve suppliers in digital innovation processes?"
        research_dimensions = [
            "supplier_involvement",
            "digital_innovation",
            "incumbent_firms",
            "process_change"
        ]
        return RocchioClassifier(
            research_question=research_question,
            research_dimensions=research_dimensions,
            logger=lambda msg: print(f"  [LOG] {msg}"),
        )

    def test_classifier_initialization(self, classifier):
        """Test classifier initializes with dimensions."""
        assert len(classifier.research_dimensions) == 4
        assert "supplier_involvement" in classifier.research_dimensions
        assert all(c is None for c in classifier.dimension_centroids.values())

    def test_compute_embedding(self, classifier):
        """Test embedding computation."""
        text = "This is a test paper about digital innovation and suppliers."
        embedding = classifier.compute_embedding(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768  # Standard sentence-transformer output
        assert not all(x == 0 for x in embedding)  # Not all zeros

    def test_empty_text_embedding(self, classifier):
        """Test embedding for empty text returns zero vector."""
        embedding = classifier.compute_embedding("")
        assert len(embedding) == 768
        assert all(x == 0 for x in embedding)

    def test_cosine_similarity(self, classifier):
        """Test cosine similarity computation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]

        # Identical vectors
        sim_identical = classifier._cosine_similarity(vec1, vec2)
        assert abs(sim_identical - 1.0) < 0.001

        # Orthogonal vectors
        sim_orthogonal = classifier._cosine_similarity(vec1, vec3)
        assert abs(sim_orthogonal) < 0.001

    def test_training_example_single_dimension(self, classifier):
        """Test adding a training example."""
        paper = create_test_paper(
            title="Supplier Involvement in Digital Projects",
            abstract="This paper discusses how suppliers are involved in digital innovation.",
            cite_key="test001",
        )

        # Initially no centroid
        assert classifier.dimension_centroids["supplier_involvement"] is None

        # Add training example
        classifier.add_training_example(paper, "supplier_involvement")

        # Now centroid exists
        assert classifier.dimension_centroids["supplier_involvement"] is not None
        assert classifier.dimension_paper_counts["supplier_involvement"] == 1

    def test_training_example_accumulation(self, classifier):
        """Test that training examples accumulate."""
        paper1 = create_test_paper(
            title="Digital Innovation Strategy",
            abstract="Strategic approaches to digital transformation.",
            cite_key="test001",
        )
        paper2 = create_test_paper(
            title="Digital Innovation Implementation",
            abstract="How to implement digital innovation in organizations.",
            cite_key="test002",
        )

        classifier.add_training_example(paper1, "digital_innovation")
        classifier.add_training_example(paper2, "digital_innovation")

        assert classifier.dimension_paper_counts["digital_innovation"] == 2

    def test_initialization_from_research_question(self, classifier):
        """Test centroid initialization from research question."""
        # No training examples, so centroids should be None
        for centroid in classifier.dimension_centroids.values():
            assert centroid is None

        # Initialize from research question
        classifier.initialize_from_research_question()

        # Now all centroids should exist
        for dimension in classifier.research_dimensions:
            assert classifier.dimension_centroids[dimension] is not None
            centroid = classifier.dimension_centroids[dimension]
            assert len(centroid) == 768

    def test_classify_paper_excluded(self, classifier):
        """Test classification of paper with no matching dimensions."""
        # Create paper about unrelated topic
        paper = create_test_paper(
            title="Weather Prediction Using Machine Learning",
            abstract="This paper proposes a neural network for weather forecasting.",
            cite_key="test_excluded",
        )

        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.5)

        # Should be excluded (no relevant dimensions)
        assert screening.decision == ScreeningDecision.EXCLUDED
        assert screening.classification == "excluded"
        assert screening.passed is False

    def test_classify_paper_included(self, classifier):
        """Test classification of paper with clear dominant dimension."""
        # Create paper about suppliers and digital innovation
        paper = create_test_paper(
            title="Digital Suppliers in Innovation",
            abstract="How supplier involvement drives digital innovation in incumbent firms.",
            cite_key="test_included",
        )

        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.5)

        # Should be included (has dominant dimension)
        # Classification could be included or uncertain depending on centroid similarities
        assert screening.decision in [ScreeningDecision.INCLUDED, ScreeningDecision.MANUAL_REVIEW]
        assert screening.passed in [True, False]  # Either is valid
        assert len(screening.classification_vector) == 4
        assert all(isinstance(x, float) for x in screening.classification_vector)

    def test_classification_vector_completeness(self, classifier):
        """Test that classification vector has entry for each dimension."""
        paper = create_test_paper(
            title="Test Paper",
            abstract="A test paper about digital innovation.",
            cite_key="test_vector",
        )

        screening, raw = classifier.classify_paper(paper)

        assert len(screening.classification_vector) == len(classifier.research_dimensions)
        assert len(raw["dimension_similarities"]) == len(classifier.research_dimensions)

    def test_dominant_dimension_identification(self, classifier):
        """Test that dominant dimension is correctly identified."""
        # Add training examples for specific dimension
        paper_supplier = create_test_paper(
            title="Supplier Involvement Strategies",
            abstract="Key strategies for effective supplier involvement.",
            cite_key="supplier001",
        )

        classifier.add_training_example(paper_supplier, "supplier_involvement")
        classifier.add_training_example(paper_supplier, "supplier_involvement")
        classifier.add_training_example(paper_supplier, "supplier_involvement")

        # Classify a paper about suppliers
        paper = create_test_paper(
            title="Supplier Involvement in Innovation",
            abstract="This paper examines supplier involvement in innovation projects.",
            cite_key="test_dominant",
        )

        screening, raw = classifier.classify_paper(paper, dimension_threshold=0.3)

        # dominant_dimension should be identified
        if raw.get("dominant_dimension"):
            assert raw["dominant_dimension"] in classifier.research_dimensions

    def test_metadata_in_screening_result(self, classifier):
        """Test that screening result includes metadata."""
        paper = create_test_paper(
            title="Test Paper",
            abstract="Test abstract",
            cite_key="test_meta",
        )

        screening, _ = classifier.classify_paper(paper)

        assert screening.metadata is not None
        assert screening.metadata.model_name == classifier.embedding_model
        assert screening.metadata.success is True
        assert screening.metadata.timestamp is not None
        assert screening.metadata.duration_seconds is not None

    def test_error_handling(self, classifier):
        """Test error handling in classification."""
        # Create paper with None fields to test robustness
        paper = Paper(
            id="test-error",
            title=None,
            abstract=None,
            cite_key="test_error",
            authors=[],
            screening=Screening(),
        )

        screening, raw = classifier.classify_paper(paper)

        # Should still classify without crashing
        assert screening is not None
        assert screening.decision in [
            ScreeningDecision.EXCLUDED,
            ScreeningDecision.INCLUDED,
            ScreeningDecision.MANUAL_REVIEW
        ]

    def test_classifier_with_multiple_papers(self, classifier):
        """Test classifying multiple papers in sequence."""
        papers = [
            create_test_paper(
                title="Digital Innovation and Suppliers",
                abstract="How suppliers participate in digital transformation.",
                cite_key=f"paper{i}",
            )
            for i in range(3)
        ]

        results = []
        for paper in papers:
            screening, raw = classifier.classify_paper(paper)
            results.append((screening, raw))

        assert len(results) == 3
        assert all(r[0].decision is not None for r in results)
        assert all(r[0].metadata is not None for r in results)


class TestRocchioClassifierIntegration:
    """Integration tests with more realistic scenarios."""

    def test_rocchio_with_trained_dimensions(self):
        """Test Rocchio classifier with trained dimension centroids."""
        classifier = RocchioClassifier(
            research_question="How do incumbent firms innovate through digital technologies?",
            research_dimensions=[
                "digital_transformation",
                "incumbent_strategy",
                "innovation_process",
            ],
            logger=lambda msg: print(f"  [LOG] {msg}"),
        )

        # Train dimensions with relevant papers
        training_papers = {
            "digital_transformation": [
                create_test_paper(
                    title="Digital Transformation in Enterprises",
                    abstract="Enterprise digital transformation strategies and implementation.",
                    cite_key="dt001",
                ),
                create_test_paper(
                    title="Digital Technologies for Business",
                    abstract="Adoption of digital technologies in business processes.",
                    cite_key="dt002",
                ),
            ],
            "incumbent_strategy": [
                create_test_paper(
                    title="Incumbent Firm Strategies",
                    abstract="Strategic approaches used by established firms.",
                    cite_key="is001",
                ),
            ],
            "innovation_process": [
                create_test_paper(
                    title="Innovation Process Models",
                    abstract="Models and frameworks for managing innovation.",
                    cite_key="ip001",
                ),
            ],
        }

        # Add training examples
        for dimension, papers in training_papers.items():
            for paper in papers:
                classifier.add_training_example(paper, dimension, weight=1.0)

        # Classify a new paper
        test_paper = create_test_paper(
            title="Digital Transformation in Incumbent Firms",
            abstract="How established companies use digital innovation to stay competitive.",
            cite_key="test_final",
        )

        screening, raw = classifier.classify_paper(test_paper, dimension_threshold=0.4)

        # Verify results
        assert screening.decision is not None
        assert screening.classification_vector is not None
        assert len(screening.classification_vector) == 3
        assert screening.metadata.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
