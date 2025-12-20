"""
Fetcher orchestrator - manages handler implementations and caching.

Coordinates metadata and citations fetching from multiple sources with fallback logic
and unified caching across all APIs.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from rich.console import Console

from paper_scanner.core.models import Paper, Citation
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import CrossrefHandler
from paper_scanner.tools.fetchers.fetcher_handlers.openalex_handler import OpenAlexHandler

console = Console(file=sys.stderr)

# Mapping of method names to handler classes
handler_classes = {
    "crossref": CrossrefHandler,
    "openalex": OpenAlexHandler,
    # "core": COREHandler,
    # Add others as implemented
}

class Fetcher:
    """
    Orchestrates metadata fetching from multiple sources.

    Manages handler registration, caching, and fallback logic.
    """

    def __init__(self, cache_dir: Path, methods: list, verbose: bool = False, debug: bool = False):
        """
        Initialize fetcher with specified methods.

        Args:
            cache_dir: Base cache directory (will use cache_dir/crossref, etc.)
            methods: List of fetcher names to enable (e.g., ["crossref"])
        """
        self.cache_dir = Path(cache_dir).expanduser()
        self.handlers: Dict[str, BaseFetcherHandler] = {}
        self.verbose = verbose
        self.debug = debug

        # Register handlers for enabled methods
        self._register_handlers(methods)

        if not self.handlers:
            raise ValueError(f"No valid handlers registered from methods: {methods}")

    def _register_handlers(self, methods: list) -> None:
        """Register handler instances for specified methods."""
        if self.debug:
            console.print(f"[blue]Registering fetcher handlers:[/blue]")

        for method in methods:
            if method not in handler_classes:
                console.print(f" [yellow]Unknown fetcher method: {method}[/yellow]")
                continue

            handler_class = handler_classes[method]
            self.handlers[method] = handler_class(cache_dir=self.cache_dir, debug=self.debug, verbose=self.verbose)
            if self.debug:
                console.print(f"[dim]{method} - {self.cache_dir}/{method}[/dim]")

    def fetch_paper(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch metadata for a DOI from registered handlers.

        Tries handlers in order until one succeeds.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        paper = None
        cache_hit = False
        for handler_name, handler in self.handlers.items():
            try:
                if self.debug:
                    console.print(f"  [blue]Trying handler {handler_name} for DOI {doi}[/blue]")
                new_paper, new_cache_hit = handler.fetch_paper(doi)
                if not paper:
                    paper = new_paper
                    cache_hit = new_cache_hit
                elif new_paper:
                    handler.merge_papers(paper, new_paper)
                    cache_hit = cache_hit and new_cache_hit
                if paper and paper.calculated_quality_score >= 0.9:
                    return paper, cache_hit
            except Exception as e:
                console.print(
                    f"[yellow]Handler {handler_name} failed for {doi}: {e}[/yellow]"
                )
                continue
        if paper:
            return paper, cache_hit
        return None, False

    def fetch_citations(self, doi: str) -> Tuple[List[Citation], bool]:
        """
        Fetch and parse backward citations for a given DOI.

        Tries handlers in order until one succeeds.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (citations list, cache_hit: bool)
        """
        for handler_name, handler in self.handlers.items():
            try:
                citations, cache_hit = handler.fetch_citations(doi)
                if citations:
                    if self.debug:
                        console.print(
                            f"[green]Fetched {len(citations)} citations for {doi} "
                            f"from {handler_name}[/green]"
                        )
                    return citations, cache_hit
            except Exception as e:
                console.print(
                    f"[yellow]Handler {handler_name} failed for {doi}: {e}[/yellow]"
                )
                continue

        return [], False
