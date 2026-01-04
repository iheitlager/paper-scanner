#!/usr/bin/env python3
"""
Try 05: Unified RAG Agent - Textual TUI

Translates try_04 prompt_toolkit to Textual framework with native CSS styling:
- Cleaner markdown support natively
- Better async/reactive model
- Simpler widget composition via CSS
- Built-in spinner animation support

Stage flow: Get → Plan → Query → Evaluate → Finalize
"""

import os
import asyncio
import threading
import sys
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

# Disable tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

MODEL = "all-mpnet-base-v2"

import psycopg2
import pyperclip
from dotenv import load_dotenv
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
from textual.app import ComposeResult, App
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.binding import Binding

from paper_scanner.core.models import Paper

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))
from components import SimplifyingPlanner, Tool, Evaluator, Synthesizer, Memory, Router, Logger, DefaultLogger

load_dotenv()


def markdown_to_rich(text: str) -> str:
    """Convert markdown syntax to Rich markup for better rendering."""
    import re
    
    # Headers: # text -> [bold cyan]text[/bold cyan]
    text = re.sub(r'^### (.*?)$', r'[bold yellow]\1[/bold yellow]', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'[bold cyan]\1[/bold cyan]', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'[bold white]\1[/bold white]', text, flags=re.MULTILINE)
    
    # Bold: **text** -> [bold]text[/bold]
    text = re.sub(r'\*\*(.*?)\*\*', r'[bold]\1[/bold]', text)
    
    # Italic: *text* or _text_ -> [italic]text[/italic]
    text = re.sub(r'\*(.*?)\*', r'[italic]\1[/italic]', text)
    text = re.sub(r'_(.*?)_', r'[italic]\1[/italic]', text)
    
    # Code: `text` -> [cyan]text[/cyan]
    text = re.sub(r'`(.*?)`', r'[cyan]\1[/cyan]', text)
    text = re.sub(r'"(.*?)"', r'[cyan]\1[/cyan]', text)
    text = re.sub(r'\'(.*?)\'', r'[cyan]\1[/cyan]', text)

    # Numbers
    text = re.sub(r'(\d+)', r'[green]\1[/green]', text)
        
    return text


class HistoryManager:
    """Manages TUI query history."""
    
    def __init__(self):
        self.history_file = Path.home() / ".paper-scanner" / "history" / "tui_history"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()
        self.current_index = len(self.history)
    
    def _load_history(self) -> list:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return [line.strip() for line in f if line.strip()]
            except Exception:
                return []
        return []
    
    def add(self, query: str) -> None:
        """Add query to history."""
        if query and query not in self.history:
            self.history.append(query)
            self._save_history()
        self.current_index = len(self.history)
    
    def _save_history(self) -> None:
        """Save history to file."""
        try:
            with open(self.history_file, 'w') as f:
                for item in self.history:
                    f.write(f"{item}\n")
        except Exception:
            pass
    
    def get_previous(self) -> Optional[str]:
        """Get previous item in history."""
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]
        return None
    
    def get_next(self) -> Optional[str]:
        """Get next item in history."""
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]
        elif self.current_index == len(self.history) - 1:
            self.current_index = len(self.history)
            return ""
        return None


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


def load_papers(db_conn, limit: int = 1000):
    """Load papers from database as Paper objects."""
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
            authors=authors or [],
        )
        papers[db_id] = paper

    cur.close()
    return papers


class TextualLogger(Logger):
    """Logger implementation for Textual TUI."""
    
    def __init__(self, answer_panel, log_panel, metrics_panel, status_panel, app):
        self.answer_panel = answer_panel
        self.log_panel = log_panel
        self.metrics_panel = metrics_panel
        self.status_panel = status_panel
        self.app = app
    
    def on_question(self, text: str):
        """Log question."""
        content = f"\n❓ QUESTION:\n{text}\n"
        self.answer_panel.write(content)
        self.app.answer_text_buffer.append(f"❓ QUESTION:\n{text}")

    def on_answer(self, text: str):
        """Log answer with markdown rendering."""
        rich_text = markdown_to_rich(text)
        content = f"\n💡 ANSWER:\n{rich_text}\n"
        self.answer_panel.write(content)
        self.app.answer_text_buffer.append(f"💡 ANSWER:\n{text}")

    def on_log(self, text: str):
        """Log debug messages."""
        for line in text.split("\n"):
            if line.strip():
                # Write without extra newline since RichLog.write adds one
                self.log_panel.write(f"[dim]{line}[/dim]")
                self.app.log_text_buffer.append(line)
    
    def on_msg(self, text: Optional[str] = ""):
        """Log informational message."""
        content = f"{text}\n"
        self.answer_panel.write(content)
        self.app.answer_text_buffer.append(text)
    
    def on_error(self, error: str, msg: Optional[str] = None):
        """Log error."""
        error_text = f"[red]❌ ERROR: {error}[/red]"
        if msg:
            error_text += f"\n[yellow]{msg}[/yellow]"
        self.status_panel.update(error_text)
    
    def on_metrics(self, metrics: Dict[str, Any]):
        """Log metrics."""
        lines = [f"{k}: {v}" if isinstance(v, (int, str)) else f"{k}: {v:.2f}" 
                 for k, v in metrics.items()]
        self.metrics_panel.update("\n".join(lines))


