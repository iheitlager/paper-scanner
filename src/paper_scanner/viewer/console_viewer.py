"""ConsoleViewer - MVC View for rendering papers in the console"""

import sys
import termios
import tty
import subprocess
from datetime import datetime, timezone
from typing import List, Callable, Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel

from paper_scanner.core.models import Paper
from paper_scanner.core.enum import ScreeningDecision
from paper_scanner.core.database import PapersDatabase
from paper_scanner.viewer.console_controller import PaperListController
from paper_scanner.viewer.json_viewer import JSONViewer


class ConsoleViewer:
    """View layer for displaying papers in paginated console format"""

    def __init__(self, papers: List[Paper], page_size: int = 10, general_config: Optional[Dict[str, Any]] = None, db: Optional[PapersDatabase] = None):
        """Initialize viewer with papers"""
        self.console = Console()
        self.controller = PaperListController(papers, page_size)
        self.page_size = page_size  # Store page_size for use in render_page
        self.general_config = general_config or {}
        self.db = db
        self.running = False
        self.message = ""  # For displaying copy/search feedback
        self.mode = "full"  # "full", "filter", "search", or "json_detail"
        self.filter_query = ""  # Current filter input
        self.filtered_indices = None  # Cached filtered results
        self.filter_selected_index = None  # Selection within filtered results
        self.detail_source_mode = None  # Track which mode to return to from detail

    def render_page(self) -> None:
        """Render current page of papers"""
        self.console.clear()

        page_info = self.controller.get_page_info()

        # In filter or search mode, show paginated filtered papers
        if (self.mode in ("filter", "search")) and self.filtered_indices:
            filtered_papers = [self.controller.papers[i] for i in self.filtered_indices]
            # Paginate filtered results
            current_page = getattr(self, "_filter_current_page", 0)
            start_idx = current_page * self.page_size
            end_idx = start_idx + self.page_size
            papers_to_show = filtered_papers[start_idx:end_idx]
            start_idx_num = start_idx + 1
        else:
            papers_to_show = self.controller.get_current_page_papers()
            start_idx_num = page_info["start_index"]

        # Papers
        for i, paper in enumerate(papers_to_show):
            idx = start_idx_num + i

            # Check if this paper is selected
            if self.mode in ("filter", "search"):
                is_selected = self.filter_selected_index == i
            else:
                is_selected = self.controller.selected_index == i


            apa_idx_color = "red" if (not paper.keywords or not paper.abstract) else "cyan"
            citations_count = len(paper.citations) if paper.citations else 0
            cited_by_count = len(paper.cited_by_papers) if paper.cited_by_papers else 0
            apa = paper.apa_formatted if not paper.is_excluded else f"[dim][strike]{paper.apa_formatted}[/strike][/dim]"
            if is_selected:
                # Highlight selected paper with background color
                self.console.print(
                    f"[{apa_idx_color} bold on blue]{idx}[/{apa_idx_color} bold on blue].[bold on blue] {apa} [dim]{citations_count}/{cited_by_count}[/dim][/bold on blue]"
                )
            else:
                self.console.print(f"[{apa_idx_color}]{idx}[/{apa_idx_color}]. {apa} [dim]{citations_count}/{cited_by_count}[/dim]")
            self.console.print()

        # Footer - 4 lines
        line1 = "[dim]Navigation: [cyan]↑/↓[/cyan] select  [cyan]→/←[/cyan] page[/dim]"
        self.console.print(line1)

        if self.controller.get_selected_paper():
            line2 = "[dim]Selected: [cyan]d[/cyan] details  [cyan]j[/cyan] json details [cyan]b[/cyan] bibtex  [cyan]i[/cyan] doi  [cyan]a[/cyan] apa  [cyan]c[/cyan] json  [cyan]/[/cyan] search  [cyan]?[/cyan] help  [cyan]q[/cyan] quit[/dim]"
            self.console.print(line2)
        else:
            line2 = "[dim]Selected: (none)  [cyan]q[/cyan] quit[/dim]"
            self.console.print(line2)

        # Line 3: Page info or mode status
        if self.mode == "search":
            match_count = len(self.filtered_indices) if self.filtered_indices else 0
            line3 = (
                f"[yellow][Search mode] Matching {match_count} papers — Press Enter to apply, Q/ESC to cancel[/yellow]"
            )
        elif self.mode == "filter":
            match_count = len(self.filtered_indices) if self.filtered_indices else 0
            filter_page = getattr(self, "_filter_current_page", 0)
            total_filter_pages = (match_count + self.page_size - 1) // self.page_size if match_count > 0 else 1
            current_filter_page = filter_page + 1
            line3 = f"[yellow][Filter mode] Page {current_filter_page}/{total_filter_pages} — {match_count} total filtered papers — Press / to search again, Q/ESC to exit[/yellow]"
        else:
            page_info = self.controller.get_page_info()
            line3 = f"[dim]Page {page_info['current_page']}/{page_info['total_pages']} — {page_info['end_index']}/{page_info['papers_total']} papers[/dim]"
        self.console.print(line3)

        # Line 4: Messages or search input
        if self.mode == "search":
            self.console.print(f"[cyan]/[/cyan] {self.filter_query}[dim]_[/dim]")
        else:
            self.console.print(self.message)

    def _render_detail_page(self) -> None:
        """Render detail view with navigation hints"""
        self.console.clear()

        # Get the paper to display
        if self.detail_source_mode == "filter" and self.filter_selected_index is not None:
            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
            position = f"{self.filter_selected_index + 1}/{len(self.filtered_indices)}"
        elif self.detail_source_mode == "full":
            paper = self.controller.get_selected_paper()
            page_info = self.controller.get_page_info()
            # Calculate absolute position across all papers in database
            absolute_position = page_info["start_index"] + self.controller.selected_index
            position = f"{absolute_position}/{page_info['papers_total']}"
        else:
            return

        if not paper:
            return

        if paper.is_duplicate:
            duplicate_note = f"[red]Duplicate of[/red] '{paper.duplicate_of.id}'\n"
            duplicate_note += f"[red]Method:[/red] {paper.screening.deduplication.method} " if paper.screening and paper.screening.deduplication and paper.screening.deduplication.method else ""
            duplicate_note += f"[red]Similarity Score:[/red] {paper.screening.deduplication.similarity_score:.4f} " if paper.screening and paper.screening.deduplication else ""
            duplicate_note += f"[red]Confidence[/red] {paper.screening.deduplication.confidence:.2f} " if paper.screening and paper.screening.deduplication else ""
            duplicate_note += f"\n\n[red]Paper apa:[/red]\n\n{paper.apa_formatted}\n"
            self.console.print(duplicate_note)
            footer = "[dim][cyan]q/ESC[/cyan] exit detail mode[/dim]"
            self.console.print(footer)
            return

        screening_reasons = [
            paper.screening.metadata_screening.exclusion_reason if paper.screening and paper.screening.metadata_screening else "",
            paper.screening.keyword_screening.exclusion_reason if paper.screening and paper.screening.keyword_screening else "",
            paper.screening.keyword_screening.inclusion_reason if paper.screening and paper.screening.keyword_screening else "",
            paper.screening.semantic_screening.reason if paper.screening and paper.screening.semantic_screening else "",
        ]
        excl_color = "red" if paper.is_excluded else "cyan"
        # Build screening decision string with proper rich markup (variable-based closing tags need to be pre-formatted)
        screening_decision = paper.screening.final_decision.value if paper.screening and paper.screening.final_decision else "N/A"
        screening_stage = paper.screening.current_stage if paper.screening else "N/A"
        study_type = paper.screening.keyword_screening.study_type.value if paper.screening and paper.screening.keyword_screening else "N/A"
        iteration = f" (Iteration {paper.discovery.iteration})" if paper.discovery and paper.discovery.iteration else ""

        details = f"""
[bold cyan]Paper Details (Detail Mode)[/bold cyan]
[dim]{position}[/dim]

[bold]Cite key:[/bold] {paper.cite_key or "N/A"}
[bold]Title:[/bold] {paper.title or "N/A"} [dim]({(paper.language or "N/A")})[/dim]
[bold]Authors:[/bold] {", ".join(a.full_name for a in paper.authors) if paper.authors else "N/A"}
[bold]Journal:[/bold] [italic]{paper.journal or "N/A"}[/italic]
[bold]Year:[/bold] {paper.year or "N/A"} [bold]Volume/Issue:[/bold] {paper.volume or "N/A"}/{paper.issue or "N/A"} [bold]Pages:[/bold] {paper.pages or "N/A"}
[bold]DOI:[/bold] {paper.doi or "N/A"}
[bold]URL:[/bold] {paper.url or "N/A"}
[bold]Source:[/bold] [cyan]{paper.discovery.source_database or "N/A"}[/cyan] {iteration}
[bold]Screening Decision:[/bold] [{excl_color}]{screening_decision}[/{excl_color}] - {screening_stage}
[bold]Study Type:[/bold] {study_type}
{"[bold]Screening:[/bold]\n * " + "\n * ".join([r for r in screening_reasons if r])}

[bold]Abstract:[/bold]
{paper.abstract or "N/A"}

[bold]Keywords:[/bold]
{", ".join(paper.keywords) if paper.keywords else "N/A"}

[bold]Citations:[/bold]
Database: {len(paper.citations) if paper.citations else 0} / {len(paper.cited_by) if paper.cited_by else 0} - Resolved: {len(paper.cited_papers) if paper.cited_papers else 0} / {len(paper.cited_by_papers) if paper.cited_by_papers else 0}

[bold cyan]APA Citation:[/bold cyan]
{paper.apa_formatted}
"""
        self.console.print(details)

        # Footer with navigation options
        footer = "[dim][cyan]↑/↓[/cyan] navigate  [cyan]b[/cyan] bibtex  [cyan]i[/cyan] doi  [cyan]a[/cyan] apa  [cyan]c[/cyan] json  [cyan]q/ESC[/cyan] exit detail mode[/dim]"
        self.console.print(footer)

        # Message line (for copy feedback, etc.)
        self.console.print(self.message)

    def _get_current_paper(self) -> Optional[Paper]:
        """Get the currently displayed paper based on mode"""
        if self.mode == "detail":
            # In detail mode, check which mode we came from
            if self.detail_source_mode == "filter" and self.filter_selected_index is not None and self.filtered_indices:
                return self.controller.papers[self.filtered_indices[self.filter_selected_index]]
            elif self.detail_source_mode == "full":
                return self.controller.get_selected_paper()
        elif self.mode == "filter" and self.filter_selected_index is not None and self.filtered_indices:
            return self.controller.papers[self.filtered_indices[self.filter_selected_index]]
        elif self.mode == "full":
            return self.controller.get_selected_paper()
        return None

    def _copy_to_clipboard_and_message(self, text: str, success_msg: str, failure_msg: str) -> None:
        """Copy text to clipboard and update message"""
        if text and self._copy_to_clipboard(text):
            self.message = f"[green]✓ {success_msg}[/green]"
        else:
            self.message = f"[red]✗ {failure_msg}[/red]"
        # Will be called by the mode-specific render method

    def _render_and_show_message(self) -> None:
        """Render current view and show message (used after copy operations)"""
        if self.mode == "detail":
            self._render_detail_page()
        else:
            self.render_page()

    def _get_key(self) -> str:
        """Get a single key press from terminal"""
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
                # If ESC not followed by arrow sequence, return ESC
                return "\x1b"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def run(self, on_exit: Optional[Callable] = None) -> None:
        """Start interactive viewer loop"""
        self.running = True
        self.console.show_cursor(False)  # Hide cursor
        self.render_page()

        try:
            while self.running:
                try:
                    key = self._get_key()

                    if self.mode == "detail":
                        # In detail mode, navigate through papers with up/down
                        if key in ("q", "Q", "\x1b"):  # q, Q, or ESC - exit detail mode
                            self.mode = self.detail_source_mode
                            self.detail_source_mode = None
                            self.message = ""  # Clear message on mode change
                            self.render_page()
                        elif key == "down":
                            # Move to next paper
                            self.message = ""  # Clear message on navigation
                            if self.detail_source_mode == "filter" and self.filter_selected_index is not None:
                                if self.filter_selected_index < len(self.filtered_indices) - 1:
                                    self.filter_selected_index += 1
                            elif self.detail_source_mode == "full":
                                page_info = self.controller.get_page_info()
                                current_page_papers = self.controller.get_current_page_papers()

                                # Check if at last paper on current page
                                is_last_on_page = self.controller.selected_index >= len(current_page_papers) - 1
                                has_next_page = page_info["current_page"] < page_info["total_pages"]

                                if is_last_on_page and has_next_page:
                                    # At end of page and there are more pages - go to next page
                                    self.controller.next_page()
                                    self.controller.selected_index = 0
                                elif not is_last_on_page:
                                    # Not at end of page - move down within page
                                    self.controller.select_down()
                                # else: at last paper of last page, do nothing
                            self._render_detail_page()
                        elif key == "up":
                            # Move to previous paper
                            self.message = ""  # Clear message on navigation
                            if self.detail_source_mode == "filter" and self.filter_selected_index is not None:
                                if self.filter_selected_index > 0:
                                    self.filter_selected_index -= 1
                            elif self.detail_source_mode == "full":
                                page_info = self.controller.get_page_info()

                                # Check if at first paper on current page
                                is_first_on_page = self.controller.selected_index <= 0
                                has_prev_page = page_info["current_page"] > 1

                                if is_first_on_page and has_prev_page:
                                    # At start of page and there are previous pages - go to previous page
                                    self.controller.prev_page()
                                    prev_page_papers = self.controller.get_current_page_papers()
                                    self.controller.selected_index = len(prev_page_papers) - 1
                                elif not is_first_on_page:
                                    # Not at start of page - move up within page
                                    self.controller.select_up()
                                # else: at first paper of first page, do nothing
                            self._render_detail_page()
                        elif key == "b":
                            # Copy bibtex
                            paper = self._get_current_paper()
                            if paper:
                                bibtex = self.controller._paper_to_bibtex(paper)
                                self._copy_to_clipboard_and_message(
                                    bibtex, f"BibTeX copied to clipboard: {paper.doi}", "Failed to copy to clipboard"
                                )
                                self._render_detail_page()
                        elif key == "i":
                            # Copy DOI
                            paper = self._get_current_paper()
                            if paper:
                                self._copy_to_clipboard_and_message(
                                    paper.doi, f"DOI copied to clipboard: {paper.doi}", "No DOI or failed to copy"
                                )
                                self._render_detail_page()
                        elif key == "c":
                            # Copy JSON
                            paper = self._get_current_paper()
                            if paper:
                                json_str = (
                                    self.controller._paper_to_json(paper)
                                    if self.detail_source_mode == "filter"
                                    else self.controller.get_selected_as_json()
                                )
                                self._copy_to_clipboard_and_message(
                                    json_str, f"JSON copied to clipboard: {paper.doi}", "Failed to copy to clipboard"
                                )
                                self._render_detail_page()
                        elif key == "a":
                            # Copy APA citation
                            paper = self._get_current_paper()
                            if paper:
                                self._copy_to_clipboard_and_message(
                                    paper.apa,
                                    f"APA citation copied to clipboard: {paper.doi}",
                                    "Failed to copy to clipboard",
                                )
                                self._render_detail_page()

                    elif self.mode == "search":
                        # In search mode, handle text input
                        if key in ("\x1b",):  # ESC - cancel search, return to full
                            self.mode = "full"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.render_page()
                        elif key in ("q", "Q"):  # Q - quit to full mode
                            self.mode = "full"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.render_page()
                        elif key == "\r":  # Enter - apply search, keep filter mode
                            self.mode = "filter"
                            self._filter_current_page = 0  # Reset to first page
                            self.filter_selected_index = None  # Reset selection in filtered results
                            self.render_page()
                        elif key == "\x08" or key == "\x7f":  # Backspace (^H or DEL)
                            self.filter_query = self.filter_query[:-1]
                            self._update_filter()
                        elif len(key) == 1 and ord(key) >= 32:  # Printable characters
                            self.filter_query += key
                            self._update_filter()

                    elif self.mode == "filter":
                        # In filter mode, all normal commands work but on filtered papers
                        if key in ("q", "Q", "\x1b"):  # q, Q, or ESC - exit to full mode
                            self.mode = "full"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.filter_selected_index = None
                            self.message = ""  # Clear message on mode change
                            self.render_page()
                        elif key == "/":
                            self.message = ""  # Clear message when entering search
                            self.mode = "search"
                            self.filter_query = ""
                            self.render_page()
                        elif key == "right":
                            # Next page in filtered results
                            self.message = ""  # Clear message on navigation
                            match_count = len(self.filtered_indices) if self.filtered_indices else 0
                            total_filter_pages = (match_count + self.page_size - 1) // self.page_size if match_count > 0 else 1
                            filter_page = getattr(self, "_filter_current_page", 0)
                            if filter_page < total_filter_pages - 1:
                                self._filter_current_page = filter_page + 1
                                self.filter_selected_index = None  # Reset selection on page change
                            self.render_page()
                        elif key == "left":
                            # Previous page in filtered results
                            self.message = ""  # Clear message on navigation
                            filter_page = getattr(self, "_filter_current_page", 0)
                            if filter_page > 0:
                                self._filter_current_page = filter_page - 1
                                self.filter_selected_index = None  # Reset selection on page change
                            self.render_page()
                        elif key == "down":
                            # Selection in filtered results (within current page)
                            self.message = ""  # Clear message on navigation
                            filter_page = getattr(self, "_filter_current_page", 0)
                            start_idx = filter_page * self.page_size
                            match_count = len(self.filtered_indices) if self.filtered_indices else 0
                            end_idx = min(start_idx + self.page_size, match_count)
                            papers_on_page = end_idx - start_idx
                            
                            if self.filter_selected_index is None:
                                self.filter_selected_index = 0
                            elif self.filter_selected_index < papers_on_page - 1:
                                self.filter_selected_index += 1
                            self.render_page()
                        elif key == "up":
                            # Selection in filtered results (within current page)
                            self.message = ""  # Clear message on navigation
                            if self.filter_selected_index is None:
                                filter_page = getattr(self, "_filter_current_page", 0)
                                start_idx = filter_page * self.page_size
                                match_count = len(self.filtered_indices) if self.filtered_indices else 0
                                end_idx = min(start_idx + self.page_size, match_count)
                                papers_on_page = end_idx - start_idx
                                self.filter_selected_index = papers_on_page - 1
                            elif self.filter_selected_index > 0:
                                self.filter_selected_index -= 1
                            self.render_page()
                        elif key == "?" and self.filter_selected_index is not None:
                            self._show_details_filtered()
                            self.message = ""  # Clear message after showing details
                            self.render_page()
                        elif key in ("d", "\r") and self.filter_selected_index is not None:
                            self.detail_source_mode = "filter"
                            self.mode = "detail"
                            self.message = ""  # Clear message when entering detail mode
                            self._render_detail_page()
                        elif key == "j" and self.filter_selected_index is not None:
                            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
                            self._show_json_viewer(paper)
                            self.render_page()
                        elif key == "b" and self.filter_selected_index is not None:
                            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
                            bibtex = self.controller._paper_to_bibtex(paper)
                            self._copy_to_clipboard_and_message(
                                bibtex, f"BibTeX copied to clipboard: {paper.doi}", "Failed to copy to clipboard"
                            )
                            self.render_page()
                        elif key == "i" and self.filter_selected_index is not None:
                            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
                            doi = paper.doi
                            if doi and self._copy_to_clipboard(doi):
                                self.message = f"[green]✓ DOI copied to clipboard: {doi}[/green]"
                            else:
                                self.message = "[red]✗ No DOI or failed to copy[/red]"
                            self.render_page()
                        elif key == "c" and self.filter_selected_index is not None:
                            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
                            json_str = self.controller._paper_to_json(paper)
                            self._copy_to_clipboard_and_message(
                                json_str, f"JSON copied to clipboard: {paper.doi}", "Failed to copy to clipboard"
                            )
                            self.render_page()
                        elif key == "a" and self.filter_selected_index is not None:
                            paper = self.controller.papers[self.filtered_indices[self.filter_selected_index]]
                            self._copy_to_clipboard_and_message(
                                paper.apa,
                                f"APA citation copied to clipboard: {paper.doi}",
                                "Failed to copy to clipboard",
                            )
                            self.render_page()

                    else:  # Full mode
                        if key in ("q", "Q", "\x1b"):  # q, Q, or ESC - quit
                            self.running = False
                        elif key in ("/",":"):
                            # Enter search mode
                            self.message = ""  # Clear message when entering search
                            self.mode = "search"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self.render_page()
                        elif key == "right":
                            self.message = ""  # Clear message on navigation
                            if self.controller.next_page():
                                self.render_page()
                        elif key == "left":
                            self.message = ""  # Clear message on navigation
                            if self.controller.prev_page():
                                self.render_page()
                        elif key == "down":
                            self.message = ""  # Clear message on navigation
                            page_changed = self.controller.select_down()
                            self.render_page()
                        elif key == "up":
                            self.message = ""  # Clear message on navigation
                            page_changed = self.controller.select_up()
                            self.render_page()
                        elif key == "?" and self.controller.get_selected_paper():
                            self._show_help()
                            self.message = ""  # Clear message after showing help
                            self.render_page()
                        elif key in ("d", "\r") and self.controller.get_selected_paper():
                            # Enter interactive detail mode
                            self.detail_source_mode = "full"
                            self.mode = "detail"
                            self.message = ""  # Clear message when entering detail mode
                            self._render_detail_page()
                        elif key == "j" and self.controller.get_selected_paper():
                            # Enter JSON viewer mode
                            paper = self.controller.get_selected_paper()
                            self._show_json_viewer(paper)
                            self.render_page()
                        elif key == "b" and self.controller.get_selected_paper():
                            bibtex = self.controller.get_selected_as_bibtex()
                            self._copy_to_clipboard_and_message(
                                bibtex,
                                f"BibTeX copied to clipboard: {self.controller.get_selected_paper().doi}",
                                "Failed to copy to clipboard",
                            )
                            self.render_page()
                        elif key == "i" and self.controller.get_selected_paper():
                            doi = self.controller.get_selected_doi()
                            if doi and self._copy_to_clipboard(doi):
                                self.message = f"[green]✓ DOI copied to clipboard: {doi}[/green]"
                            else:
                                self.message = "[red]✗ No DOI or failed to copy[/red]"
                            self.render_page()

                        elif key == "c" and self.controller.get_selected_paper():
                            json_str = self.controller.get_selected_as_json()
                            self._copy_to_clipboard_and_message(
                                json_str,
                                f"JSON copied to clipboard: {self.controller.get_selected_paper().doi}",
                                "Failed to copy to clipboard",
                            )
                            self.render_page()
                        elif key == "a" and self.controller.get_selected_paper():
                            paper = self.controller.get_selected_paper()
                            self._copy_to_clipboard_and_message(
                                paper.apa,
                                f"APA citation copied to clipboard: {paper.doi}",
                                "Failed to copy to clipboard",
                            )
                            self.render_page()
                        elif key in ("x", "X") and self.controller.get_selected_paper():
                            # Mark paper as manually excluded
                            paper = self.controller.get_selected_paper()
                            email = self.general_config.get("project", {}).get("email", "unknown@example.com")
                            
                            paper.screening.final_decision = ScreeningDecision.EXCLUDED_MANUAL
                            paper.screening.final_decision_at = datetime.now(timezone.utc)
                            paper.screening.final_decision_by = f"manual:{email}"
                            
                            # Update database if available
                            if self.db:
                                self.db.update(paper)
                            
                            self.message = f"[yellow]✓ Marked as manually excluded: {paper.doi}[/yellow]"
                            self.render_page()
                        elif key == ":":
                            self.mode = "filter"
                            self.filter_query = ""
                            self.filtered_indices = None
                            self._filter_current_page = 0  # Reset to first page
                            self.render_page()
                except EOFError:
                    self.running = False
        finally:
            self.console.show_cursor(True)  # Restore cursor
            if on_exit:
                on_exit()

    def stop(self) -> None:
        """Stop the viewer"""
        self.running = False

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using pbcopy (macOS)"""
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
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
  [cyan]a[/cyan]        Copy APA citation to clipboard
  [cyan]c[/cyan]        Copy full JSON to clipboard
  [cyan]x[/cyan]        Mark as manually excluded

[bold]Search & Quit:[/bold]
  [cyan]/[/cyan]        Enter filter mode (type to filter, [cyan]\\[/cyan] to exit)
  [cyan]?[/cyan]        Show this help
  [cyan]q/ESC[/cyan]    Quit viewer
"""
        self.console.clear()
        self.console.print(help_text)
        self.console.print("\n[dim]Press any key to return...[/dim]")
        self._get_key()

    def _show_details(self) -> None:
        """Display details of selected paper (full mode)"""
        self.detail_source_mode = "full"
        self._render_detail_page()

    def _show_json_viewer(self, paper: Paper) -> None:
        """Display interactive JSON viewer for a paper."""
        # Convert paper to JSON (model_dump)
        paper_dict = paper.model_dump(mode='json')

        # Create and run JSON viewer
        json_viewer = JSONViewer(paper_dict, title=f"Paper JSON: {paper.doi or 'Unknown'}")
        json_viewer.run()

    def _show_details_filtered(self) -> None:
        """Display details of selected paper in filter mode"""
        self.detail_source_mode = "filter"
        self._render_detail_page()

    def _update_filter(self) -> None:
        """Update filter results as user types"""
        if self.filter_query.strip():
            self.filtered_indices = self.controller.search_papers(self.filter_query)
        else:
            self.filtered_indices = None
        self.render_page()
