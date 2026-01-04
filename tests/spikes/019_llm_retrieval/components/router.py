"""Router: Orchestrator managing the 5-stage pipeline."""

import time
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown

from .planner import BasePlanner
from .tool import Tool
from .evaluator import Evaluator
from .synthesizer import Synthesizer
from .memory import Memory
from .common import PipelineMetrics, SearchPlan
from .logger import Logger, DefaultLogger


class Router:
    """Orchestrates the 5-stage RAG pipeline: Get → Plan → Query → Evaluate → Finalize."""

    def __init__(
        self,
        planner: BasePlanner,
        tool: Tool,
        evaluator: Evaluator,
        synthesizer: Synthesizer,
        memory: Memory,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize Router with components.

        Args:
            planner: Strategy decision-maker
            tool: Database interface
            evaluator: Quality assessor
            synthesizer: Answer generator
            memory: Cache and history
            logger: Optional Logger instance (uses DefaultLogger if None and verbose=True)
        """
        self.planner = planner
        self.tool = tool
        self.evaluator = evaluator
        self.synthesizer = synthesizer
        self.memory = memory

        # Setup logger
        if not logger:
            self.logger = DefaultLogger()


    def _validate_question(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Validate question quality.

        Args:
            question: User's question

        Returns:
            None if valid, error dict if invalid
        """
        words = question.strip().split()
        if len(words) < 2:
            return {
                "error": "incomplete_question",
                "message": f"Question too short ({len(words)} word). Please ask a full question with at least 2 words.",
                "source": "error",
            }
        return None

    def route_query(self, question: str) -> Dict[str, Any]:
        """
        Execute full 5-stage pipeline: Get → Plan → Query → Evaluate → Finalize.

        Args:
            question: User's question

        Returns:
            Dictionary with answer, results, metrics, and metadata
            If question is incomplete, returns error dict
        """
        # Validate input quality
        validation_error = self._validate_question(question)
        if validation_error:
            self.logger.on_error(validation_error["error"], validation_error.get("message"))
            return validation_error

        # Log question
        self.logger.on_question(question)

        start_time = time.time()
        metrics = PipelineMetrics()

        # === Stage 1: Get ===
        self.logger.on_log("→ Stage 1: Initialization")
        papers = self._stage_get()
        self.logger.on_log("  ✓ Papers loaded")

        # Check memory for cached result
        self.logger.on_log("  Checking memory for similar queries...")
        cached = self.memory.find_similar_query(question)
        if cached:
            self.logger.on_log("  ⚡ Cache hit! Using similar cached result")
            return {"answer": cached["answer"], "source": "cache", "metrics": metrics}
        self.logger.on_log("  No cache hit, proceeding with full pipeline\n")

        # === Stage 2: Plan ===
        plan, plan_metrics = self._stage_plan(question, papers)
        metrics.plan_tokens = plan_metrics[0]
        metrics.plan_time_ms = plan_metrics[1]

        # === Stage 3: Query ===
        retrieval_result, query_metrics = self._stage_query(plan)
        metrics.search_time_ms = query_metrics[0]
        metrics.chunks_found = len(retrieval_result.chunks)

        # === Stage 4: Evaluate ===
        quality_score = self._stage_evaluate(retrieval_result, question, papers)

        # === Stage 5: Finalize (Synthesize) ===
        synthesis_result, synthesis_metrics = self._stage_finalize(question, retrieval_result)
        metrics.synthesis_tokens = synthesis_result.tokens_used
        metrics.synthesis_time_ms = synthesis_result.latency_ms

        # Store in memory
        self.memory.store_interaction(
            question=question,
            answer=synthesis_result.answer_text,
            chunks_count=metrics.chunks_found,
            papers_count=retrieval_result.paper_count,
            quality_score=quality_score,
            plan_type=plan.plan_type.value,
            metrics=metrics,
        )

        # Finalize metrics
        metrics.total_tokens = metrics.plan_tokens + metrics.synthesis_tokens
        metrics.total_time_ms = time.time() - start_time

        return {
            "answer": synthesis_result.answer_text,
            "citations": synthesis_result.citations,
            "chunks": retrieval_result.chunks,
            "quality_score": quality_score,
            "plan_type": plan.plan_type.value,
            "metrics": metrics,
            "source": "generated",
        }

    def _stage_get(self) -> List[Dict[str, Any]]:
        """Stage 1: Load papers from database."""
        # In production, query database; for spike, return empty list
        # Papers are loaded as needed by Tool
        return []

    def _stage_plan(self, question: str, papers: List[Dict[str, Any]]) -> tuple:
        """Stage 2: Generate retrieval plan."""
        self.logger.on_log("→ Stage 2: Planning")
        self.logger.on_log("  Calling Claude to formalize query strategy...")

        start_time = time.time()
        plan = self.planner.formalize(question, papers)
        plan_time = (time.time() - start_time) * 1000
        plan_tokens = self.planner.plan_tokens

        self.logger.on_log(f"  ✓ Plan created ({plan_tokens} tokens, {plan_time:.0f}ms): {plan.plan_type.value}")
        if plan.reasoning:
            self.logger.on_log(f"    Reasoning: {plan.reasoning}")

        return plan, (plan_tokens, plan_time)

    def _stage_query(self, plan: SearchPlan) -> tuple:
        """Stage 3: Execute retrieval based on plan."""
        self.logger.on_log("→ Stage 3: Retrieval")
        self.logger.on_log(f"  Executing {len(plan.queries)} search query/queries from plan...")

        start_time = time.time()

        # Execute queries using specified tool methods
        results = []
        for i, (query, method) in enumerate(zip(plan.queries, plan.tool_methods), 1):
            self.logger.on_log(f"  [{i}/{len(plan.queries)}] {method}: {query[:60]}...")

            if method == "vector_search":
                result = self.tool.vector_search(query)
            elif method == "search_methodology":
                result = self.tool.search_methodology(query)
            elif method == "search_findings":
                result = self.tool.search_findings(query)
            else:
                result = self.tool.vector_search(query)  # Fallback

            results.append(result)

        # Merge results if multiple
        if len(results) > 1:
            self.logger.on_log(f"  Deduplicating results from {len(results)} queries...")
            retrieval_result = self.tool.deduplicate_results(results)
        else:
            retrieval_result = results[0] if results else None

        query_time = (time.time() - start_time) * 1000

        if retrieval_result:
            self.logger.on_log(
                f"  ✓ Retrieved {len(retrieval_result.chunks)} chunks from {retrieval_result.paper_count} papers ({query_time:.0f}ms)"
            )

        return retrieval_result, (query_time,)

    def _stage_evaluate(self, retrieval_result, question: str, papers: List[Dict[str, Any]]) -> Any:
        """Stage 4: Assess result quality."""
        self.logger.on_log("→ Stage 4: Evaluation")
        self.logger.on_log("  Assessing retrieval quality...")

        quality_score = self.evaluator.evaluate(retrieval_result, question, papers)

        self.logger.on_log(
            f"  ✓ Coverage {quality_score.coverage:.0f}%, "
            f"Relevance {quality_score.relevance:.0f}%, "
            f"Freshness {quality_score.freshness:.0f}%"
        )

        return quality_score

    def _stage_finalize(self, question: str, retrieval_result) -> tuple:
        """Stage 5: Generate and format final answer."""
        self.logger.on_log("→ Stage 5: Synthesis")
        self.logger.on_log(f"  Calling Claude to synthesize answer from {len(retrieval_result.chunks)} chunks...")

        synthesis_result = self.synthesizer.synthesize(question, retrieval_result)

        self.logger.on_log(
            f"  ✓ Answer generated ({synthesis_result.tokens_used} tokens, {synthesis_result.latency_ms:.0f}ms)"
        )
        if synthesis_result.citations:
            self.logger.on_log(f"  ✓ Extracted {len(synthesis_result.citations)} citations")

        return synthesis_result, ()

    def print_results(self, results: Dict[str, Any]):
        """Print formatted results using logger.

        Args:
            results: Dictionary with answer, metrics, citations, or error
        """
        if not self.logger:
            print(results)
            return

        # Handle error case
        if "error" in results:
            self.logger.on_error(results["error"], results.get("message"))
            return

        # Answer
        self.logger.on_answer(results["answer"])

        # Citations
        if results.get("citations"):
            citations_text = "\n".join([f"• {citation}" for citation in results["citations"]])
            self.logger.on_msg(f"Citations:\n{citations_text}")
        self.logger.on_msg("")  # Extra newline for spacing

        # Metrics
        metrics = results["metrics"]
        self.logger.on_metrics(
            {
                "Plan Tokens": metrics.plan_tokens,
                "Synthesis Tokens": metrics.synthesis_tokens,
                "Total Tokens": metrics.total_tokens,
                "Search Time (ms)": metrics.search_time_ms,
                "Total Time (ms)": metrics.total_time_ms,
            }
        )
