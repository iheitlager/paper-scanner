"""Semantic logging interface for the Router."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from rich.console import Console
from rich.theme import Theme
from rich.table import Table
from rich.markdown import Markdown

# Custom theme for markdown formatting
MARKDOWN_THEME = Theme(
    {
        "markdown.h1": "bold magenta",
        "markdown.h2": "bold cyan",
        "markdown.strong": "bold yellow",
        "markdown.emph": "italic green",
        "markdown.code": "dim yellow",
        "markdown.link": "underline blue",
    }
)


class Logger(ABC):
    """Abstract base class for semantic logging."""

    @abstractmethod
    def on_question(self, text: str):
        """Log a question (multiline, formatted text)."""
        pass

    @abstractmethod
    def on_answer(self, text: str):
        """Log an answer (multiline, formatted text)."""
        pass

    @abstractmethod
    def on_log(self, text: str):
        """Log a debug message (multiline text)."""
        pass

    @abstractmethod
    def on_msg(self, text: Optional[str] = ""):
        """Output a regular informational message."""
        pass

    @abstractmethod
    def on_error(self, error: str, msg: Optional[str] = None):
        """Log an error.

        Args:
            error: Single-line error message
            msg: Optional multiline detailed message
        """
        pass

    @abstractmethod
    def on_metrics(self, metrics: Dict[str, Any]):
        """Log metrics as key-value pairs."""
        pass


class DefaultLogger(Logger):
    """Default implementation using Rich console."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize logger.

        Args:
            console: Optional Rich Console instance (creates one with markdown theme if None)
        """
        self.console = console or Console(theme=MARKDOWN_THEME)

    def on_question(self, text: str):
        """Print question with formatting."""
        self.console.print(f"\n[bold cyan]Question:[/bold cyan]\n{text}\n")

    def on_answer(self, text: str):
        """Print answer with markdown formatting."""
        self.console.print(f"\n[bold yellow]Answer:[/bold yellow]\n")
        self.console.print(Markdown(text), justify="left")

    def on_msg(self, text: Optional[str] = ""):
        """Print informational message."""
        self.console.print(f"{text}")

    def on_log(self, text: str):
        """Print debug log line(s)."""
        for line in text.split("\n"):
            if line.strip():
                self.console.print(f"[dim]{line}[/dim]")

    def on_error(self, error: str, msg: Optional[str] = None):
        """Print error in red."""
        self.console.print(f"\n[red]✗ Error: {error}[/red]")
        if msg:
            self.console.print(f"[yellow]{msg}[/yellow]")

    def on_metrics(self, metrics: Dict[str, Any]):
        """Print metrics as a formatted table."""
        if not metrics:
            return

        self.console.print()
        table = Table(title="Metrics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        for key, value in metrics.items():
            # Format value based on type
            if isinstance(value, float):
                formatted_value = f"{value:.0f}" if value > 100 else f"{value:.2f}"
            else:
                formatted_value = str(value)

            table.add_row(key, formatted_value)

        self.console.print(table)


class SilentLogger(Logger):
    """Logger that does nothing (for testing)."""

    def on_question(self, text: str):
        pass

    def on_answer(self, text: str):
        pass

    def on_log(self, text: str):
        pass

    def on_msg(self, text: str):
        pass

    def on_error(self, error: str, msg: Optional[str] = None):
        pass

    def on_metrics(self, metrics: Dict[str, Any]):
        pass
