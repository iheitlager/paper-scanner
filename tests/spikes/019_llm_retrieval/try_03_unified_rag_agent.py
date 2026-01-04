#!/usr/bin/env python3
"""
Try 03: Unified RAG Agent - Query Simplification Architecture

Recreates try_02 functionality using the unified component architecture:
- Router orchestrates the 5-stage pipeline
- SimplifyingPlanner handles query keyword extraction
- Tool performs vector search
- Evaluator assesses result quality
- Synthesizer generates answer
- Memory manages caching and history

Stage flow: Get → Plan → Query → Evaluate → Finalize
"""

import os
import sys
from pathlib import Path

# Disable tokenizers parallelism warning (must be set before transformers import)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
MODEL = "all-mpnet-base-v2"

import psycopg2
from dotenv import load_dotenv
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from rich.table import Table
from paper_scanner.core.models import Paper

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))
from components import SimplifyingPlanner, Tool, Evaluator, Synthesizer, Memory, Router, DefaultLogger

# Load environment
load_dotenv()


def connect_db():
    """Connect to PostgreSQL."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "paper_scanner_dev"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432"),
    )
    return conn


def get_history_path() -> Path:
    """Get path to history file."""
    cache_dir = Path.home() / ".paper-scanner" / "history"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "unified_rag_history.txt"


def load_papers(db_conn, limit: int = 1000):
    """Load papers from database as Paper objects (like try_01 & try_02)."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT db_id, id, cite_key, doi, title, year, journal, volume, issue, abstract, authors
        FROM papers
        ORDER BY year DESC, cite_key
        LIMIT %s
    """,
        (limit,),
    )

    papers = {}  # Maps db_id -> Paper object
    for row in cur.fetchall():
        db_id, id_val, cite_key, doi, title, year, journal, volume, issue, abstract, authors = row

        # Create Paper object with full model including authors
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
            authors=authors or [],
        )
        papers[db_id] = paper

    cur.close()
    return papers


def setup_prompt_session():
    """Setup prompt_toolkit session with history."""
    history_path = get_history_path()
    return PromptSession(history=FileHistory(str(history_path)), mouse_support=False)


def show_papers_table(papers, limit=10):
    """Display papers in a nice table."""
    table = Table(title="Available Papers")

    table.add_column("Cite Key", style="cyan")
    table.add_column("APA")

    # papers is dict of db_id -> Paper object
    for paper in list(papers.values())[:limit]:
        table.add_row(paper.cite_key, paper.apa_formatted)

    return table


def show_chunks_table(chunks, limit=5):
    """Display retrieved chunks in a table."""
    table = Table(title="Retrieved Chunks")

    table.add_column("Paper", style="cyan")
    table.add_column("Section", style="green")
    table.add_column("Relevance", style="yellow")
    table.add_column("Preview", style="dim")

    for chunk in chunks[:limit]:
        table.add_row(
            f"{chunk['cite_key']} ({chunk['year']})",
            chunk.get("section", "N/A"),
            f"{chunk['similarity']:.2f}",
            chunk["content"][:40] + "...",
        )

    return table


def interactive_session(router: Router, papers, prompt_session, logger: DefaultLogger):
    """Run interactive REPL with command support."""
    logger.on_msg(
        "[bold cyan]RAG Agent - Query Simplification Architecture (try_03)[/bold cyan]\n"
        "Type 'help' for commands, 'exit' to quit, Ctrl+D to exit"
    )

    while True:
        try:
            user_input = prompt_session.prompt("? ").strip()
        except EOFError:
            user_input = "exit"
        except KeyboardInterrupt:
            continue

        if not user_input:
            continue

        command = user_input.lower()
        if command in ["exit", "quit", "q", "bye"]:
            logger.on_msg("[yellow]👋 Goodbye![/yellow]")
            break

        if command == "help":
            logger.on_msg("""
[bold cyan]Commands:[/bold cyan]
  papers              Show available papers
  chunks              Show last query chunks
  memory              Show cache statistics
  history             Show recent query history (last 5)
  help                This help message
  exit / Ctrl+D       Exit the session

[bold cyan]Otherwise:[/bold cyan]
  Type any question to query the papers
            """)
            continue

        if command == "papers":
            logger.on_msg(show_papers_table(papers))
            continue

        if command == "chunks":
            logger.on_msg(show_chunks_table(router.last_retrieval_chunks))
            continue

        if command == "memory":
            stats = router.memory.get_statistics()
            table = Table(show_header=False)
            for key, value in stats.items():
                table.add_row(key, str(value))
            logger.on_msg(table)
            continue

        if command == "history":
            history = router.memory.get_conversation_context(n=5)
            if history:
                for i, interaction in enumerate(history, 1):
                    logger.on_msg(f"[cyan][{i}] Q:[/cyan] {interaction['question'][:60]}...")
            else:
                logger.on_msg("[dim]No history yet[/dim]")
            continue

        # Process as question
        results = router.route_query(user_input)
        router.print_results(results)


def main():
    """Main entry point."""
    logger = DefaultLogger()

    try:
        # Initialize components
        logger.on_log("Initializing RAG Agent...")

        # Database
        db_conn = connect_db()

        # Encoder

        logger.on_log(f"Loading encoder model '{MODEL}'... ")
        encoder = SentenceTransformer(MODEL)

        # LLM Client
        llm_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Load papers as Paper objects
        papers = load_papers(db_conn)
        logger.on_log(f"✓ Loaded {len(papers)} papers")

        # Convert to list for Evaluator
        papers_list = list(papers.values())

        # Initialize components
        planner = SimplifyingPlanner(llm_client)
        tool = Tool(db_conn, encoder)
        evaluator = Evaluator()
        synthesizer = Synthesizer(llm_client)
        memory = Memory(encoder)

        # Create Router (orchestrator)
        router = Router(planner=planner, tool=tool, evaluator=evaluator, synthesizer=synthesizer, memory=memory)

        logger.on_log("✓ Components initialized")
        logger.on_log("✓ Memory cache ready\n")

        # Interactive session
        prompt_session = setup_prompt_session()
        interactive_session(router, papers, prompt_session, logger)

    except Exception as e:
        logger.on_error(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
    finally:
        if "db_conn" in locals():
            db_conn.close()


if __name__ == "__main__":
    main()
