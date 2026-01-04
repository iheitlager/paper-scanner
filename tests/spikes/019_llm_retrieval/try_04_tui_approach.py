#!/usr/bin/env python3
"""
Try 03: Unified RAG Agent - Query Simplification Architecture

Recreates try_03 functionality but with a Textual User Interface (TUI):
- Router orchestrates the 5-stage pipeline
- SimplifyingPlanner handles query keyword extraction
- Tool performs vector search
- Evaluator assesses result quality
- Synthesizer generates answer
- Memory manages caching and history

Stage flow: Get → Plan → Query → Evaluate → Finalize
"""

import os
import threading
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import sys
import time

# Disable tokenizers parallelism warning (must be set before transformers import)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
MODEL = "all-mpnet-base-v2"

import psycopg2
from dotenv import load_dotenv
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, ScrollablePane
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.widgets import Frame
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.table import Table
from rich.markdown import Markdown

from rich.console import Console
from io import StringIO

def render_markdown_to_ansi(text: str) -> str:
    console = Console(file=StringIO(), force_terminal=True, width=80)
    console.print(Markdown(text))
    return console.file.getvalue()

from paper_scanner.core.models import Paper


# Add components to path
sys.path.insert(0, str(Path(__file__).parent))
from components import SimplifyingPlanner, Tool, Evaluator, Synthesizer, Memory, Router, Logger, DefaultLogger

# Load environment
load_dotenv()

# Define styles
style = Style.from_dict(
    {
        # Frame titles
        "frame.label": "bold fg:cyan",
        # Frame borders
        "frame.border": "fg:#444444",
        # Different panel title colors via custom classes
        "answer-title": "bold fg:magenta",
        "log-title": "bold fg:yellow",
        "metrics-title": "bold fg:green",
        "input-title": "bold fg:cyan",
        # status bar
        "status": "bg:#1a1a1a fg:#888888",
        "status.error": "bg:#661111 fg:white bold",
        "status.success": "bg:#116611 fg:white",        
    }
)


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


class TUILogger(Logger):
    """Logger implementation that writes to prompt_toolkit panels."""

    SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']  # Braille spinner

    def __init__(
        self,
        answer_control: FormattedTextControl,
        log_control: FormattedTextControl,
        metrics_control: FormattedTextControl,
        status_control: FormattedTextControl,
        app: Application,
        answer_frame = None,
    ):
        self.answer_control = answer_control
        self.log_control = log_control
        self.metrics_control = metrics_control
        self.status_control = status_control
        self.app = app
        self._log_buffer: list[str] = []
        self.old_answer_text = None
        self.answer_frame = answer_frame
        self.spinner_index = 0
        self._spinner_thread = None
        self._spinner_stop = False
        self._original_title = "Question / Answer"


    def _refresh(self):
        """Request UI refresh."""
        self.app.invalidate()

    def _set_frame_title(self, title: str):
        """Update the answer frame title."""
        if self.answer_frame:
            self.answer_frame.title = title

    def _start_spinner(self):
        """Start spinner animation in background thread."""
        self._spinner_stop = False

        def animate():
            spinner_index = 0
            while not self._spinner_stop:
                spinner_char = self.SPINNER[spinner_index % len(self.SPINNER)]
                self._set_frame_title(f"{spinner_char} {self._original_title}")
                self._refresh()
                spinner_index += 1
                time.sleep(0.1)  # 100ms delay

        self._spinner_thread = threading.Thread(target=animate, daemon=True)
        self._spinner_thread.start()
    
    def _stop_spinner(self):
        """Stop spinner animation and restore original title."""
        self._spinner_stop = True
        if self._spinner_thread:
            self._spinner_thread.join(timeout=0.2)
        self._set_frame_title(self._original_title)
        self._refresh()

    def on_question(self, text: str):
        current = self.old_answer_text or self.answer_control.text or ""
        self.answer_control.text = f"{current}\n\n❓ QUESTION:\n{text}"
        self.status_control.text = ""
        self.old_answer_text = None
        # Start spinner animation
        self._start_spinner()
        self._refresh()

    def on_answer(self, text: str):
        current = self.answer_control.text or ""
        text =render_markdown_to_ansi(text)
        self.answer_control.text = f"{current}\n\n💡 ANSWER:\n{text}"
        self.status_control.text = ""
        # Stop spinner and restore title
        self._stop_spinner()

    def on_log(self, text: str):
        self._log_buffer.append(text)
        # Keep last 100 lines
        self._log_buffer = self._log_buffer[-100:]
        self.log_control.text = "\n".join(self._log_buffer)
        self._refresh()

    def on_msg(self, text: Optional[str] = ""):
        current = self.answer_control.text or ""
        self.answer_control.text = f"{current}\n{text}"
        self.status_control.text = ""
        self._refresh()

    def on_error(self, error: str, msg: Optional[str] = None):
        error_text = f"❌ ERROR: {error}"
        if msg:
            error_text += f"\n   {msg}"
        self.status_control.text = error_text
        self._refresh()

    def on_metrics(self, metrics: Dict[str, Any]):
        lines = [f"{k}: {v}" if isinstance(v, (int, str)) else f"{k}: {v:.2f}" for k, v in metrics.items()]
        self.metrics_control.text = "\n".join(lines)
        self._refresh()

    def on_help(self, msg: str):
        self.old_answer_text = self.answer_control.text or ""
        self.answer_control.text = msg
        self._refresh()


