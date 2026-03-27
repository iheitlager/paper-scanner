#!/usr/bin/env python
"""
test_05_llm_classification.py

LLM-based paper classification using Claude.

This spike demonstrates using Claude to classify papers based on:
1. Research question from general config
2. Research dimensions (enumerated as classification labels)
3. Paper details (TITLE, ABSTRACT, KEYWORDS)

The classifier updates:
- classification_vector: List of floats (0-1 or binary)
- classification: String classification label
- classification_labels: List of applicable labels

Run with:
    pytest test_05_llm_classification.py -v
    or
    python test_05_llm_classification.py --manual
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Paper Scanner imports
from paper_scanner.core.enum import ScreeningDecision
from paper_scanner.core.models import (
    Paper,
    ProcessingMetadata,
    Screening,
    SemanticScreening,
)
from paper_scanner.models.anthropic import ClaudeHandler


class LLMClassifier:
    """
    LLM-based paper classifier using Claude.

    Classifies papers according to research dimensions defined in general_config.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are an expert academic paper classifier.
Your task is to classify research papers based on predefined research dimensions.

You will be provided with:
1. A research question describing the study scope
2. Research dimensions (classification categories)
3. Paper details (title, abstract, keywords)

For each paper, you must:
1. Determine which research dimensions apply (binary classification)
2. Assign a confidence score (0-1) for each dimension
3. Provide a brief reasoning

Output ONLY valid JSON with this structure:
{{
    "classifications": {{
        "dimension_name": {{
            "applies": true/false,
            "confidence": 0.0-1.0,
            "reasoning": "Brief explanation"
        }}
    }},
    "overall_decision": "include/exclude/review",
    "summary": "Overall classification summary"
}}

Be strict and only include dimensions that clearly apply to the paper."""

    def __init__(
        self,
        research_question: str,
        research_dimensions: List[str],
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-20250514",
        logger=None,
    ):
        """
        Initialize the LLM classifier.

        Args:
            research_question: The research question from general_config
            research_dimensions: List of classification dimension names
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use
            logger: Optional logging function
        """
        self.research_question = research_question
        self.research_dimensions = research_dimensions
        self.model_name = model
        self.logger = logger or (lambda msg: None)

        # Initialize Claude handler
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.claude = ClaudeHandler(api_key=api_key, model=model, logger=self.logger)

    def _format_paper_text(self, paper: Paper) -> str:
        """Format paper details for LLM input."""
        lines = []

        # Title
        if paper.title:
            lines.append(f"TITLE: {paper.title}")

        # Abstract
        if paper.abstract:
            lines.append(f"ABSTRACT: {paper.abstract}")

        # Keywords
        if paper.keywords:
            keywords_str = ", ".join(paper.keywords) if isinstance(paper.keywords, list) else str(paper.keywords)
            lines.append(f"KEYWORDS: {keywords_str}")

        # Year
        if paper.year:
            lines.append(f"YEAR: {paper.year}")

        # Authors (limited)
        if paper.authors and len(paper.authors) > 0:
            author_names = [a.full_name if hasattr(a, 'full_name') else str(a) for a in paper.authors[:5]]
            authors_str = ", ".join(author_names)
            if len(paper.authors) > 5:
                authors_str += f", and {len(paper.authors) - 5} more"
            lines.append(f"AUTHORS: {authors_str}")

        return "\n".join(lines)

    def _build_prompt(self, paper: Paper) -> str:
        """Build the classification prompt for a single paper."""
        dimensions_text = "\n".join(
            f"- {i+1}. {dim}" for i, dim in enumerate(self.research_dimensions)
        )

        paper_text = self._format_paper_text(paper)

        prompt = f"""RESEARCH QUESTION:
{self.research_question}

RESEARCH DIMENSIONS (Classification Categories):
{dimensions_text}

PAPER TO CLASSIFY:
{paper_text}

