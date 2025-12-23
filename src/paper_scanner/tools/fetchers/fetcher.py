"""
Fetcher orchestrator - manages handler implementations and caching.

Coordinates metadata and citations fetching from multiple sources with fallback logic
and unified caching across all APIs.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.models import Citation, Paper, PDFInfo
from paper_scanner.tools.cache import PDFCache
from paper_scanner.tools.fetchers.fetcher_handlers.base import BaseFetcherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.crossref_handler import CrossrefHandler
from paper_scanner.tools.fetchers.fetcher_handlers.openalex_handler import OpenAlexHandler
from paper_scanner.tools.fetchers.fetcher_handlers.publisher_handler import PublisherHandler
from paper_scanner.tools.fetchers.fetcher_handlers.semantic_scholar_handler import SemanticScholarHandler

console = Console(file=sys.stderr)

# Mapping of method names to handler classes
handler_classes = {
    "crossref": CrossrefHandler,
    "openalex": OpenAlexHandler,
    "semanticscholar": SemanticScholarHandler,
    "publisher": PublisherHandler,
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
        # NB: PDF caching is handled here in the Fetcher, not in individual handlers
        self.pdf_cache = PDFCache(cache_dir=self.cache_dir / "pdfs")

        # Register handlers for enabled methods
        self._register_handlers(methods)

        if not self.handlers:
            raise ValueError(f"No valid handlers registered from methods: {methods}")

    def _register_handlers(self, methods: list) -> None:
        """Register handler instances for specified methods."""
        if self.debug:
            console.print(" Registering fetcher handlers:")

        for method in methods:
            if method not in handler_classes:
                console.print(f" [yellow]Unknown fetcher method: {method}[/yellow]")
                continue

            handler_class = handler_classes[method]
            self.handlers[method] = handler_class(cache_dir=self.cache_dir, debug=self.debug, verbose=self.verbose)
            if self.debug:
                console.print(f" [dim]{method} - {self.cache_dir}/{method}[/dim]")

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
                    console.print(f"  Trying handler {handler_name} for DOI {doi}")
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

        Tries handlers in order until first succeeds.

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
                            f" [green]✓[/green] Fetched {len(citations)} backward citations for {doi} from {handler_name}"
                        )
                    return citations, cache_hit
            except Exception as e:
                console.print(
                    f" [yellow]⚠️  Handler {handler_name} failed for {doi}: {e}[/yellow]"
                )
                continue

        return [], False


    def fetch_cited_by(self, doi: str, limit: Optional[int] = 100) -> Tuple[List[Citation], bool]:
        """
        Fetch and parse forward citations for a given DOI.

        Tries handlers in order until first succeeds.

        Args:
            doi: Digital Object Identifier

        Returns:
            Tuple of (citations list, cache_hit: bool)
        """
        for handler_name, handler in self.handlers.items():
            try:
                citations, cache_hit = handler.fetch_cited_by(doi, limit=limit)
                if citations:
                    if self.debug:
                        console.print(
                            f" [green]✓[/green] Fetched {len(citations)} forward citations for {doi} from {handler_name}"
                        )
                    return citations, cache_hit
            except Exception as e:
                console.print(
                    f" [yellow]⚠️  Handler {handler_name} failed for {doi}: {e}[/yellow]"
                )
                continue

        return [], False

    def fetch_pdf(self, doi: str, timeout: int = 30) -> Optional[PDFInfo]:
        """
        Fetch PDF for a DOI, using cache if available.

        Checks the PDF cache first, then attempts to fetch from handlers.
        Once fetched, the PDF is cached for future use.
        NB: Note that caching PDFs is handled here in the Fetcher, not in individual handlers.

        Args:
            doi: Digital Object Identifier

        Returns:
            PDFInfo with file path and metadata if found or successfully downloaded, None otherwise
        """
        # Check cache first
        cached_path = self.pdf_cache.get(doi)
        if cached_path:
            if self.debug:
                console.print(f" [green]✓[/green] PDF cache hit for {doi}")
            # Return PDFInfo from cached path (we'll reconstruct metadata)
            if cached_path.exists():
                return PDFInfo(
                    file_path=str(cached_path),
                    file_size_bytes=cached_path.stat().st_size,
                    download_source="cache",
                )
            return None

        # Try to fetch from handlers
        for handler_name, handler in self.handlers.items():
            try:
                if self.debug:
                    console.print(f"  Trying to fetch PDF from {handler_name} for DOI {doi}")

                # Handler now returns PDFInfo with handler name as source
                pdf_info = handler.fetch_pdf(doi, timeout=timeout)
                if pdf_info and pdf_info.file_path:
                    tmp_pdf_path = Path(pdf_info.file_path)
                    # Cache the PDF
                    cached_path = self.pdf_cache.set(doi, tmp_pdf_path)
                    if self.debug:
                        console.print(f" [green]✓[/green] PDF cached for {doi} from {handler_name}")

                    # Return PDFInfo with updated file path (now in cache) but preserve handler name
                    return PDFInfo(
                        file_path=str(cached_path),
                        file_size_bytes=cached_path.stat().st_size,
                        download_source=pdf_info.download_source,  # Preserve handler name
                        download_url=pdf_info.download_url,
                        downloaded_at=pdf_info.downloaded_at,
                    )
            except Exception as e:
                console.print(
                    f" [yellow]⚠️  Handler {handler_name} failed to fetch PDF for {doi}: {e}[/yellow]"
                )
                continue

        return None
