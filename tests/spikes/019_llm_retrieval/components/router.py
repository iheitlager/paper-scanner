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


class Router:
    """Orchestrates the 5-stage RAG pipeline: Get → Plan → Query → Evaluate → Finalize."""

    def __init__(self,
                 planner: BasePlanner,
                 tool: Tool,
                 evaluator: Evaluator,
                 synthesizer: Synthesizer,
                 memory: Memory,
                 verbose: bool = False):
        """
        Initialize Router with components.
        
        Args:
            planner: Strategy decision-maker
            tool: Database interface
            evaluator: Quality assessor
            synthesizer: Answer generator
            memory: Cache and history
            verbose: Print verbose output
        """
        self.planner = planner
        self.tool = tool
        self.evaluator = evaluator
        self.synthesizer = synthesizer
        self.memory = memory
        self.verbose = verbose
        self.console = Console() if verbose else None

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
                'error': 'incomplete_question',
                'message': f'Question too short ({len(words)} word). Please ask a full question with at least 2 words.',
                'source': 'error'
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
            return validation_error
        
        start_time = time.time()
        metrics = PipelineMetrics()
        
        if self.verbose:
            self.console.print(f"\n[bold cyan]─────────────────────────────────────[/bold cyan]")
            self.console.print(f"[bold cyan]Question:[/bold cyan] {question}")
            self.console.print(f"[bold cyan]─────────────────────────────────────[/bold cyan]\n")
        
        # === Stage 1: Get ===
        if self.verbose:
            self.console.print(f"[bold blue]→ Stage 1: Initialization[/bold blue]")
        papers = self._stage_get()
        if self.verbose:
            self.console.print(f"[green]  ✓ Papers loaded[/green]")
        
        # Check memory for cached result
        if self.verbose:
            self.console.print(f"[dim]  Checking memory for similar queries...[/dim]")
        cached = self.memory.find_similar_query(question)
        if cached:
            if self.verbose:
                self.console.print(f"[yellow]  ⚡ Cache hit! Using similar cached result[/yellow]")
            return {
                'answer': cached['answer'],
                'source': 'cache',
                'metrics': metrics
            }
        if self.verbose:
            self.console.print(f"[dim]  No cache hit, proceeding with full pipeline[/dim]\n")
        
        # === Stage 2: Plan ===
        plan, plan_metrics = self._stage_plan(question, papers)
        metrics.plan_tokens = plan_metrics[0]
        metrics.plan_time_ms = plan_metrics[1]
        
        if self.verbose:
            self.console.print()
        
        # === Stage 3: Query ===
        retrieval_result, query_metrics = self._stage_query(plan)
        metrics.search_time_ms = query_metrics[0]
        metrics.chunks_found = len(retrieval_result.chunks)
        
        if self.verbose:
            self.console.print()
        
        # === Stage 4: Evaluate ===
        quality_score = self._stage_evaluate(retrieval_result, question, papers)
        
        if self.verbose:
            self.console.print()
        
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
            metrics=metrics
        )
        
        # Finalize metrics
        metrics.total_tokens = metrics.plan_tokens + metrics.synthesis_tokens
        metrics.total_time_ms = time.time() - start_time
        
        if self.verbose:
            self.console.print(f"\n[bold green]─────────────────────────────────────[/bold green]")
            self.console.print(f"[bold green]✓ PIPELINE COMPLETE[/bold green]")
            self.console.print(f"[green]Total: {metrics.total_tokens} tokens in {metrics.total_time_ms:.0f}ms[/green]")
            self.console.print(f"[bold green]─────────────────────────────────────[/bold green]\n")
        
        return {
            'answer': synthesis_result.answer_text,
            'citations': synthesis_result.citations,
            'chunks': retrieval_result.chunks,
            'quality_score': quality_score,
            'plan_type': plan.plan_type.value,
            'metrics': metrics,
            'source': 'generated'
        }

    def _stage_get(self) -> List[Dict[str, Any]]:
        """Stage 1: Load papers from database."""
        # In production, query database; for spike, return empty list
        # Papers are loaded as needed by Tool
        return []

    def _stage_plan(self, question: str, papers: List[Dict[str, Any]]) -> tuple:
        """Stage 2: Generate retrieval plan."""
        if self.verbose:
            self.console.print(f"[bold blue]→ Stage 2: Planning[/bold blue]")
            self.console.print(f"[dim]  Calling Claude to formalize query strategy...[/dim]")
        
        start_time = time.time()
        plan = self.planner.formalize(question, papers)
        plan_time = (time.time() - start_time) * 1000
        plan_tokens = self.planner.plan_tokens
        
        if self.verbose:
            self.console.print(f"[green]  ✓ Plan created ({plan_tokens} tokens, {plan_time:.0f}ms): {plan.plan_type.value}[/green]")
            if plan.reasoning:
                self.console.print(f"[dim]    Reasoning: {plan.reasoning}[/dim]")
        
        return plan, (plan_tokens, plan_time)

    def _stage_query(self, plan: SearchPlan) -> tuple:
        """Stage 3: Execute retrieval based on plan."""
        if self.verbose:
            self.console.print(f"[bold blue]→ Stage 3: Retrieval[/bold blue]")
            self.console.print(f"[dim]  Executing {len(plan.queries)} search query/queries from plan...[/dim]")
        
        start_time = time.time()
        
        # Execute queries using specified tool methods
        results = []
        for i, (query, method) in enumerate(zip(plan.queries, plan.tool_methods), 1):
            if self.verbose:
                self.console.print(f"[dim]  [{i}/{len(plan.queries)}] {method}: {query[:60]}...[/dim]")
            
            if method == 'vector_search':
                result = self.tool.vector_search(query)
            elif method == 'search_methodology':
                result = self.tool.search_methodology(query)
            elif method == 'search_findings':
                result = self.tool.search_findings(query)
            else:
                result = self.tool.vector_search(query)  # Fallback
            
            results.append(result)
        
        # Merge results if multiple
        if len(results) > 1:
            if self.verbose:
                self.console.print(f"[dim]  Deduplicating results from {len(results)} queries...[/dim]")
            retrieval_result = self.tool.deduplicate_results(results)
        else:
            retrieval_result = results[0] if results else None
        
        query_time = (time.time() - start_time) * 1000
        
        if self.verbose and retrieval_result:
            self.console.print(f"[green]  ✓ Retrieved {len(retrieval_result.chunks)} chunks from {retrieval_result.paper_count} papers ({query_time:.0f}ms)[/green]")
        
        return retrieval_result, (query_time,)

    def _stage_evaluate(self,
                       retrieval_result,
                       question: str,
                       papers: List[Dict[str, Any]]) -> Any:
        """Stage 4: Assess result quality."""
        if self.verbose:
            self.console.print(f"[bold blue]→ Stage 4: Evaluation[/bold blue]")
            self.console.print(f"[dim]  Assessing retrieval quality...[/dim]")
        
        quality_score = self.evaluator.evaluate(
            retrieval_result,
            question,
            papers
        )
        
        if self.verbose:
            self.console.print(f"[green]  ✓ Coverage {quality_score.coverage:.0f}%, "
                              f"Relevance {quality_score.relevance:.0f}%, "
                              f"Freshness {quality_score.freshness:.0f}%[/green]")
        
        return quality_score

    def _stage_finalize(self, question: str, retrieval_result) -> tuple:
        """Stage 5: Generate and format final answer."""
        if self.verbose:
            self.console.print(f"[bold blue]→ Stage 5: Synthesis[/bold blue]")
            self.console.print(f"[dim]  Calling Claude to synthesize answer from {len(retrieval_result.chunks)} chunks...[/dim]")
        
        synthesis_result = self.synthesizer.synthesize(
            question,
            retrieval_result,
            verbose=self.verbose
        )
        
        if self.verbose:
            self.console.print(f"[green]  ✓ Answer generated ({synthesis_result.tokens_used} tokens, {synthesis_result.latency_ms:.0f}ms)[/green]")
            if synthesis_result.citations:
                self.console.print(f"[green]  ✓ Extracted {len(synthesis_result.citations)} citations[/green]")
        
        return synthesis_result, ()

    def print_results(self, results: Dict[str, Any], convert_markdown: bool = True):
        """Print formatted results.
        
        Args:
            results: Dictionary with answer, metrics, citations, or error
            convert_markdown: If True, render answer as markdown; if False, print as plain text
        """
        if not self.console:
            print(results)
            return
        
        console = self.console
        
        # Handle error case
        if 'error' in results:
            console.print(f"\n[red]✗ Error: {results['error']}[/red]")
            if 'message' in results:
                console.print(f"[yellow]{results['message']}[/yellow]")
            return
        
        # Answer
        console.print(f"\n[bold yellow]ANSWER:[/bold yellow]")
        if convert_markdown:
            console.print(Markdown(results['answer']))
        else:
            console.print(results['answer'])
        
        # Metrics
        metrics = results['metrics']
        console.print(f"\n[bold cyan]Metrics:[/bold cyan]")
        table = Table(show_header=False)
        table.add_row("Plan Tokens", str(metrics.plan_tokens))
        table.add_row("Synthesis Tokens", str(metrics.synthesis_tokens))
        table.add_row("Total Tokens", str(metrics.total_tokens))
        table.add_row("Search Time", f"{metrics.search_time_ms:.0f}ms")
        table.add_row("Total Time", f"{metrics.total_time_ms:.0f}ms")
        console.print(table)
        
        # Citations
        if results.get('citations'):
            console.print(f"\n[bold cyan]Citations:[/bold cyan]")
            for citation in results['citations']:
                console.print(f"  • {citation}")
