"""Common types and utilities for RAG components."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class PlanType(Enum):
    """Types of retrieval plans."""
    DIRECT = "direct"  # Direct vector search
    SIMPLIFY = "simplify"  # Query simplification
    DECOMPOSE = "decompose"  # Query decomposition
    ROUTE = "route"  # Agentic routing
    HYPOTHETICAL = "hypothetical"  # HyDE
    ITERATIVE = "iterative"  # Multi-turn


@dataclass
class SearchPlan:
    """Structured retrieval plan from Planner."""
    plan_type: PlanType
    queries: List[str]  # List of queries to search
    tool_methods: List[str]  # Which Tool methods to call
    parameters: Dict[str, Any] = field(default_factory=dict)  # Additional params
    reasoning: Optional[str] = None  # Why this plan was chosen


@dataclass
class QualityScore:
    """Quality assessment of retrieval results."""
    coverage: float  # 0-100, % of papers represented
    relevance: float  # 0-100, direct relevance to question
    freshness: float  # 0-100, recency of papers
    is_adequate: bool  # Pass/fail for stopping iterative search
    feedback: Optional[str] = None  # Suggestions for refinement


@dataclass
class RetrievalResult:
    """Result from Tool retrieval."""
    chunks: List[Dict[str, Any]]  # Retrieved chunks with metadata
    paper_count: int  # Number of unique papers
    total_similarity: float  # Sum of similarity scores
    search_method: str  # Which Tool method found these


@dataclass
class SynthesisResult:
    """Result from Synthesizer."""
    answer_text: str
    tokens_used: int
    latency_ms: float
    citations: List[str] = field(default_factory=list)


@dataclass
class PipelineMetrics:
    """Metrics for entire pipeline execution."""
    plan_tokens: int = 0
    search_time_ms: float = 0
    chunks_found: int = 0
    synthesis_tokens: int = 0
    synthesis_time_ms: float = 0
    total_tokens: int = 0
    total_time_ms: float = 0
