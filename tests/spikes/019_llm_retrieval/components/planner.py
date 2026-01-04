"""Planner: Strategy decision-maker for retrieval operations."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import time
from anthropic import Anthropic

from .common import SearchPlan, PlanType


class BasePlanner(ABC):
    """Abstract base class for all Planner implementations."""

    def __init__(self, llm_client: Optional[Anthropic] = None):
        """
        Initialize Planner.
        
        Args:
            llm_client: Anthropic client for LLM calls (optional)
        """
        self.llm_client = llm_client or Anthropic()
        self.plan_tokens = 0
        self.plan_time_ms = 0

    @abstractmethod
    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        Analyze question and create retrieval plan.
        
        Args:
            question: User's question
            papers: Available papers from database
            
        Returns:
            SearchPlan with queries and tool methods to use
        """
        pass

    def refine(self, question: str, initial_results: Dict[str, Any]) -> Optional[SearchPlan]:
        """
        Optionally refine plan based on initial results (for iterative planning).
        
        Args:
            question: Original question
            initial_results: Results from first search
            
        Returns:
            Refined SearchPlan or None if no refinement needed
        """
        return None  # Override in subclasses that need refinement


class NullPlanner(BasePlanner):
    """No-op planner for direct vector search (Architecture 1)."""

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        No planning - just return direct vector search plan.
        
        Args:
            question: User's question
            papers: Available papers
            
        Returns:
            Direct vector search plan
        """
        return SearchPlan(
            plan_type=PlanType.DIRECT,
            queries=[question],
            tool_methods=['vector_search'],
            reasoning="Direct vector search without planning"
        )


class SimplifyingPlanner(BasePlanner):
    """Query simplification planner (Architecture 1b)."""

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        Extract keywords from complex question for better matching.
        
        Args:
            question: User's question (potentially with meta-language)
            papers: Available papers
            
        Returns:
            SearchPlan with simplified keywords query
        """
        start_time = time.time()
        
        # LLM extracts keywords
        message = self.llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Extract 3-5 key academic search terms from this question. 
Return ONLY the keywords separated by spaces, no explanation.

Question: {question}

Keywords:"""
            }]
        )
        
        simplified = message.content[0].text.strip()
        self.plan_tokens = message.usage.input_tokens + message.usage.output_tokens
        self.plan_time_ms = (time.time() - start_time) * 1000
        
        return SearchPlan(
            plan_type=PlanType.SIMPLIFY,
            queries=[simplified],
            tool_methods=['vector_search'],
            parameters={'original_question': question},
            reasoning=f"Simplified '{question}' to '{simplified}' for better matching"
        )


class RouterPlanner(BasePlanner):
    """Agentic routing planner (Architecture 2)."""

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        LLM decides which Tool methods to call and with what queries.
        
        Args:
            question: User's question
            papers: Available papers
            
        Returns:
            SearchPlan with multiple tool method calls
        """
        start_time = time.time()
        
        # LLM decides routing strategy
        message = self.llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Given this question about academic papers, decide which search methods to use.
Available methods: vector_search, search_methodology, search_findings

For methodology questions, use search_methodology.
For findings questions, use search_findings.
For general questions, use vector_search.
For complex questions, combine multiple methods.

Respond as JSON with keys: "methods" (list), "queries" (list), "reasoning" (string)

Question: {question}

