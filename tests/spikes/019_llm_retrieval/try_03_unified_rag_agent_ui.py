#!/usr/bin/env python3
"""
Try 03 UI: Unified RAG Agent with Multi-Panel Layout

Recreates try_03 with a split-panel UI:
- Top: Question/Answer (scrollable)
- Middle: Debug Log (left, scrollable) + Metrics (right, fixed width)
- Bottom: Input bar

Uses prompt_toolkit for layout management and real-time updates.
"""
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional
from collections import deque
from io import StringIO

# Disable tokenizers parallelism warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import psycopg2
from dotenv import load_dotenv
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, ScrollablePane
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.enums import EditingMode
from rich.console import Console as RichConsole
from rich.table import Table

from paper_scanner.core.models import Paper

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))
from components import (
    SimplifyingPlanner, Tool, Evaluator, Synthesizer, Memory, Router
)

# Load environment
load_dotenv()


class PanelManager:
    """Manages multi-panel UI state and updates."""
    
    def __init__(self):
        self.answer_text = ""
        self.log_lines = deque(maxlen=200)  # Keep last 200 log lines
        self.metrics_text = "Tokens: 0\nTime: 0ms\nCoverage: --\nRelevance: --"
        self.status_text = "[Ready]"
        
    def append_log(self, message: str):
        """Add a line(s) to the debug log."""
        for line in message.split('\n'):
            if line:  # Skip empty lines
                self.log_lines.append(line)
    
    def set_answer(self, text: str):
        """Set the answer/Q&A text."""
        self.answer_text = text
    
    def set_metrics(self, tokens: int, time_ms: float, coverage: float = 0, relevance: float = 0):
        """Update metrics display."""
        self.metrics_text = f"""Tokens: {tokens}
Time: {time_ms:.0f}ms
Coverage: {coverage:.0f}%
Relevance: {relevance:.0f}%"""
    
    def set_status(self, status: str):
        """Set status indicator."""
        self.status_text = status
    
    def get_log_text(self) -> str:
        """Get formatted log text."""
        return "\n".join(self.log_lines)
    
    def clear_logs(self):
        """Clear all logs."""
        self.log_lines.clear()


class LoggingHandler(logging.Handler):
    """Send all logging to panel manager."""
    
    def __init__(self, panel_manager: 'PanelManager'):
        super().__init__()
        self.panel_manager = panel_manager
    
    def emit(self, record):
        try:
            msg = self.format(record)
            self.panel_manager.append_log(msg)
        except Exception:
            self.handleError(record)


def connect_db():
    """Connect to PostgreSQL."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "paper_scanner_dev"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432")
    )
    return conn


def load_papers(db_conn, limit: int = 1000):
    """Load papers from database as Paper objects."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT db_id, id, cite_key, doi, title, year, journal, volume, issue, abstract, authors
        FROM papers
        ORDER BY year DESC, cite_key
        LIMIT %s
    """, (limit,))
    
    papers = {}
    for row in cur.fetchall():
        db_id, id_val, cite_key, doi, title, year, journal, volume, issue, abstract, authors = row
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
            authors=authors or []
        )
        papers[db_id] = paper
    
    cur.close()
    return papers


def build_layout(panel_manager: PanelManager, input_text_area: TextArea):
    """Build the multi-panel layout."""
    answer_control = FormattedTextControl(text=lambda: panel_manager.answer_text)
    log_control = FormattedTextControl(text=lambda: panel_manager.get_log_text())
    metrics_control = FormattedTextControl(text=lambda: panel_manager.metrics_text)
    status_control = FormattedTextControl(text=lambda: panel_manager.status_text)
    
    root = HSplit([
        # Top: Question/Answer (60% height, scrollable)
        Frame(
            ScrollablePane(Window(answer_control, wrap_lines=True)),
            title="Question / Answer",
        ),
        
        # Middle: Debug Log (left, scrollable) + Metrics (right, fixed 28 width)
        VSplit([
            Frame(
                ScrollablePane(Window(log_control, wrap_lines=True)),
                title="Pipeline Log",
            ),
            Frame(
                Window(metrics_control, wrap_lines=True),
                title="Metrics",
                width=28,
            ),
        ], height=12),
        
        # Status line
        Window(status_control, height=1),
        
        # Bottom: Input area (fixed height)
        Frame(
            input_text_area,
            title="Query",
            height=3,
        ),
    ])
    
    return Layout(root)


def main():
    """Main entry point with multi-panel UI."""
    import sys
    
    # Check if we're in a real terminal
    is_tty = sys.stdout.isatty()
    
    # Initialize panel manager FIRST
    panel_manager = PanelManager()
    panel_manager.append_log("Initializing RAG Agent...")
    
    try:
        # Connect to database
        panel_manager.append_log("Connecting to database...")
        db_conn = connect_db()
        panel_manager.append_log("✓ Database connected")
        
        # Load encoder
        panel_manager.append_log("Loading encoder model...")
        encoder = SentenceTransformer('all-mpnet-base-v2')
        panel_manager.append_log("✓ Encoder loaded")
        
        # Initialize LLM
        panel_manager.append_log("Initializing LLM client...")
        llm_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        panel_manager.append_log("✓ LLM client ready")
        
        # Load papers
        panel_manager.append_log("Loading papers from database...")
        papers = load_papers(db_conn)
        panel_manager.append_log(f"✓ Loaded {len(papers)} papers")
        papers_list = list(papers.values())
        
        # Initialize components
        panel_manager.append_log("Initializing pipeline components...")
        planner = SimplifyingPlanner(llm_client)
        tool = Tool(db_conn, encoder)
        evaluator = Evaluator()
        synthesizer = Synthesizer(llm_client)
        memory = Memory(encoder)
        panel_manager.append_log("✓ All components initialized")
        
        # Create Router
        router = Router(
            planner=planner,
            tool=tool,
            evaluator=evaluator,
            synthesizer=synthesizer,
            memory=memory,
            verbose=True
        )
        panel_manager.append_log("✓ Router ready")
        panel_manager.append_log("\n[Ready for queries]")
        
        # Set initial answer text
        panel_manager.set_answer(
            "[bold cyan]Unified RAG Agent - Query Simplification[/bold cyan]\n\n"
            "Type a question below to start.\n"
            "Commands: papers, memory, history, help, exit\n"
            "Press Ctrl+C to quit."
        )
        
        # BUILD UI AFTER ALL COMPONENTS INITIALIZED
        panel_manager.append_log("\nBuilding UI...")
        input_text_area = TextArea(
            text="",
            prompt=">>> ",
            multiline=False,
        )
        layout = build_layout(panel_manager, input_text_area)
        panel_manager.append_log("✓ UI ready")
        panel_manager.append_log("\n=== APP STARTING ===")
        
        # Key bindings
        kb = KeyBindings()
        
        @kb.add('c-c')
        @kb.add('c-q')
        def exit_(event):
            panel_manager.set_status("[yellow]Exiting...[/yellow]")
            event.app.exit()
        
        @kb.add('enter')
        def handle_enter(event):
            question = input_text_area.text.strip()
            if not question:
                return
            
            input_text_area.text = ""
            
            if question.lower() == 'exit':
                event.app.exit()
                return
            
            if question.lower() == 'help':
                panel_manager.set_answer("""[bold cyan]Commands:[/bold cyan]
  papers      - Show available papers
  memory      - Show cache statistics
  history     - Show recent queries
  help        - This help message
  exit        - Exit the session

