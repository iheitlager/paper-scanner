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

console = Console(file=sys.stderr)

# Mapping of method names to handler classes
handler_classes = {
    "crossref": CrossrefHandler,
    # "openalex": OpenAlexHandler,
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
            method_cache_dir = self.cache_dir / method
            self.handlers[method] = handler_class(cache_dir=method_cache_dir)
            if self.debug:
                console.print(f"  [dim]{method} - {method_cache_dir}[/dim]")

    def fetch_metadata(self, doi: str) -> Tuple[Optional[Paper], bool]:
        """
        Fetch metadata for a DOI from registered handlers.

        Tries handlers in order until one succeeds.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (Paper model or None, cache_hit: bool)
        """
        for handler_name, handler in self.handlers.items():
            try:
                paper, cache_hit = handler.fetch_metadata(doi)
                if paper:
                    console.print(f"[green]Fetched {doi} from {handler_name}[/green]")
                    return paper, cache_hit
            except Exception as e:
                console.print(f"[red]Handler {handler_name} failed for {doi}: {e}[/red]")
                continue

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