class QueryTUI:
    """Full-screen TUI for paper queries."""

    def __init__(self, router: Router, papers: Dict[int, Paper]):
        """
        Args:
            on_query_submit: Callback(query: str, logger: Logger) called when user submits query
        """

        # Content controls
        self.answer_text = FormattedTextControl(text="Enter a query below to search papers...")
        self.logging_text = FormattedTextControl(text="Pipeline logs will appear here...")
        self.metrics_text = FormattedTextControl(text="")
        self.status_text = FormattedTextControl(text="")

        # Input area with history
        self.input_buffer = Buffer(
            history=FileHistory(str(get_history_path())),
            accept_handler=self._handle_input,
            multiline=False,
        )

        # Create panes so we can focus them later
        self.answer_pane = ScrollablePane(Window(self.answer_text, wrap_lines=True))
        self.answer_frame = Frame(self.answer_pane, title="Question / Answer")
        self.log_pane = ScrollablePane(Window(self.logging_text, wrap_lines=True))
        self.input_window = Window(
            BufferControl(buffer=self.input_buffer),
            height=1,
            style="class:toolbar.text",
            get_line_prefix=lambda l, w: [("class:toolbar.prompt", " >>> ")],
        )

        # Layout
        self.layout = Layout(
            HSplit(
                [
                    # Top: Q&A (scrollable, flex height)
                    self.answer_frame,
                    # Mid: Logging + Metrics
                    VSplit(
                        [
                            Frame(self.log_pane, title="Pipeline Log"),
                            Frame(Window(self.metrics_text), title="Metrics", width=30),
                        ],
                        height=12,
                    ),
                    # Bottom: Input (fixed)
                    Window(
                        self.status_text,
                        height=1,
                        style="class:status",
                    ),
                    # Input toolbar
                    self.input_window,
                ]
            )
        )

        # Key bindings
        self.kb = KeyBindings()

        @self.kb.add("c-d")
        @self.kb.add("c-q")
        def exit_(event):
            event.app.exit()

        # Tab cycles focus between panels
        @self.kb.add("tab")
        def focus_next(event):
            event.app.layout.focus_next()

        @self.kb.add("s-tab")
        def focus_prev(event):
            event.app.layout.focus_previous()

        # Scroll focused panel with arrow keys / page up/down
        @self.kb.add("up")
        def scroll_up(event):
            self._scroll_focused(-1)

        @self.kb.add("down")
        def scroll_down(event):
            self._scroll_focused(1)

        @self.kb.add("pageup")
        def page_up(event):
            self._scroll_focused(-10)

        @self.kb.add("pagedown")
        def page_down(event):
            self._scroll_focused(10)

        # Quick focus shortcuts (use Alt+N)
        @self.kb.add("escape", "1")
        def focus_answer(event):
            self.status_text.text = FormattedText([("class:status", " Focus: Q&A Panel (↑↓ to scroll) ")])
            event.app.layout.focus(self.answer_pane)
            event.app.invalidate()

        @self.kb.add("escape", "2")
        def focus_log(event):
            self.status_text.text = FormattedText([("class:status", " Focus: Log Panel (↑↓ to scroll) ")])
            event.app.layout.focus(self.log_pane)
            event.app.invalidate()

        @self.kb.add("escape", "3")
        def focus_input(event):
            self.status_text.text = FormattedText([("class:status", " Focus: Input ")])
            event.app.layout.focus(self.input_window)
            event.app.invalidate()

        # Application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            style=style,
            mouse_support=True,
        )

        # Logger wired to panels
        self.logger = TUILogger(
            self.answer_text,
            self.logging_text,
            self.metrics_text,
            self.status_text,
            self.app,
            self.answer_frame,
        )

        self.router = router
        self.router.logger = self.logger
        self.papers = papers

    def _scroll_focused(self, lines: int):
        """Scroll the currently focused scrollable pane."""
        focused = self.app.layout.current_window
        # Find parent ScrollablePane
        for pane in [self.answer_pane, self.log_pane]:
            if pane.is_modal or focused in pane.get_children():
                pane.vertical_scroll += lines
                self.app.invalidate()
                return

    def _handle_input(self, buff):
        """Handle query submission."""
        query = buff.text.strip()
        if not query:
            return

        buff.text = ""  # Clear input

        command = query.lower()
        # Handle commands
        if command in ("exit", "quit", "q"):
            self.app.exit()
            return

        if command == "clear":
            self.answer_text.text = ""
            self.logging_text.text = ""
            return

        if command == "help":
            self.logger.on_help("""
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
            return

        if command == "papers":
            self.logger.on_msg(show_papers_table(self.papers))
            return

        if command == "chunks":
            self.logger.on_msg(show_chunks_table(self.router.last_retrieval_chunks))
            return

        if command == "memory":
            stats = self.router.memory.get_statistics()
            table = Table(show_header=False)
            for key, value in stats.items():
                table.add_row(key, str(value))
            self.logger.on_msg(table)
            return

        if command == "history":
            history = self.router.memory.get_conversation_context(n=5)
            if history:
                for i, interaction in enumerate(history, 1):
                    self.logger.on_msg(f"[cyan][{i}] Q:[/cyan] {interaction['question'][:60]}...")
            else:
                self.logger.on_msg("[dim]No history yet[/dim]")
            return

        # Run query in background thread so UI stays responsive
        def run_query():
            try:
                results = self.router.route_query(query)
                self.router.print_results(results)
            except Exception as e:
                self.logger.on_error(str(e))
        
        thread = threading.Thread(target=run_query, daemon=True)
        thread.start()

    def run(self):
        """Start the TUI."""
        self.app.run()


def main():
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
        # papers_list = list(papers.values())

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
        # interactive_session(router, papers, prompt_session, logger)
        tui = QueryTUI(router, papers)
        tui.run()

    except Exception as e:
        logger.on_error(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
    finally:
        if "db_conn" in locals():
            db_conn.close()


# Usage example
if __name__ == "__main__":
    main()