[bold cyan]Otherwise:[/bold cyan]
  Type any question to query the papers""")
                return
            
            if question.lower() == 'papers':
                table = Table(title="Available Papers")
                table.add_column("Cite Key", style="cyan")
                table.add_column("Title", style="yellow")
                table.add_column("Year", style="green")
                for paper in list(papers.values())[:15]:
                    table.add_row(paper.cite_key, paper.title[:40], str(paper.year))
                
                # Render table to string for display
                with StringIO() as buffer:
                    temp_console = RichConsole(file=buffer)
                    temp_console.print(table)
                    panel_manager.set_answer(buffer.getvalue())
                return
            
            if question.lower() == 'memory':
                stats = router.memory.get_statistics()
                text = "[bold cyan]Memory Statistics:[/bold cyan]\n"
                for key, value in stats.items():
                    text += f"{key}: {value}\n"
                panel_manager.set_answer(text)
                return
            
            if question.lower() == 'history':
                history = router.memory.get_conversation_context(n=5)
                if history:
                    text = "[bold cyan]Recent Queries:[/bold cyan]\n"
                    for i, interaction in enumerate(history, 1):
                        text += f"\n[{i}] {interaction['question'][:60]}...\n"
                    panel_manager.set_answer(text)
                else:
                    panel_manager.set_answer("[dim]No history yet[/dim]")
                return
            
            # Process question
            panel_manager.set_status("[blue]Processing...[/blue]")
            panel_manager.clear_logs()
            panel_manager.append_log(f"Processing: {question}\n")
            
            results = router.route_query(question)
            
            # Update panels with results
            if 'error' in results:
                panel_manager.set_answer(f"[red]✗ Error: {results['error']}[/red]\n{results.get('message', '')}")
                panel_manager.append_log(f"\n[ERROR] {results.get('message', '')}")
                panel_manager.set_status("[red][Error][/red]")
            else:
                answer = results.get('answer', '')
                panel_manager.set_answer(f"[bold yellow]ANSWER:[/bold yellow]\n\n{answer}")
                
                metrics = results.get('metrics', {})
                quality = results.get('quality_score', {})
                panel_manager.set_metrics(
                    tokens=metrics.total_tokens if metrics else 0,
                    time_ms=metrics.total_time_ms if metrics else 0,
                    coverage=quality.coverage if quality else 0,
                    relevance=quality.relevance if quality else 0,
                )
                
                # Add citations to log
                if results.get('citations'):
                    panel_manager.append_log("Citations:")
                    for citation in results['citations']:
                        panel_manager.append_log(f"  • {citation}")
                
                panel_manager.set_status("[green][Ready][/green]")
        
        # Create and run application
        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=True,
            enable_page_navigation_bindings=True,
        )
        
        if not is_tty:
            print("ERROR: Not running in a TTY. This app requires an interactive terminal.")
            print("Run with: uv run tests/spikes/019_llm_retrieval/try_03_unified_rag_agent_ui.py")
            sys.exit(1)
        
        print(f"\n[DEBUG] TTY detected, starting app. Panel manager has {len(panel_manager.log_lines)} log lines")
        app.run()
        
    except KeyboardInterrupt:
        panel_manager.append_log("\n[yellow]Interrupted[/yellow]")
    except Exception as e:
        panel_manager.append_log(f"\n[red]Error: {e}[/red]")
        import traceback
        panel_manager.append_log(traceback.format_exc())
        # Print to stderr so we see the error
        print(f"\nERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        if 'db_conn' in locals():
            db_conn.close()


if __name__ == "__main__":
    main()
