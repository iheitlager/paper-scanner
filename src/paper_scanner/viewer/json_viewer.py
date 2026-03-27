"""JSON viewer - rich-based interactive JSON viewer for paper-scanner"""

import os
import sys
import termios
import tty
from typing import Any

# Disable tokenizers parallelism to avoid fork deadlocks
# (happens when viewing papers with text chunks that use embedding models)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from rich.console import Console

from paper_scanner.viewer.json_controller import JSONController


class JSONViewer:
    """Rich-based interactive JSON viewer."""

    def __init__(self, data: Any, title: str = "JSON Viewer"):
        """Initialize JSON viewer with data."""
        self.console = Console()
        self.controller = JSONController(data, title)
        self.running = False
        self.message = ""
        self.search_mode = False
        self.search_query = ""

    def render(self) -> None:
        """Render current view."""
        self.console.clear()

        # Get terminal dimensions
        term_size = os.popen("stty size", "r").read().split()
        max_y = int(term_size[0]) if term_size else 24
        max_x = int(term_size[1]) if len(term_size) > 1 else 80

        # Header (1 line)
        self.console.print(f"[bold cyan]{self.controller.title}[/bold cyan]")

        # Available space for JSON tree (reserve 4 lines for footer and buffer)
        content_height = max(max_y - 5, 10)

        # JSON tree
        visible_start = self.controller.scroll_offset
        visible_end = min(
            len(self.controller.flat_nodes),
            self.controller.scroll_offset + content_height,
        )

        for i in range(visible_start, visible_end):
            node = self.controller.flat_nodes[i]
            indent = "  " * node.depth
            is_selected = i == self.controller.cursor

            # Build line
            indicator = ""
            if not node.is_leaf:
                indicator = "▼ " if node.expanded else "▶ "
            else:
                indicator = "  "

            # Build content
            content_parts = []
            if node.key:
                content_parts.append(f"[cyan]{node.key}[/cyan]: ")
            content_parts.append(node.get_display_value())
            content = "".join(content_parts)

            # Format line, truncate if necessary
            line = f"{indent}{indicator}{content}"
            if len(line) > max_x - 2:
                line = line[: max_x - 5] + "..."

            # Highlight selection
            if is_selected:
                self.console.print(f"[bold on blue]{line}[/bold on blue]")
            else:
                self.console.print(line)

        # Footer (3 lines)
        nav_help = "[dim]Navigation: [cyan]↑/↓[/cyan] or [cyan]j/k[/cyan]  [cyan]←/→[/cyan] or [cyan]h/l[/cyan] collapse/expand  [cyan]/[/cyan] search  [cyan]q[/cyan] quit[/dim]"
        self.console.print(nav_help)

        if self.controller.get_current_node():
            node = self.controller.get_current_node()
            action_help = "[dim]Actions: [cyan]v[/cyan] value  [cyan]p[/cyan] path  [cyan]n/N[/cyan] next/prev search[/dim]"
            self.console.print(action_help)

        # Status or search input
        if self.search_mode:
            # Escape the search query to prevent Rich markup errors
            escaped_query = self.search_query.replace("[", r"\[").replace("]", r"\]")
            self.console.print(f"[cyan]/[/cyan] {escaped_query}[dim]_[/dim]")
        else:
            if self.message:
                self.console.print(self.message)
            else:
                # Position info
                if self.controller.get_current_node():
                    path = self.controller.get_current_path()
                    pos = f"[dim]{self.controller.cursor + 1}/{len(self.controller.flat_nodes)} | {path}[/dim]"
                    self.console.print(pos)

    def _get_key(self) -> str:
        """Get a single key press from terminal."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            # Check for escape sequences (arrow keys)
            if ch == "\x1b":  # ESC sequence
                next_ch = sys.stdin.read(1)
                if next_ch == "[":
                    arrow = sys.stdin.read(1)
                    if arrow == "C":  # Right arrow
                        return "right"
                    elif arrow == "D":  # Left arrow
                        return "left"
                    elif arrow == "A":  # Up arrow
                        return "up"
                    elif arrow == "B":  # Down arrow
                        return "down"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def run(self) -> None:
        """Start interactive viewer loop."""
        self.running = True
        self.render()

        try:
            while self.running:
                try:
                    key = self._get_key()

                    if self.search_mode:
                        # In search mode, handle text input
                        if key in ("\x1b",):  # ESC - cancel search
                            self.search_mode = False
                            self.search_query = ""
                            self.message = ""
                        elif key in ("q", "Q"):  # Q - quit search
                            self.search_mode = False
                            self.search_query = ""
                            self.message = ""
                        elif key == "\r":  # Enter - apply search
                            self.controller.search(self.search_query)
                            self.search_mode = False
                            self.message = self.controller.status_message
                        elif key == "\x08" or key == "\x7f":  # Backspace
                            self.search_query = self.search_query[:-1]
                        elif len(key) == 1 and ord(key) >= 32:  # Printable
                            self.search_query += key
                        self.render()
                    else:
                        # Normal mode - navigation and actions
                        if key in ("q", "Q", "\x1b"):  # Quit
                            self.running = False
                        elif key == "/" :  # Enter search mode
                            self.search_mode = True
                            self.search_query = ""
                            self.message = ""
                            self.render()
                            continue
                        elif key in ("up", "k"):
                            self.message = ""
                            self.controller.navigate_up()
                        elif key in ("down", "j"):
                            self.message = ""
                            self.controller.navigate_down()
                        elif key in ("left", "h"):
                            self.message = ""
                            self.controller.collapse_current()
                        elif key in ("right", "l"):
                            self.message = ""
                            self.controller.expand_current()
                        elif key in (" ", "\r"):  # Space or Enter
                            self.message = ""
                            self.controller.toggle_expand_current()
                        elif key == "g":
                            self.message = ""
                            self.controller.navigate_to_top()
                        elif key == "G":
                            self.message = ""
                            self.controller.navigate_to_bottom()
                        elif key == "v":  # Copy value
                            value = self.controller.get_current_value_for_clipboard()
                            if value and self.controller.copy_to_clipboard(value):
                                self.message = f"[green]✓ Value copied to clipboard ({len(value)} chars)[/green]"
                            else:
                                self.message = "[red]✗ Failed to copy to clipboard[/red]"
                        elif key == "p":  # Copy path
                            path = self.controller.get_current_path()
                            if path and self.controller.copy_to_clipboard(path):
                                self.message = f"[green]✓ Path copied: {path}[/green]"
                            else:
                                self.message = "[red]✗ Failed to copy path[/red]"
                        elif key == "n":  # Next search result
                            self.controller.next_search_result()
                            self.message = self.controller.status_message
                        elif key == "N":  # Previous search result
                            self.controller.prev_search_result()
                            self.message = self.controller.status_message

                        # Update scroll offset with dynamic terminal height
                        term_size = os.popen("stty size", "r").read().split()
                        max_y = int(term_size[0]) if term_size else 24
                        content_height = max(max_y - 5, 10)
                        self.controller.update_scroll_offset(content_height)
                        self.render()

                except EOFError:
                    self.running = False
        finally:
            pass

    def stop(self) -> None:
        """Stop the viewer."""
        self.running = False


def view_json(data: Any, title: str = "JSON Viewer") -> None:
    """View JSON data interactively."""
    viewer = JSONViewer(data, title)
    viewer.run()