Please classify this paper according to the research dimensions listed above."""

        return prompt

    def classify_paper(
        self,
        paper: Paper,
        max_tokens: int = 1024,
    ) -> Tuple[SemanticScreening, Dict[str, Any]]:
        """
        Classify a single paper.

        Args:
            paper: Paper object to classify
            max_tokens: Maximum tokens for LLM output

        Returns:
            Tuple of (SemanticScreening model, raw classification dict)
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Build prompt
            prompt = self._build_prompt(paper)

            self.logger(f"Classifying paper: {paper.cite_key}")

            # Call Claude
            parsed_response, token_usage = self.claude.call(
                text=prompt,
                system_prompt=self.SYSTEM_PROMPT_TEMPLATE,
                max_tokens=max_tokens,
            )

            if not parsed_response:
                raise ValueError("Claude API returned no response")

            # Extract classification results
            classifications = parsed_response.get("classifications", {})
            overall_decision_str = parsed_response.get("overall_decision", "review").lower()
            summary = parsed_response.get("summary", "")

            # Build classification vector (confidence scores for each dimension)
            classification_vector = []
            classification_labels = []
            applies_count = 0

            for dimension in self.research_dimensions:
                if dimension in classifications:
                    dim_data = classifications[dimension]
                    confidence = float(dim_data.get("confidence", 0.0))
                    applies = dim_data.get("applies", False)

                    classification_vector.append(confidence)

                    if applies:
                        classification_labels.append(dimension)
                        applies_count += 1
                else:
                    # Default to 0 confidence if not in response
                    classification_vector.append(0.0)

            # Determine decision
            if overall_decision_str == "include":
                decision = ScreeningDecision.INCLUDED
            elif overall_decision_str == "exclude":
                decision = ScreeningDecision.EXCLUDED
            else:
                decision = ScreeningDecision.MANUAL_REVIEW

            # Calculate confidence as average of dimension confidences
            avg_confidence = sum(classification_vector) / len(classification_vector) if classification_vector else 0.0

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
                similarity_score=avg_confidence,  # Use avg confidence as "similarity"
                threshold=0.5,
                classification_vector=classification_vector,
                classification_labels=classification_labels,
                classification=overall_decision_str,
                decision=decision,
                confidence=avg_confidence,
                reason=summary,
                metadata=metadata,
            )

            # Return both screening result and raw classification data
            raw_data = {
                "classifications": classifications,
                "overall_decision": overall_decision_str,
                "summary": summary,
                "classification_vector": classification_vector,
                "classification_labels": classification_labels,
                "applies_count": applies_count,
                "dimension_count": len(self.research_dimensions),
                "token_usage": token_usage,
            }

            return screening_result, raw_data

        except Exception as e:
            self.logger(f"Error classifying paper {paper.cite_key}: {e}")

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
# TESTS
# ============================================================================


def create_test_paper(
    cite_key: str,
    title: str,
    abstract: str,
    keywords: Optional[List[str]] = None,
) -> Paper:
    """Helper to create a test paper."""
    return Paper(
        cite_key=cite_key,
        title=title,
        abstract=abstract,
        keywords=keywords or [],
        authors=[],
        year=2024,
        screening=Screening(),
    )