class QueryApp(App):
    """Textual TUI for paper query interface."""
    
    TITLE = "Paper Scanner - RAG Query Interface"
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #answer-panel {
        border: round $panel;
        height: 8fr;
        text-wrap: wrap;
        width: 100%;
        max-width: 100%;
        overflow-y: auto;
    }
    
    #content-row {
        height: 2fr;
    }
    
    #log-panel {
        border: round $panel;
        width: 1fr;
        height: 1fr;
        text-wrap: wrap;
    }
    
    #metrics-panel {
        border: round $panel;
        width: 30;
        height: 1fr;
        text-wrap: wrap;
    }
    
    #status-panel {
        height: 1;
        background: $surface;
        text-wrap: wrap;
    }
    
    #query-input {
        height: 3;
        border: round $panel;
        text-wrap: wrap;
    }
    
    /* Focus styling */
    #answer-panel:focus {
        border: solid $accent;
    }
    
    #log-panel:focus {
        border: solid $accent;
    }
    
    #query-input:focus {
        border: solid $accent;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "copy_focused", "Copy Panel", show=True),
        Binding("ctrl+d", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+1", "focus_answer", "Q&A", show=True),
        Binding("ctrl+2", "focus_log", "Log", show=True),
        Binding("ctrl+0", "focus_input", "Input", show=True),
        Binding("escape", "focus_input", "Input", show=False),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
        Binding("up", "history_previous", "Prev History", show=False),
        Binding("down", "history_next", "Next History", show=False),
    ]
    
    def __init__(self, router: Router, papers: Dict[int, Paper]):
        super().__init__()
        self.router = router
        self.papers = papers
        self.history_manager = HistoryManager()
        # Buffers to track panel content for copying
        self.answer_text_buffer = []
        self.log_text_buffer = []
    
    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header(show_clock=True)
        
        # Answer panel
        self.answer_panel = RichLog(
            id="answer-panel",
            markup=True,
            wrap=True,
            auto_scroll=True,
        )
        self.answer_panel.border_title = "Question / Answer"
        yield self.answer_panel
        
        # Log + Metrics row
        with Horizontal(id="content-row"):
            self.log_panel = RichLog(
                id="log-panel",
                markup=True,
                auto_scroll=True,
            )
            self.log_panel.border_title = "Pipeline Log"
            yield self.log_panel
            
            self.metrics_panel = Static("", id="metrics-panel")
            self.metrics_panel.border_title = "Metrics"
            yield self.metrics_panel
        
        # Status bar
        self.status_panel = Static(
            "",
            id="status-panel",
        )
        yield self.status_panel
        
        # Input bar
        self.input = Input(
            placeholder="Type a question or command (help, papers, chunks, memory, history, clear)",
            id="query-input",
        )
        self.input.border_title = "Input"
        yield self.input
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Setup after app mounts."""
        self.router.logger = TextualLogger(
            self.answer_panel,
            self.log_panel,
            self.metrics_panel,
            self.status_panel,
            self,
        )
        
        # Focus input by default
        self.input.focus()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        query = event.value.strip()
        self.input.value = ""
        
        if not query:
            return
        
        command = query.lower()
        
        # Handle commands
        if command in ("exit", "quit", "q"):
            self.exit()
            return
        
        if command == "clear":
            self.answer_panel.clear()
            self.log_panel.clear()
            return
        
        if command == "help":
            self.answer_panel.write("""
[bold cyan]Commands:[/bold cyan]
  papers              Show available papers
  chunks              Show last query chunks
  memory              Show cache statistics
  history             Show recent query history
  help                This help message
  exit / Ctrl+C       Exit the session

