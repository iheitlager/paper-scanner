"""ConsoleViewer - MVC View for rendering papers in the console"""

import sys
import termios
import tty
import subprocess
from typing import List, Callable, Optional

from rich.console import Console
from rich.panel import Panel

from paper_scanner.core.models import Paper
from paper_scanner.viewer.console_controller import PaperListController


class ConsoleViewer:
    """View layer for displaying papers in paginated console format"""

    def __init__(self, papers: List[Paper], page_size: int = 10):
        """Initialize viewer with papers"""
        self.console = Console()
        self.controller = PaperListController(papers, page_size)
        self.running = False
        self.message = ""  # For displaying copy/search feedback
        self.mode = "full"  # "full" or "filter"
        self.filter_query = ""  # Current filter input
        self.filtered_indices = None  # Cached filtered results

    def render_page(self) -> None:
        """Render current page of papers"""
        self.console.clear()

        page_info = self.controller.get_page_info()
        
        # In filter mode, show only filtered papers
        if self.mode == "filter" and self.filtered_indices:
            papers_to_show = [self.controller.papers[i] for i in self.filtered_indices]
            start_idx = 1  # Start numbering from 1
        else:
            papers_to_show = self.controller.get_current_page_papers()
            start_idx = page_info['start_index']

        # Papers
        for i, paper in enumerate(papers_to_show):
            idx = start_idx + i
            
            # Check if this paper is selected
            is_selected = (self.controller.selected_index == i)
            
            if is_selected:
                # Highlight selected paper with background color
                self.console.print(f"[cyan bold on blue]{idx}.[/cyan bold on blue][bold on blue] {paper.apa}[/bold on blue]")
            else:
                self.console.print(f"[cyan]{idx}.[/cyan] {paper.apa}")
            
            self.console.print()

        # Footer - 4 lines
        line1 = "[dim]Navigation: [cyan]↑/↓[/cyan] select  [cyan]→/←[/cyan] page[/dim]"
        self.console.print(line1)
        
        if self.controller.get_selected_paper():
            line2 = "[dim]Selected: [cyan]d[/cyan] details  [cyan]b[/cyan] bibtex  [cyan]i[/cyan] doi  [cyan]c[/cyan] json  [cyan]:[/cyan] search  [cyan]?[/cyan] help  [cyan]q[/cyan] quit[/dim]"
            self.console.print(line2)
        else:
            line2 = "[dim]Selected: (none)  [cyan]q[/cyan] quit[/dim]"
            self.console.print(line2)
        
        # Line 3: Page info or filter status
        if self.mode == "filter":
            match_count = len(self.filtered_indices) if self.filtered_indices else 0
            line3 = f"[yellow][Filter mode] Matching {match_count} papers — Press ESC/Enter to exit[/yellow]"
        else:
            page_info = self.controller.get_page_info()
            line3 = f"[dim]Page {page_info['current_page']}/{page_info['total_pages']} — {page_info['end_index']}/{page_info['papers_total']} papers[/dim]"
        self.console.print(line3)
        
        # Line 4: Messages or filter input
        if self.mode == "filter":
            self.console.print(f"[cyan]:[/cyan] {self.filter_query}[dim]_[/dim]")
        else:
            self.console.print(self.message)

    def _get_key(self) -> str:
        """Get a single key press from terminal"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            # Check for escape sequences (arrow keys)
            if ch == '\x1b':  # ESC sequence
                next_ch = sys.stdin.read(1)
                if next_ch == '[':
                    arrow = sys.stdin.read(1)
                    if arrow == 'C':  # Right arrow
                        return 'right'
                    elif arrow == 'D':  # Left arrow
                        return 'left'
                    elif arrow == 'A':  # Up arrow
                        return 'up'
                    elif arrow == 'B':  # Down arrow
                        return 'down'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def run(self, on_exit: Optional[Callable] = None) -> None:
        """Start interactive viewer loop"""
        self.running = True
        self.render_page()

        try:
            while self.running:
                try:
                    key = self._get_key()

                    if self.mode == "filter":
                        # In filter mode, handle key input differently
                        if key in ('\x1b', '\r'):  # ESC or Enter - exit filter mode
                            self.mode = "full"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.render_page()
                        elif key == '\x08' or key == '\x7f':  # Backspace (^H or DEL)
                            self.filter_query = self.filter_query[:-1]
                            self._update_filter()
                        elif len(key) == 1 and ord(key) >= 32:  # Printable characters
                            self.filter_query += key
                            self._update_filter()
                    else:
                        # Full mode navigation
                        if key in ('q', 'Q', '\x1b'):  # q, Q, or ESC
                            self.running = False
                        elif key == 'right':
                            if self.controller.next_page():
                                self.render_page()
                        elif key == 'left':
                            if self.controller.prev_page():
                                self.render_page()
                        elif key == 'down':
                            page_changed = self.controller.select_down()
                            self.render_page()
                        elif key == 'up':
                            page_changed = self.controller.select_up()
                            self.render_page()
                        elif key == '?' and self.controller.get_selected_paper():
                            self._show_help()
                            self.render_page()
                        elif key == 'd' and self.controller.get_selected_paper():
                            self._show_details()
                            self.render_page()
                        elif key == 'b' and self.controller.get_selected_paper():
                            bibtex = self.controller.get_selected_as_bibtex()
                            if bibtex and self._copy_to_clipboard(bibtex):
                                self.message = "[green]✓ BibTeX copied to clipboard[/green]"
                            else:
                                self.message = "[red]✗ Failed to copy to clipboard[/red]"
                            self.render_page()
                        elif key == 'i' and self.controller.get_selected_paper():
                            doi = self.controller.get_selected_doi()
                            if doi and self._copy_to_clipboard(doi):
                                self.message = f"[green]✓ DOI copied to clipboard: {doi}[/green]"
                            else:
                                self.message = "[red]✗ No DOI or failed to copy[/red]"
                            self.render_page()
                        elif key == 'c' and self.controller.get_selected_paper():
                            json_str = self.controller.get_selected_as_json()
                            if json_str and self._copy_to_clipboard(json_str):
                                self.message = "[green]✓ JSON copied to clipboard[/green]"
                            else:
                                self.message = "[red]✗ Failed to copy to clipboard[/red]"
                            self.render_page()
                        elif key == ':':
                            self.mode = "filter"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.render_page()
                except EOFError:
                    self.running = False
        finally:
            if on_exit:
                on_exit()

    def stop(self) -> None:
        """Stop the viewer"""
        self.running = False

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using pbcopy (macOS)"""
        try:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))
            return process.returncode == 0
        except (FileNotFoundError, Exception):
            return False

    def _show_help(self) -> None:
        """Display help for viewer commands"""
        help_text = """
[bold cyan]Viewer Commands[/bold cyan]

[bold]Navigation:[/bold]
  [cyan]↑/↓[/cyan]       Move selection up/down (with page scrolling)
  [cyan]←/→[/cyan]       Previous/next page

[bold]Selection Actions:[/bold]
  [cyan]d[/cyan]        Show details of selected paper
  [cyan]b[/cyan]        Copy BibTeX entry to clipboard
  [cyan]i[/cyan]        Copy DOI to clipboard
  [cyan]c[/cyan]        Copy full JSON to clipboard

[bold]Search & Quit:[/bold]
  [cyan]:[/cyan]        Enter filter mode (type to filter, [cyan]\\[/cyan] to exit)
  [cyan]?[/cyan]        Show this help
  [cyan]q/ESC[/cyan]    Quit viewer
"""
        self.console.clear()
        self.console.print(help_text)
        self.console.print("\n[dim]Press any key to return...[/dim]")
        self._get_key()

    def _show_details(self) -> None:
        """Display details of selected paper"""
        paper = self.controller.get_selected_paper()
        if not paper:
            return

        self.console.clear()
        details = f"""
[bold cyan]Paper Details[/bold cyan]

[bold]Title:[/bold] {paper.title or 'N/A'}
[bold]Authors:[/bold] {', '.join(a.full_name for a in paper.authors) if paper.authors else 'N/A'}
[bold]Year:[/bold] {paper.year or 'N/A'}
[bold]Journal:[/bold] {paper.journal or 'N/A'}
[bold]Volume/Issue:[/bold] {paper.volume or 'N/A'}/{paper.number or 'N/A'}
[bold]Pages:[/bold] {paper.pages or 'N/A'}
[bold]DOI:[/bold] {paper.doi or 'N/A'}
[bold]URL:[/bold] {paper.url or 'N/A'}

[bold]Abstract:[/bold]
{paper.abstract or 'N/A'}

[bold]Keywords:[/bold]
{', '.join(paper.keywords) if paper.keywords else 'N/A'}

[bold cyan]APA Citation:[/bold cyan]
{paper.apa}
"""
        self.console.print(details)
        self.console.print("\n[dim]Press any key to return...[/dim]")
        self._get_key()

    def _update_filter(self) -> None:
        """Update filter results as user types"""
        if self.filter_query.strip():
            self.filtered_indices = self.controller.search_papers(self.filter_query)
        else:
            self.filtered_indices = None
        self.render_page()