class TestLLMClassifier:
    """Test LLM classification functionality."""

    @pytest.fixture
    def general_config(self) -> Dict[str, Any]:
        """Setup general config with research question and dimensions."""
        return {
            "project_name": "Digital Transformation Review",
            "researcher": "Test Researcher",
            "research_question": """
            How do organizations leverage digital technologies to transform
            their business models and achieve competitive advantage?
            """,
            "research_dimensions": [
                "Digital Technology Adoption",
                "Business Model Innovation",
                "Organizational Transformation",
                "Competitive Advantage",
                "Change Management",
                "Process Automation",
            ],
        }

    @pytest.fixture
    def classifier(self, general_config) -> LLMClassifier:
        """Create a classifier instance."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        return LLMClassifier(
            research_question=general_config["research_question"],
            research_dimensions=general_config["research_dimensions"],
            api_key=api_key,
        )

    @pytest.fixture
    def test_papers(self) -> List[Paper]:
        """Create test papers."""
        papers = [
            create_test_paper(
                cite_key="paper_01",
                title="Digital Transformation in Manufacturing: A Case Study",
                abstract="""
                This paper investigates how manufacturing firms implement digital technologies
                to transform their production processes and business models. We analyze 15 firms
                using technology adoption frameworks and find that successful transformation
                requires both technological and organizational changes.
                """,
                keywords=["digital transformation", "manufacturing", "innovation", "automation"],
            ),
            create_test_paper(
                cite_key="paper_02",
                title="The Impact of AI on Customer Service in Retail",
                abstract="""
                Customer service automation using AI is becoming increasingly important.
                This study examines implementation challenges and benefits.
                """,
                keywords=["artificial intelligence", "customer service", "retail"],
            ),
            create_test_paper(
                cite_key="paper_03",
                title="A Comprehensive Review of Machine Learning Applications",
                abstract="""
                This is a systematic review of machine learning applications across various
                domains including healthcare, finance, and manufacturing.
                """,
                keywords=["machine learning", "review", "applications"],
            ),
        ]
        return papers

    def test_classifier_initialization(self, classifier):
        """Test classifier can be initialized."""
        assert classifier is not None
        assert classifier.research_question
        assert len(classifier.research_dimensions) > 0

    def test_format_paper_text(self, classifier, test_papers):
        """Test paper formatting for LLM input."""
        paper = test_papers[0]
        formatted = classifier._format_paper_text(paper)

        assert "TITLE:" in formatted
        assert paper.title in formatted
        assert "ABSTRACT:" in formatted
        assert "KEYWORDS:" in formatted

    def test_build_prompt(self, classifier, test_papers):
        """Test prompt building."""
        paper = test_papers[0]
        prompt = classifier._build_prompt(paper)

        assert "RESEARCH QUESTION:" in prompt
        assert "RESEARCH DIMENSIONS" in prompt
        assert "PAPER TO CLASSIFY:" in prompt
        assert classifier.research_question in prompt
        assert paper.title in prompt

    def test_classify_single_paper(self, classifier, test_papers):
        """Test classifying a single paper."""
        paper = test_papers[0]

        screening_result, raw_data = classifier.classify_paper(paper)

        # Check result structure
        assert screening_result is not None
        assert isinstance(screening_result, SemanticScreening)

        # Check classification vector
        assert hasattr(screening_result, "classification_vector")
        assert len(screening_result.classification_vector) == len(classifier.research_dimensions)

        # Check classification labels
        assert hasattr(screening_result, "classification_labels")
        assert isinstance(screening_result.classification_labels, list)

        # Check decision
        assert screening_result.decision in [
            ScreeningDecision.INCLUDED,
            ScreeningDecision.EXCLUDED,
            ScreeningDecision.MANUAL_REVIEW,
        ]

        # Check confidence
        assert 0.0 <= screening_result.confidence <= 1.0

        # Check raw data
        assert "classifications" in raw_data
        assert "overall_decision" in raw_data
        assert "summary" in raw_data

    def test_classify_multiple_papers(self, classifier, test_papers):
        """Test classifying multiple papers."""
        results = {}

        for paper in test_papers:
            screening_result, raw_data = classifier.classify_paper(paper)
            results[paper.cite_key] = {
                "screening": screening_result,
                "raw": raw_data,
            }

        # Check all papers were classified
        assert len(results) == len(test_papers)

        # Check each result
        for cite_key, result in results.items():
            assert result["screening"] is not None
            assert result["raw"] is not None


def test_format_paper_for_classification():
    """Test paper formatting without fixture."""
    paper = create_test_paper(
        cite_key="test",
        title="Test Paper",
        abstract="This is a test.",
        keywords=["test", "classification"],
    )


    # Just test the formatting logic
    lines = []
    if paper.title:
        lines.append(f"TITLE: {paper.title}")
    if paper.abstract:
        lines.append(f"ABSTRACT: {paper.abstract}")
    if paper.keywords:
        keywords_str = ", ".join(paper.keywords)
        lines.append(f"KEYWORDS: {keywords_str}")

    formatted = "\n".join(lines)

    assert "TITLE: Test Paper" in formatted
    assert "ABSTRACT: This is a test." in formatted
    assert "KEYWORDS: test, classification" in formatted


def test_decision_mapping():
    """Test mapping LLM decisions to ScreeningDecision enum."""
    test_cases = [
        ("include", ScreeningDecision.INCLUDED),
        ("exclude", ScreeningDecision.EXCLUDED),
        ("review", ScreeningDecision.MANUAL_REVIEW),
    ]

    for llm_decision, expected_enum in test_cases:
        if llm_decision == "include":
            result = ScreeningDecision.INCLUDED
        elif llm_decision == "exclude":
            result = ScreeningDecision.EXCLUDED
        else:
            result = ScreeningDecision.MANUAL_REVIEW

        assert result == expected_enum


if __name__ == "__main__":
    # Run with: python test_05_llm_classification.py --manual
    pytest.main([__file__, "-v"])