[bold cyan]Otherwise:[/bold cyan]
  Type any question to query the papers
            """)
            return
        
        if command == "papers":
            papers_list = list(self.papers.values())[:10]
            papers_text = "\n".join([f"• {p.cite_key}: {p.apa}" for p in papers_list])
            self.answer_panel.write(f"[bold cyan]Available Papers:[/bold cyan]\n{papers_text}\n")
            return
        
        if command == "chunks":
            chunks = self.router.last_retrieval_chunks[:5] if hasattr(self.router, 'last_retrieval_chunks') else []
            if chunks:
                chunks_text = "\n".join([f"• {c['cite_key']}: {c['content'][:60]}..." for c in chunks])
                self.answer_panel.write(f"[bold cyan]Retrieved Chunks:[/bold cyan]\n{chunks_text}\n")
            else:
                self.answer_panel.write("[dim]No chunks yet[/dim]\n")
            return
        
        if command == "memory":
            stats = self.router.memory.get_statistics()
            stats_text = "\n".join([f"{k}: {v}" if isinstance(v, (int, str)) else f"{k}: {v:.2f}" for k, v in stats.items()])
            self.answer_panel.write(f"[bold cyan]Cache Statistics:[/bold cyan]\n{stats_text}\n")
            return
        
        if command == "history":
            history = self.router.memory.get_conversation_context(n=5)
            if history:
                history_text = "\n".join([f"[{i}] {h['question'][:60]}..." for i, h in enumerate(history, 1)])
                self.answer_panel.write(f"[bold cyan]History:[/bold cyan]\n{history_text}\n")
            else:
                self.answer_panel.write("[dim]No history yet[/dim]\n")
            return
        
        # Save query to history
        self.history_manager.add(query)
        
        # Run query asynchronously
        self.status_panel.update("[yellow]Processing query...[/yellow]")
        asyncio.create_task(self._run_query_async(query))
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark
    
    async def _run_query_async(self, query: str) -> None:
        """Run query in executor to avoid blocking UI."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._execute_query, query)
            self.status_panel.update("[green]Query completed[/green]")
        except Exception as e:
            self.status_panel.update("[red]Query failed[/red]")
    
    def _execute_query(self, query: str) -> None:
        """Execute query synchronously (runs in executor)."""
        try:
            results = self.router.route_query(query)
            self.router.print_results(results)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.router.logger.on_log(f"ERROR: {e}\n\nStacktrace:\n{tb}")
            self.router.logger.on_error(f"Error processing query: {e}")
    
    def action_copy_focused(self) -> None:
        """Copy content from the currently focused panel."""
        try:
            focused_widget = self.focused
            
            if focused_widget is self.answer_panel:
                text = "\n".join(self.answer_text_buffer)
                panel_name = "Q&A"
            elif focused_widget is self.log_panel:
                text = "\n".join(self.log_text_buffer)
                panel_name = "Log"
            elif focused_widget is self.metrics_panel:
                text = self.metrics_panel.renderable if hasattr(self.metrics_panel, 'renderable') else ""
                panel_name = "Metrics"
            else:
                self.notify("No copyable content in focused panel", timeout=2)
                return
            
            if text:
                pyperclip.copy(text)
                self.notify(f"Copied {panel_name} to clipboard", timeout=2)
            else:
                self.notify(f"{panel_name} panel is empty", timeout=2)
        except Exception as e:
            self.notify(f"Copy failed: {e}", timeout=2)
    
    def action_focus_answer(self) -> None:
        """Focus the Q&A panel."""
        self.query_one("#answer-panel").focus()
        self.status_panel.update("[cyan]Focus: Q&A Panel[/cyan] (↑↓ scroll, Escape=input)")
    
    def action_focus_log(self) -> None:
        """Focus the log panel."""
        self.query_one("#log-panel").focus()
        self.status_panel.update("[yellow]Focus: Log Panel[/yellow] (↑↓ scroll, Escape=input)")
    
    def action_focus_input(self) -> None:
        """Focus the input field."""
        self.query_one("#query-input", Input).focus()
        self.status_panel.update("")
    
    def action_focus_next(self) -> None:
        """Focus next panel."""
        self.screen.focus_next()
    
    def action_focus_previous(self) -> None:
        """Focus previous panel."""
        self.screen.focus_previous()
    
    def action_history_previous(self) -> None:
        """Navigate to previous query in history."""
        if self.input.has_focus:
            prev_query = self.history_manager.get_previous()
            if prev_query is not None:
                self.input.value = prev_query
    
    def action_history_next(self) -> None:
        """Navigate to next query in history."""
        if self.input.has_focus:
            next_query = self.history_manager.get_next()
            if next_query is not None:
                self.input.value = next_query

async def main():
    """Main entry point."""
    logger = DefaultLogger()
    
    try:
        logger.on_log("Initializing RAG Agent...")
        
        # Initialize tqdm's lock in main thread to avoid subprocess spawning later
        from tqdm import tqdm
        tqdm.get_lock()
        
        # Database
        db_conn = connect_db()
        
        # Encoder
        logger.on_log(f"Loading encoder model '{MODEL}'...")
        # Disable all parallelism in SentenceTransformer
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        os.environ["OPENBLAS_NUM_THREADS"] = "1"
        encoder = SentenceTransformer(MODEL)
        # Disable pooling to prevent subprocess spawning
        encoder.max_seq_length = 256
        
        # LLM Client
        llm_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Load papers
        papers = load_papers(db_conn)
        logger.on_log(f"✓ Loaded {len(papers)} papers")
        
        # Initialize components
        planner = SimplifyingPlanner(llm_client)
        tool = Tool(db_conn, encoder)
        evaluator = Evaluator()
        synthesizer = Synthesizer(llm_client)
        memory = Memory(encoder)
        
        # Create Router
        router = Router(planner=planner, tool=tool, evaluator=evaluator, synthesizer=synthesizer, memory=memory)
        
        logger.on_log("✓ Components initialized")
        logger.on_log("✓ Memory cache ready\n")
        
        # Run TUI
        app = QueryApp(router, papers)
        await app.run_async()
        
    except Exception as e:
        logger.on_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if "db_conn" in locals():
            db_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
