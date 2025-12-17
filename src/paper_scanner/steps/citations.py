"""
Citations step - Extract backward citations from papers using external APIs.

Walks over Paper records in the database and fetches backward citations
(references) from configured sourcess (Crossref by default), then resolves
citations against the Paper database and creates new Paper records for
unresolved citations.

Three-pass architecture for improved testability:
PASS 1: Fetch citations from external sourcess and store in papers
PASS 2: Resolve citations to existing papers or create new papers, fetch metadata
PASS 3: Build citation graph (cited_papers, cited_by_papers) in memory

Process:
1. Filter papers by paper_type (default: journal_article)
2. PASS 1: For each paper with a DOI, fetch citations from configured sources
3. PASS 2: For each citation, resolve to existing paper or create new Paper
   - Update Citation.resolved_paper with full Paper object
   - Fetch paper metadata via fetcher.fetch_paper() for enrichment
4. PASS 3: Loop over all papers and build bidirectional citation graph
   - Add resolved_paper to Paper.cited_papers
   - Add Paper to resolved_paper.cited_by_papers
5. Batch update all modified papers to database
"""

import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pprint import pformat
from rich.console import Console
import logging

from paper_scanner.core.models import Paper, Citation, Discovery, DiscoveryMethod, PaperType
from paper_scanner.core.database import PapersDatabase
from paper_scanner.tools.fetchers.fetcher import Fetcher
from paper_scanner.core.doi import DOI
from .base import BaseStep

console = Console(file=sys.stderr)
logger = logging.getLogger(__name__)