JSON:"""
            }]
        )
        
        response_text = message.content[0].text.strip()
        self.plan_tokens = message.usage.input_tokens + message.usage.output_tokens
        self.plan_time_ms = (time.time() - start_time) * 1000
        
        # Parse response - simplified parsing, in production use json.loads
        methods = ['vector_search']  # Fallback
        queries = [question]
        reasoning = response_text
        
        return SearchPlan(
            plan_type=PlanType.ROUTE,
            queries=queries,
            tool_methods=methods,
            reasoning=reasoning
        )


class DecompositionPlanner(BasePlanner):
    """Query decomposition planner (Architecture 3)."""

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        Break complex question into multiple sub-queries.
        
        Args:
            question: User's question
            papers: Available papers
            
        Returns:
            SearchPlan with multiple sub-queries
        """
        start_time = time.time()
        
        message = self.llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"""Break this complex question into 3-4 focused sub-queries that cover different aspects.
Return ONLY the sub-queries, one per line, no numbering.

Question: {question}

Sub-queries:"""
            }]
        )
        
        response_text = message.content[0].text.strip()
        sub_queries = [q.strip() for q in response_text.split('\n') if q.strip()]
        
        self.plan_tokens = message.usage.input_tokens + message.usage.output_tokens
        self.plan_time_ms = (time.time() - start_time) * 1000
        
        return SearchPlan(
            plan_type=PlanType.DECOMPOSE,
            queries=sub_queries,
            tool_methods=['vector_search'] * len(sub_queries),
            reasoning=f"Decomposed into {len(sub_queries)} sub-queries for comprehensive coverage"
        )


class HyDEPlanner(BasePlanner):
    """Hypothetical Document Embeddings planner (Architecture 4)."""

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        Generate hypothetical answer for better embedding matching.
        
        Args:
            question: User's question
            papers: Available papers
            
        Returns:
            SearchPlan with hypothetical answer query
        """
        start_time = time.time()
        
        message = self.llm_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"""Write a 2-3 sentence hypothetical answer to this question about academic papers.
Write as if this answer appeared in a research paper.

Question: {question}

Hypothetical answer:"""
            }]
        )
        
        hypothetical = message.content[0].text.strip()
        self.plan_tokens = message.usage.input_tokens + message.usage.output_tokens
        self.plan_time_ms = (time.time() - start_time) * 1000
        
        return SearchPlan(
            plan_type=PlanType.HYPOTHETICAL,
            queries=[hypothetical],
            tool_methods=['vector_search'],
            parameters={'original_question': question},
            reasoning=f"Searching with hypothetical answer instead of question for better vocabulary match"
        )


class IterativePlanner(BasePlanner):
    """Iterative multi-turn planner (Architecture 5)."""

    def __init__(self, llm_client: Optional[Anthropic] = None, max_iterations: int = 3):
        """Initialize with iteration limit."""
        super().__init__(llm_client)
        self.max_iterations = max_iterations
        self.iteration = 0

    def formalize(self, question: str, papers: List[Dict[str, Any]]) -> SearchPlan:
        """
        Start first iteration of multi-turn retrieval.
        
        Args:
            question: User's question
            papers: Available papers
            
        Returns:
            SearchPlan for initial search
        """
        self.iteration = 0
        return SearchPlan(
            plan_type=PlanType.ITERATIVE,
            queries=[question],
            tool_methods=['vector_search'],
            parameters={'iteration': 0, 'max_iterations': self.max_iterations},
            reasoning="Starting iterative retrieval with initial broad search"
        )

    def refine(self, question: str, initial_results: Dict[str, Any]) -> Optional[SearchPlan]:
        """
        Decide if more iteration needed based on quality score.
        
        Args:
            question: Original question
            initial_results: Results from previous iteration with quality_score
            
        Returns:
            Refined SearchPlan or None if adequate
        """
        quality_score = initial_results.get('quality_score')
        
        if not quality_score or self.iteration >= self.max_iterations:
            return None
        
        # If coverage is low, refine search
        if quality_score.coverage < 70:
            self.iteration += 1
            
            # Ask LLM what to search for next
            message = self.llm_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": f"""Current search found low coverage. Suggest one refinement query to find more relevant papers.
Original question: {question}
Coverage so far: {quality_score.coverage:.0f}%

Refined query:"""
                }]
            )
            
            refined_query = message.content[0].text.strip()
            
            return SearchPlan(
                plan_type=PlanType.ITERATIVE,
                queries=[refined_query],
                tool_methods=['vector_search'],
                parameters={'iteration': self.iteration, 'max_iterations': self.max_iterations},
                reasoning=f"Iteration {self.iteration}: Refining search for better coverage"
            )
        
        return None  # Results are adequate
