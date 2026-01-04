#!/usr/bin/env python
"""
Spike 019 - Architecture 1: Retrieve-Then-Read (Baseline)

This is the baseline retrieval architecture from Spike 018.

Flow:
    User question → Encoder embeds question → pgvector similarity search 
    → Top-k chunks retrieved → LLM synthesizes

This implementation serves as the reference point for comparing with other
retrieval architectures (LLM-as-router, query-decomposition, HyDE, iterative).

Usage:
    python try_01_retrieve_then_read.py

Examples of questions:
    - "What do papers say about digital transformation?"
    - "Who discusses platform ecosystems?"
    - "What methodologies are used in digital business research?"
"""

import os
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv

from paper_scanner.core.models import Paper

# Disable tokenizer parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
import anthropic
from sentence_transformers import SentenceTransformer
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Import prompt_toolkit for history and better REPL
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

# Initialize rich console for colored output
console = Console()

# Load environment
load_dotenv()


@dataclass
class QueryMetrics:
    """Metrics for retrieval and synthesis"""
    query_text: str
    embedding_time: float
    search_time: float
    llm_calls: int
    llm_tokens_in: int
    llm_tokens_out: int
    total_time: float
    chunks_retrieved: int
    

def get_db_url():
    """Build database URL from env"""
    db_user = os.getenv("DB_USER", "pdfuser")
    db_password = os.getenv("DB_PASSWORD", "pdfpass")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "paper_scanner")
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class RetrieveThenReadEngine:
    """
    Baseline retrieval architecture: Encode query → Vector search → LLM synthesis
    
    This is the reference implementation from Spike 018.
    Used to benchmark other retrieval strategies.
    """

    def __init__(self):
        """Initialize engine with encoder, database, and LLM"""
        self.conn = psycopg2.connect(get_db_url())
        register_vector(self.conn)
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-haiku-4-5-20251001"
        
        # Initialize encoder
        console.print("[dim]Loading encoder model...[/dim]")
        self.encoder = SentenceTransformer("all-mpnet-base-v2")
        
        self.load_papers()
        self.metrics_log = []
        
        # Initialize prompt session with history
        self._setup_prompt_session()

    def load_papers(self):
        """Load papers and their info into memory as Paper objects"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT db_id, id, cite_key, doi, title, year, journal, volume, issue, abstract, authors
            FROM papers
            ORDER BY year DESC, cite_key
        """
        )
        self.papers = {}  # Maps db_id to Paper object
        for row in cursor.fetchall():
            db_id, id_val, cite_key, doi, title, year, journal, volume, issue, abstract, authors = row
            
            # Create Paper object
            paper = Paper(
                db_id=db_id,
                id=id_val,
                cite_key=cite_key,
                doi=doi,
                title=title,
                year=year,
                journal=journal,
                volume=volume,
                issue=issue,
                abstract=abstract,
                authors=authors
            )
            self.papers[db_id] = paper
        cursor.close()
        console.print(f"[green]✓[/green] Loaded [bold cyan]{len(self.papers)}[/bold cyan] papers from database")

    def _setup_prompt_session(self):
        """Setup prompt_toolkit session with history file"""
        # Create cache directory for history
        cache_dir = Path.home() / ".cache" / "paper-scanner" / "spike019"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # History file for REPL
        history_file = cache_dir / ".retrieve_then_read_history"
        self.history = FileHistory(str(history_file))
        
        # Setup key bindings for tab expansion
        kb = KeyBindings()
        
        @kb.add('tab')
        def _(event):
            """Convert tab to spaces"""
            event.current_buffer.insert_text('  ')
        
        # Setup prompt session with rich console styling
        self.prompt_session = PromptSession(
            completer=WordCompleter(
                ["papers", "metrics", "help", "exit", "quit"],
                ignore_case=True
            ),
            history=self.history,
            enable_history_search=True,
            style=Style.from_dict({
                "completion-menu.completion": "bg:#008888 #ffffff",
                "completion-menu.completion.current": "bg:#00aaaa #000000",
                "prompt": "#00aa00 bold",
            }),
            key_bindings=kb,
        )

    def retrieve_similar_chunks(self, query_text: str, limit: int = 5, verbose: bool = True) -> tuple[List[Dict], Dict[str, Any]]:
        """
        Retrieve similar chunks using vector search.
        
        Steps:
        1. Process query text
        2. Encode question to 768-dimensional vector using all-mpnet-base-v2 encoder
        3. Query PostgreSQL database with pgvector cosine distance similarity
        4. Return top-k most similar chunks with metadata
        
        Returns:
            Tuple of (results, retrieval_info)
        """
        start_time = time.time()
        
        if verbose:
            console.print("\n[bold cyan]═══ RETRIEVAL PIPELINE ═══[/bold cyan]")
            console.print(f"[cyan]📝 Input Question:[/cyan] [yellow]\"{query_text}\"[/yellow]")
        
        # ========== STEP 1: Process Query ==========
        if verbose:
            console.print("\n[bold green]STEP 1: QUESTION PROCESSING[/bold green]")
            console.print(f"  [dim]✓ Question length: {len(query_text)} characters[/dim]")
            console.print(f"  [dim]✓ Word count: {len(query_text.split())} words[/dim]")
            console.print(f"  [dim]✓ Requesting top {limit} most similar chunks[/dim]")
        
        # ========== STEP 2: Embedding ==========
        if verbose:
            console.print("\n[bold green]STEP 2: EMBEDDING QUESTION[/bold green]")
            console.print("  [dim]Model: all-mpnet-base-v2[/dim]")
            console.print("  [dim]Output dimensions: 768[/dim]")
        
        embed_start = time.time()
        query_embedding = self.encoder.encode(query_text)
        embed_time = time.time() - embed_start
        
        if verbose:
            console.print(f"  [green]✓ Encoded in {embed_time:.4f}s[/green]")
            console.print(f"  [dim]  Vector shape: {query_embedding.shape}[/dim]")
            console.print(f"  [dim]  Vector norm: {np.linalg.norm(query_embedding):.4f}[/dim]")
            console.print(f"  [dim]  First 5 values: [{', '.join(f'{v:.4f}' for v in query_embedding[:5])}][/dim]")

        # ========== STEP 3: Database Query ==========
        if verbose:
            console.print("\n[bold green]STEP 3: DATABASE SIMILARITY SEARCH[/bold green]")
            console.print("  [dim]Executing PostgreSQL pgvector query:[/dim]")
            console.print("  [dim]  SELECT embedding <=> query_vector (cosine distance)[/dim]")
            console.print("  [dim]  JOIN chunk_embeddings → paper_chunks → papers[/dim]")
            console.print(f"  [dim]  ORDER BY distance LIMIT {limit}[/dim]")
        
        search_start = time.time()
        cursor = self.conn.cursor()
        
        # Execute the similarity search with pgvector
        cursor.execute(
            """
            SELECT 
                ce.id,
                p.db_id,
                p.cite_key,
                p.title,
                p.year,
                pc.section,
                pc.text,
                ce.embedding <=> %s::vector as distance
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_id = pc.id
            JOIN papers p ON pc.paper_id = p.db_id
            ORDER BY ce.embedding <=> %s::vector
            LIMIT %s
        """,
            (query_embedding, query_embedding, limit),
        )

        results = cursor.fetchall()
        cursor.close()
        search_time = time.time() - search_start

        if verbose:
            console.print(f"  [green]✓ Query executed in {search_time:.4f}s[/green]")
            console.print(f"  [green]✓ Retrieved {len(results)} chunks[/green]")
        
        # ========== STEP 4: Format Results ==========
        if verbose:
            console.print("\n[bold green]STEP 4: FORMATTING RESULTS[/bold green]")
        
        formatted_results = []
        for i, r in enumerate(results):
            similarity = float(1 - r[7]) * 100
            formatted_results.append({
                "chunk_id": r[0],
                "paper_db_id": r[1],
                "cite_key": r[2],
                "paper_title": r[3],
                "year": r[4],
                "section": r[5],
                "text": r[6][:500] + ("..." if len(r[6]) > 500 else ""),
                "distance": float(r[7]),
                "similarity": similarity,
            })
            if verbose and i < 3:  # Show details for top 3
                console.print(f"  [dim]  {i+1}. {r[2]} ({r[4]}) - Section: {r[5]} - Similarity: {similarity:.1f}%[/dim]")

        retrieval_info = {
            "embedding_time": embed_time,
            "search_time": search_time,
            "chunks_retrieved": len(formatted_results),
        }

        if verbose:
            console.print(f"  [green]✓ Formatted {len(formatted_results)} result(s)[/green]")

        return formatted_results, retrieval_info

    def format_search_results(self, results: List[Dict]) -> str:
        """Format search results for display"""
        if not results:
            return "[yellow]No relevant papers found.[/yellow]"

        output = []
        output.append("\n[bold magenta]📄 RETRIEVED CHUNKS:[/bold magenta]")
        output.append("[dim]" + "=" * 80 + "[/dim]")

        for i, result in enumerate(results, 1):
            similarity_pct = result['similarity']
            color = "green" if similarity_pct > 80 else "yellow" if similarity_pct > 60 else "white"
            output.append(f"\n[bold cyan]{i}.[/bold cyan] [bold]{result['cite_key']}[/bold] [dim]({result['year']})[/dim]")
            output.append(f"   [blue]Title:[/blue] {result['paper_title']}")
            output.append(f"   [blue]Section:[/blue] {result['section']}")
            output.append(f"   [blue]Similarity:[/blue] [{color}]{similarity_pct:.1f}%[/{color}]")
            output.append(f"   [blue]Content:[/blue] {result['text']}")
            output.append("[dim]" + "-" * 80 + "[/dim]")

        return "\n".join(output)

    def synthesize_with_llm(self, user_question: str, search_results: List[Dict], verbose: bool = True) -> tuple[str, Dict[str, Any]]:
        """
        Use LLM to synthesize findings from retrieved chunks.
        
        Steps:
        1. Build context from papers and search results
        2. Construct detailed prompt with examples
        3. Send to Claude API with max_tokens limit
        4. Parse response and track token usage
        
        Returns:
            Tuple of (synthesis_text, synthesis_info)
        """
        if verbose:
            console.print("\n[bold cyan]═══ SYNTHESIS PIPELINE ═══[/bold cyan]")
        
        # ========== STEP 1: Build Context ==========
        if verbose:
            console.print("\n[bold green]STEP 1: BUILD CONTEXT FOR LLM[/bold green]")
        
        # Format papers info for context
        papers_context = "\n\n".join(
            [
                f"- {p.cite_key}: {p.apa_formatted}"
                for p in self.papers.values()
            ]
        )
        
        if verbose:
            console.print(f"  [green]✓ Formatted {len(self.papers)} papers in database[/green]")
            console.print(f"  [dim]  Papers context size: {len(papers_context)} characters[/dim]")

        # Format search results for Claude
        results_context = "\n\n".join(
            [
                f"From {r['cite_key']} ({r['year']}):\n"
                f"Section: {r['section']}\n"
                f"Similarity: {r['similarity']:.1f}%\n"
                f"Quote: {r['text']}"
                for r in search_results
            ]
        )
        
        if verbose:
            console.print(f"  [green]✓ Formatted {len(search_results)} retrieved chunks[/green]")
            console.print(f"  [dim]  Results context size: {len(results_context)} characters[/dim]")

        prompt = f"""You are an academic research assistant helping with a literature review.
A user asked: "{user_question}"

Available papers in database:
{papers_context}

Most relevant findings from vector search:
{results_context}

Based on these findings, provide a synthesis answer to the user's question about "who says what".

Format your response EXACTLY as follows (use [bold]...[/bold], [cyan]...[/cyan], [yellow]...[/yellow] for Rich markup - NO markdown):

[bold]1. Direct Answer[/bold]
<direct answer to the question>

[bold]2. Key Findings by Paper[/bold]
For each paper, format as:
[cyan]<paper_cite_key> (<year>)[/cyan] - "<title>"
  - <key finding>
  - <another finding>

[bold]3. Patterns and Insights[/bold]
<observations about patterns>

[bold]4. Suggested Follow-Up Questions[/bold]
- <question 1>
- <question 2>

Use [cyan]...[/cyan] for paper names, [yellow]...[/yellow] for important terms, [bold]...[/bold] for headings.
NO markdown syntax (no #, ##, **, etc). Be specific about which papers make which claims."""

        # ========== STEP 2: Prepare API Call ==========
        if verbose:
            console.print("\n[bold green]STEP 2: PREPARE LLM API CALL[/bold green]")
            console.print(f"  [dim]Model: {self.model}[/dim]")
            console.print(f"  [dim]Max tokens: 1024[/dim]")
            console.print(f"  [dim]Prompt size: {len(prompt)} characters[/dim]")
            console.print(f"  [dim]Estimated prompt tokens: ~{len(prompt) // 4}[/dim]")

        # ========== STEP 3: Call Claude API ==========
        if verbose:
            console.print("\n[bold green]STEP 3: SEND REQUEST TO CLAUDE API[/bold green]")
        
        start_time = time.time()
        spinner = Spinner("dots", text="[cyan]Calling Claude API...[/cyan]")
        with Live(spinner, console=console, refresh_per_second=12.5):
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
        synthesis_time = time.time() - start_time

        if verbose:
            console.print(f"  [green]✓ API call completed in {synthesis_time:.4f}s[/green]")
        
        # ========== STEP 4: Parse Response ==========
        if verbose:
            console.print("\n[bold green]STEP 4: PARSE RESPONSE[/bold green]")
            console.print(f"  [dim]Response status: {message.stop_reason}[/dim]")
            console.print(f"  [dim]Output tokens: {message.usage.output_tokens}[/dim]")
            console.print(f"  [dim]Input tokens: {message.usage.input_tokens}[/dim]")
            console.print(f"  [dim]Total tokens: {message.usage.input_tokens + message.usage.output_tokens}[/dim]")
        
        synthesis_response = message.content[0].text

        synthesis_info = {
            "llm_calls": 1,
            "llm_tokens_in": message.usage.input_tokens,
            "llm_tokens_out": message.usage.output_tokens,
            "llm_time": synthesis_time,
        }

        if verbose:
            console.print(f"  [green]✓ Response length: {len(synthesis_response)} characters[/green]")

        return synthesis_response, synthesis_info

    def query(self, user_question: str, limit: int = 5, verbose: bool = True) -> Dict[str, Any]:
        """
        Execute retrieve-then-read pipeline for a single query.
        
        Full pipeline flow:
        1. [RETRIEVAL] Embed question to 768-dim vector
        2. [RETRIEVAL] Query pgvector for top-k similar chunks
        3. [RETRIEVAL] Return formatted results with similarity scores
        4. [SYNTHESIS] Build context from papers and chunks
        5. [SYNTHESIS] Call Claude API with synthetic prompt
        6. [SYNTHESIS] Parse response and track tokens
        
        Returns full query result with metrics and detailed steps.
        """
        query_start = time.time()

        # Step 1: Retrieve
        search_results, retrieval_info = self.retrieve_similar_chunks(user_question, limit=limit, verbose=verbose)

        if not search_results:
            return {
                "status": "no_results",
                "question": user_question,
                "message": "No relevant papers found",
                "metrics": {
                    "total_time": time.time() - query_start,
                    "chunks_retrieved": 0,
                }
            }

        # Step 2: Synthesize
        synthesis, synthesis_info = self.synthesize_with_llm(user_question, search_results, verbose=verbose)

        total_time = time.time() - query_start

        if verbose:
            console.print("\n[bold cyan]═══ PIPELINE COMPLETE ═══[/bold cyan]")

        result = {
            "status": "success",
            "question": user_question,
            "retrieved_chunks": search_results,
            "synthesis": synthesis,
            "metrics": {
                "embedding_time": retrieval_info["embedding_time"],
                "search_time": retrieval_info["search_time"],
                "llm_time": synthesis_info["llm_time"],
                "total_time": total_time,
                "chunks_retrieved": len(search_results),
                "llm_tokens_in": synthesis_info["llm_tokens_in"],
                "llm_tokens_out": synthesis_info["llm_tokens_out"],
            }
        }

        # Log metrics
        self.metrics_log.append(result["metrics"])

        return result

    def display_result(self, result: Dict[str, Any]):
        """Display query result with formatting"""
        if result["status"] == "no_results":
            console.print("[bold red]❌ No relevant papers found.[/bold red] Try a different question.")
            return

        # Display retrieved chunks
        console.print(self.format_search_results(result["retrieved_chunks"]))

        # Display synthesis
        synthesis_panel = Panel(
            result["synthesis"],
            title="[bold magenta]📝 SYNTHESIS[/bold magenta]",
            border_style="magenta"
        )
        console.print(synthesis_panel)

        # Display metrics
        metrics = result["metrics"]
        metrics_text = (
            f"⏱️ [cyan]Embedding:[/cyan] {metrics['embedding_time']:.3f}s | "
            f"[cyan]Search:[/cyan] {metrics['search_time']:.3f}s | "
            f"[cyan]LLM:[/cyan] {metrics['llm_time']:.3f}s | "
            f"[cyan]Total:[/cyan] {metrics['total_time']:.3f}s\n"
            f"📊 [cyan]Chunks:[/cyan] {metrics['chunks_retrieved']} | "
            f"[cyan]Tokens:[/cyan] {metrics['llm_tokens_in']} in + {metrics['llm_tokens_out']} out"
        )
        metrics_panel = Panel(metrics_text, title="[bold blue]📈 METRICS[/bold blue]", border_style="blue")
        console.print(metrics_panel)

    def interactive_session(self):
        """Run interactive query session with history"""
        help_panel = Panel(
            "[bold]🔍 RETRIEVE-THEN-READ RETRIEVAL[/bold]\n"
            "[dim]Spike 019 - Architecture 1 (Baseline)[/dim]\n\n"
            "Use natural language to ask questions about papers.\n\n"
            "[cyan]Examples:[/cyan]\n"
            "  • 'What do papers say about digital transformation?'\n"
            "  • 'Who discusses platform ecosystems?'\n"
            "  • 'What methodologies are used?'\n\n"
            "[cyan]Commands:[/cyan]\n"
            "  [bold]exit[/bold] or [bold]quit[/bold] - Exit\n"
            "  [bold]papers[/bold] - List papers\n"
            "  [bold]metrics[/bold] - Show aggregated metrics\n"
            "  [bold]help[/bold] - Show help\n\n"
            "[dim]💡 Use ↑/↓ arrows or Ctrl+R to search history\n"
            "💡 Press Ctrl+D to close the script[/dim]",
            title="[bold magenta]Welcome[/bold magenta]",
            border_style="magenta"
        )
        console.print(help_panel)

        query_count = 0
        
        while True:
            try:
                # Use prompt_session for input with history
                user_input = self.prompt_session.prompt(
                    "🔍 Your question: ",
                    enable_history_search=True
                ).strip()
                
                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\n[yellow]👋 Goodbye![/yellow]")
                    break

                if user_input.lower() == "papers":
                    table = Table(title="📖 PAPERS IN DATABASE", show_header=True, header_style="bold magenta")
                    table.add_column("Cite Key", style="cyan")
                    table.add_column("APA")
                    for db_id, paper in sorted(
                        self.papers.items(), key=lambda x: x[1].year or 0, reverse=True
                    ):
                        table.add_row(
                            paper.cite_key,
                            paper.apa_formatted
                        )
                    console.print(table)
                    continue

                if user_input.lower() == "metrics":
                    if not self.metrics_log:
                        console.print("[yellow]No queries executed yet.[/yellow]")
                        continue

                    total_queries = len(self.metrics_log)
                    avg_total = sum(m["total_time"] for m in self.metrics_log) / total_queries
                    avg_embedding = sum(m["embedding_time"] for m in self.metrics_log) / total_queries
                    avg_search = sum(m["search_time"] for m in self.metrics_log) / total_queries
                    avg_llm = sum(m["llm_time"] for m in self.metrics_log) / total_queries
                    total_tokens_in = sum(m["llm_tokens_in"] for m in self.metrics_log)
                    total_tokens_out = sum(m["llm_tokens_out"] for m in self.metrics_log)

                    metrics_text = (
                        f"[bold cyan]Queries Executed:[/bold cyan] {total_queries}\n"
                        f"[bold cyan]Average Total Time:[/bold cyan] {avg_total:.3f}s\n"
                        f"  - Embedding: {avg_embedding:.3f}s\n"
                        f"  - Search: {avg_search:.3f}s\n"
                        f"  - LLM: {avg_llm:.3f}s\n"
                        f"[bold cyan]Total LLM Tokens:[/bold cyan] {total_tokens_in + total_tokens_out}\n"
                        f"  - Input: {total_tokens_in}\n"
                        f"  - Output: {total_tokens_out}"
                    )
                    metrics_panel = Panel(metrics_text, title="[bold blue]📊 AGGREGATED METRICS[/bold blue]", border_style="blue")
                    console.print(metrics_panel)
                    continue

                if user_input.lower() == "help":
                    help_text = Panel(
                        "[bold cyan]ARCHITECTURE:[/bold cyan]\n"
                        "Query → Embed → pgvector search → LLM synthesizes\n\n"
                        "[bold cyan]COMMANDS:[/bold cyan]\n"
                        "  [bold]papers[/bold]   - List all papers\n"
                        "  [bold]metrics[/bold]  - Show aggregated metrics\n"
                        "  [bold]exit[/bold]     - Exit program\n"
                        "  [bold]help[/bold]     - Show this help\n\n"
                        "[bold cyan]HISTORY:[/bold cyan]\n"
                        "  [bold]↑/↓[/bold]      - Navigate history\n"
                        "  [bold]Ctrl+R[/bold]   - Search history\n"
                        "  [bold]Ctrl+S[/bold]   - Forward search\n\n"
                        "[bold cyan]QUESTION TYPES:[/bold cyan]\n"
                        "  • Simple: 'What do papers say about X?'\n"
                        "  • Topic: 'Who discusses X?'\n"
                        "  • Method: 'What methodologies are used?'",
                        title="[bold magenta]Help[/bold magenta]",
                        border_style="cyan"
                    )
                    console.print(help_text)
                    continue

                # Process question
                query_count += 1
                console.print("\n[bold blue]⏳ Executing retrieve-then-read pipeline...[/bold blue]")
                result = self.query(user_input, verbose=True)
                self.display_result(result)
                console.print(f"\n[cyan]💡 Query #{query_count} complete. Try follow-up questions![/cyan]")

            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Interrupted. Goodbye![/yellow]")
                break
            except EOFError:
                # Ctrl+D closes the script
                console.print("\n[yellow]👋 EOF received. Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
                console.print("[dim]Please try another question.[/dim]")

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    banner = Panel(
        "[bold cyan]🚀 RETRIEVE-THEN-READ ENGINE[/bold cyan]\n"
        "[dim]Spike 019 - Architecture 1 (Baseline from Spike 018)[/dim]",
        border_style="cyan"
    )
    console.print(banner)

    try:
        engine = RetrieveThenReadEngine()
        console.print("\n[bold green]✅ Engine ready! Starting interactive session...[/bold green]")
        engine.interactive_session()

    except Exception as e:
        console.print(f"\n[bold red]❌ Error initializing engine:[/bold red] {e}")
        sys.exit(1)
    finally:
        try:
            engine.close()
        except:
            pass


if __name__ == "__main__":
    main()