class CitationsStep(BaseStep):
    """Extract and resolve backward citations for papers."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate citations step configuration.

        Args:
            config: Step configuration with:
                - paper_types or paper-type: List of PaperType values to process (default: ["journal_article"])
                - backward:
                    - sources: Fetcher name(s) - string or list (default: "crossref")
                    - continue_on_not_found: bool (default: True - create new Paper for unresolved citations)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate paper_types
        if "paper-type" in config:
            if not isinstance(config["paper-type"], list):
                errors.append("'paper-types' must be a list")
            else:
                valid_types = [pt.value for pt in PaperType]
                for pt in config["paper-type"]:
                    if pt not in valid_types:
                        errors.append(f"'{pt}' is not a valid PaperType. Valid: {valid_types}")

        # Validate backward config
        if "backward" in config:
            backward = config["backward"]
            if not isinstance(backward, dict):
                errors.append("'backward' must be a dictionary")
            else:
                if "sources" in backward:
                    sources = backward["sources"]
                    if not isinstance(sources, (str, list)):
                        errors.append("'backward.sources' must be a string or list of fetcher names")
                    elif isinstance(sources, list):
                        for src in sources:
                            if not isinstance(src, str):
                                errors.append(f"'backward.sources' items must be strings, got {type(src).__name__}")
                if "continue_on_not_found" in backward:
                    if not isinstance(backward["continue_on_not_found"], bool):
                        errors.append("'backward.continue_on_not_found' must be a boolean")
                if "limit" in backward:
                    if not isinstance(backward["limit"], int) or backward["limit"] < 1:
                        errors.append("'backward.limit' must be a positive integer")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute backward citations extraction for papers in three passes.

        Pass 1: Fetch citations from external sourcess and store in papers
        Pass 2: Resolve citations to existing papers or create new papers
        Pass 3: Build citation graph in memory (cited_papers, cited_by_papers)

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't write to database if True
            debug: Enable debug output

        Returns:
            Results dict with statistics
        """
        # Extract configuration
        backward_config = config.get("backward", {})
        if backward_config:
            paper_types = backward_config.get("paper-types", ["journal_article"])
            sourcess = backward_config.get("sources", ["crossref"])
            continue_on_not_found = backward_config.get("continue_on_not_found", True)
            limit = backward_config.get("limit", None)

            if verbose:
                console.print(f"[blue]Citations backward processing[/blue]")
                console.print(f"[blue]Paper types to process:[/blue] {paper_types}")
                console.print(f"[blue]Citation sourcess:[/blue] {sourcess}")
                console.print(f"[blue]Continue on not found:[/blue] {continue_on_not_found}")
                if limit:
                    console.print(f"[blue]Limit papers to process:[/blue] {limit}")

        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=sourcess,
            verbose=verbose,
            debug=debug
        )

        # Get papers to process (filter by paper_type)
        target_papers = self.db.find(
            lambda p: p.paper_type and p.paper_type.value in paper_types,
            primary_only=True
        )

        if debug:
            console.print(f"[blue]Fetcher initialized:[/blue]\n{pformat(fetcher.handlers, indent=2)}")
            console.print(f"[blue]Total papers in DB:[/blue] {self.db.count(primary_only=True)}")
            console.print(f"[blue]Target papers to process:[/blue] {len(target_papers)}")

        results = {
            "total_papers": self.db.count(primary_only=True),
            "target_papers": len(target_papers),
            "papers_with_citations": 0,
            "citations_fetched": 0,
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "forward_links_created": 0,
            "reverse_links_created": 0,
            "errors": [],
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # PASS 1: Fetch citations from external sourcess
        self._fetch_citations_for_papers(
            target_papers=target_papers,
            fetcher=fetcher,
            results=results,
            verbose=verbose,
            debug=debug,
            limit=limit,
        )

        # PASS 2: Resolve citations and expand database
        self._resolve_citations_and_fetch_papers(
            papers=target_papers,
            fetcher=fetcher,
            continue_on_not_found=continue_on_not_found,
            dry_run=dry_run,
            results=results,
            verbose=verbose,
            debug=debug
        )

        # PASS 3: Build citation graph in memory
        all_papers = self.db.all(primary_only=False)
        self._link_citation_graph(
            papers=all_papers,
            results=results,
            verbose=verbose,
            debug=debug
        )

        if verbose:
            console.print(f"[green]Citation graph linking completed.[/green]")
            console.print(f"\n[bold cyan]=== CITATION STATISTICS ===[/bold cyan]")
            console.print(f"[cyan]Total papers in DB:[/cyan] {results['total_papers']}")
            console.print(f"[cyan]Target papers processed:[/cyan] {results['target_papers']}")
            console.print(f"[cyan]Papers with citations:[/cyan] {results['papers_with_citations']}")
            console.print(f"[cyan]Citations fetched:[/cyan] {results['citations_fetched']}")
            console.print(f"[cyan]Citations resolved:[/cyan] {results['citations_resolved']}")
            console.print(f"[cyan]Citations created new papers:[/cyan] {results['citations_created_new_paper']}")
            console.print(f"[cyan]Citations unresolved:[/cyan] {results['citations_unresolved']}")
            console.print(f"[cyan]Forward links created:[/cyan] {results['forward_links_created']}")
            console.print(f"[cyan]Reverse links created:[/cyan] {results['reverse_links_created']}")
            console.print(f"[cyan]Cache hits:[/cyan] {results['cache_hits']}")
            console.print(f"[cyan]Cache misses:[/cyan] {results['cache_misses']}")
            if results['errors']:
                console.print(f"[red]Errors:[/red] {len(results['errors'])}")
                for error in results['errors'][:5]:  # Show first 5 errors
                    console.print(f"  [red]- {error}[/red]")

        return results

    def _fetch_citations_for_papers(
        self,
        target_papers: List[Paper],
        fetcher: "Fetcher",
        results: Dict[str, Any],
        verbose: bool = False,
        debug: bool = False,
        limit: Optional[int] = None,
    ) -> None:
        """
        PASS 1: Fetch citations from external sourcess and store in papers.

        Iterates over target papers, fetches citations from configured sourcess,
        and stores them in each paper's citations list.

        Args:
            target_papers: List of papers to fetch citations for
            fetcher: Fetcher instance to use for citation retrieval
            limit: Optional limit on number of citations to process
            results: Results dict to update with statistics
            verbose: Enable verbose output
            debug: Enable debug output
        """
        for i, paper in enumerate(target_papers, 1):
            if not paper.doi:
                continue

            try:
                # Fetch citations from external sources or cache
                citations, cache_hit = fetcher.fetch_citations(paper.doi)

                if cache_hit:
                    results["cache_hits"] += 1
                else:
                    results["cache_misses"] += 1

                if not citations:
                    if verbose:
                        console.print(
                            f"[yellow][{i}/{len(target_papers)}] No citations found for {paper.doi}"
                        )
                    continue

                if limit:
                    citations = citations[:limit]
                results["papers_with_citations"] += 1
                results["citations_fetched"] += len(citations)

                if debug:
                    console.print(
                        f"[cyan][{i}/{len(target_papers)}] Fetched {len(citations)} "
                        f"citations for {paper.doi}[/cyan]"
                    )

                # Store citations in paper
                paper.citations.extend(citations)

                if debug:
                    console.print(
                        f"[blue]Paper {paper.doi} now has {len(paper.citations)} citations[/blue]"
                    )

            except Exception as e:
                results["errors"].append(f"Fetch error for {paper.doi}: {str(e)}")
                console.print(f"[red]Error fetching citations for {paper.doi}: {e}[/red]")


    def _resolve_citations_and_fetch_papers(
        self,
        papers: List[Paper],
        fetcher: "Fetcher",
        continue_on_not_found: bool = True,
        dry_run: bool = False,
        results: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
        debug: bool = False
    ) -> None:
        """
        PASS 2: Resolve citations to existing papers or create new papers.

        Iterates over all papers with citations, resolves each citation to
        existing papers or creates new Paper records, and fetches metadata
        for enrichment. Updates Citation.resolved_paper with full Paper object.

        Args:
            papers: List of all papers (including those with citations)
            fetcher: Fetcher instance to use for metadata enrichment
            continue_on_not_found: If True, create new Paper for unresolved citations
            dry_run: Don't write to database if True
            results: Results dict to update with statistics (optional)
            verbose: Enable verbose output
            debug: Enable debug output
        """
        if results is None:
            results = {}

        for paper in papers:
            if not paper.citations:
                continue

            if debug:
                console.print(f"[cyan]Resolving {len(paper.citations)} citations for {paper.doi}[/cyan]")

            try:
                # Resolve each citation
                for citation in paper.citations:
                    resolved_paper, created_new = self._resolve_citation(
                        citation=citation,
                        citing_paper=paper,
                        fetcher=fetcher,
                        continue_on_not_found=continue_on_not_found,
                        dry_run=dry_run,
                        verbose=verbose,
                        debug=debug
                    )

                    if resolved_paper:
                        # Store full Paper object for Pass 3 linking
                        citation.resolved_paper = resolved_paper
                        results["citations_resolved"] = results.get("citations_resolved", 0) + 1
                        if created_new:
                            results["citations_created_new_paper"] = results.get("citations_created_new_paper", 0) + 1
                    else:
                        results["citations_unresolved"] = results.get("citations_unresolved", 0) + 1

                    if debug:
                        console.print(f"[blue]Citation resolved: {resolved_paper.id if resolved_paper else 'None'}[/blue]")

            except Exception as e:
                results["errors"].append(f"Resolve error for {paper.doi}: {str(e)}")
                console.print(f"[red]Error resolving citations for {paper.doi}: {e}[/red]")
                if debug:
                    logger.exception(f"Exception while resolving citations for {paper.doi}")

    def _resolve_citation(
        self,
        citation: Citation,
        citing_paper: Paper,
        fetcher: "Fetcher",
        continue_on_not_found: bool = True,
        dry_run: bool = False,
        verbose: bool = False,
        debug: bool = False
    ) -> Tuple[Optional[Paper], bool]:
        """
        Resolve a citation to an existing paper or create a new paper.

        Attempts to resolve the citation to an existing paper by DOI or title+year.
        If found, fetches full metadata via fetcher.fetch_paper() for enrichment.
        If not found and continue_on_not_found=True, creates a new Paper record.
        Citation graph linking (cited_by) is deferred to Pass 3.

        Args:
            citation: Citation object to link
            citing_paper: Paper that contains this citation
            fetcher: Fetcher instance for metadata enrichment
            continue_on_not_found: If True, create new Paper; if False, leave unresolved
            dry_run: Don't write to database if True
            verbose: Enable verbose output
            debug: Enable debug output

        Returns:
            Tuple of (resolved_paper, created_new_paper: bool)
        """
        # Try to resolve by DOI first
        if citation.doi:
            normalized_doi = DOI(citation.doi).stem
            papers = self.db.get_by_doi(normalized_doi, primary_only=True)
            if papers:
                paper = papers[0]
                return paper, False
            else:
                enriched_paper, cached = fetcher.fetch_paper(normalized_doi)
                if cached and debug:
                    console.print(f"[green]Cache hit for citation DOI {normalized_doi}[/green]")
                
                # Only add if fetcher successfully returned a paper
                if enriched_paper:
                    self.db.add(enriched_paper)
                    return enriched_paper, True
                else:
                    if debug:
                        console.print(f"[yellow]Could not fetch paper for DOI {normalized_doi}[/yellow]")
                    return None, False

        # Citation not found in database
        # TODO: Implement title+year and/or other resolutions if needed
        if continue_on_not_found:
            return None, False
        else:
            raise ValueError(f"Citation {citation.doi} could not be resolved and 'continue_on_not_found' is False.")

    def _link_citation_graph(
        self,
        papers: List[Paper],
        results: Dict[str, Any],
        verbose: bool = False,
        debug: bool = False
    ) -> None:
        """
        PASS 3: Build citation graph in memory (cited_papers, cited_by_papers).

        Iterates over all papers and their citations, linking resolved citations
        bidirectionally by updating cited_papers and cited_by lists.

        Args:
            papers: List of all papers
            results: Results dict to update with statistics
            verbose: Enable verbose output
            debug: Enable debug output
        """
        for paper in papers:
            if not paper.citations:
                continue

            for citation in paper.citations:
                resolved_paper = citation.resolved_paper
                if not resolved_paper:
                    continue

                # Link cited paper
                if resolved_paper.id not in [p.id for p in paper.cited_papers]:
                    paper.cited_papers.append(resolved_paper)
                    results["forward_links_created"] += 1

                # Link citing paper
                if paper.id not in [p.id for p in resolved_paper.cited_by_papers]:
                    resolved_paper.cited_by_papers.append(paper)
                    results["reverse_links_created"] += 1

