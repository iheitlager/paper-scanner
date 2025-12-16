"""
Citations step - Extract backward citations from papers using external APIs.

Walks over Paper records in the database and fetches backward citations
(references) from configured sources (Crossref by default), then resolves
citations against the Paper database and creates new Paper records for
unresolved citations.

Process:
1. Filter papers by paper_type (default: journal_article)
2. For each paper with a DOI:
   - Fetch citations from configured source (Crossref)
   - For each citation:
     a. Normalize citation DOI if available
     b. Query database for existing paper with matching DOI
     c. If found: link citation to existing paper, update cited_by
     d. If not found and continue_on_not_found=True: Create new Paper record
        with discovery.iteration = citing_paper.discovery.iteration + 1
     e. Store Citation object in paper.citations list
3. Update paper record in database with new citations
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
from paper_scanner.tools.doi import DOI
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
                    - source: Fetcher name(s) - string or list (default: "crossref")
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
                if "source" in backward:
                    source = backward["source"]
                    if not isinstance(source, (str, list)):
                        errors.append("'backward.source' must be a string or list of fetcher names")
                    elif isinstance(source, list):
                        for s in source:
                            if not isinstance(s, str):
                                errors.append(f"'backward.source' items must be strings, got {type(s).__name__}")
                if "continue_on_not_found" in backward:
                    if not isinstance(backward["continue_on_not_found"], bool):
                        errors.append("'backward.continue_on_not_found' must be a boolean")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute backward citations extraction for papers in two passes.

        Pass 1: Fetch citations from external sources and store in papers
        Pass 2: Resolve citations to existing papers or create new papers

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't write to database if True
            debug: Enable debug output

        Returns:
            Results dict with statistics
        """
        # Extract configuration
        paper_types = config.get("paper-types", ["journal_article"])
        backward_config = config.get("backward", {})
        sources = backward_config.get("source", ["crossref"])
        continue_on_not_found = backward_config.get("continue_on_not_found", True)

        if verbose:
            console.print(f"[blue]Paper types to process:[/blue] {paper_types}")
            console.print(f"[blue]Citation sources:[/blue] {sources}")
            console.print(f"[blue]Continue on not found:[/blue] {continue_on_not_found}")

        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=sources,
            verbose=verbose,
            debug=debug
        )

        # Get papers to process (filter by paper_type)
        papers = self.db.all(primary_only=True)
        target_papers = [
            p for p in papers
            if p.paper_type and p.paper_type.value in paper_types and p.doi
        ]

        if debug:
            console.print(f"[blue]Fetcher initialized:[/blue]\n{pformat(fetcher.handlers, indent=2)}")
            console.print(f"[blue]Total papers in DB:[/blue] {len(papers)}")
            console.print(f"[blue]Target papers to process:[/blue] {len(target_papers)}")

        results = {
            "total_papers": len(papers),
            "target_papers": len(target_papers),
            "papers_with_citations": 0,
            "citations_fetched": 0,
            "citations_resolved": 0,
            "citations_created_new_paper": 0,
            "citations_unresolved": 0,
            "errors": [],
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # PASS 1: Fetch citations from external sources
        self._fetch_citations_for_papers(
            target_papers=target_papers,
            fetcher=fetcher,
            results=results,
            verbose=verbose,
            debug=debug
        )

        # PASS 2: Resolve citations and expand database
        self._resolve_and_create_citations(
            papers=target_papers,
            continue_on_not_found=continue_on_not_found,
            dry_run=dry_run,
            results=results,
            verbose=verbose,
            debug=debug
        )

        return results

    def _fetch_citations_for_papers(
        self,
        target_papers: List[Paper],
        fetcher: "Fetcher",
        results: Dict[str, Any],
        verbose: bool = False,
        debug: bool = False
    ) -> None:
        """
        PASS 1: Fetch citations from external sources and store in papers.

        Iterates over target papers, fetches citations from configured sources,
        and stores them in each paper's citations list.

        Args:
            target_papers: List of papers to fetch citations for
            fetcher: Fetcher instance to use for citation retrieval
            results: Results dict to update with statistics
            verbose: Enable verbose output
            debug: Enable debug output
        """
        for i, paper in enumerate(target_papers, 1):
            if not paper.doi:
                continue

            try:
                # Fetch citations from external source
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

                results["papers_with_citations"] += 1
                results["citations_fetched"] += len(citations)

                if verbose:
                    console.print(
                        f"[cyan][{i}/{len(target_papers)}] Fetched {len(citations)} "
                        f"citations for {paper.doi}[/cyan]"
                    )

                # Store citations in paper
                paper.citations.extend(citations)
                paper.citation_count = len(paper.citations)

                if debug:
                    console.print(
                        f"[blue]Paper {paper.doi} now has {len(paper.citations)} citations[/blue]"
                    )

            except Exception as e:
                results["errors"].append(f"Fetch error for {paper.doi}: {str(e)}")
                console.print(f"[red]Error fetching citations for {paper.doi}: {e}[/red]")
                if debug:
                    logger.exception(f"Exception while fetching citations for {paper.doi}")

    def _resolve_and_create_citations(
        self,
        papers: List[Paper],
        continue_on_not_found: bool = True,
        dry_run: bool = False,
        results: Optional[Dict[str, Any]] = None,
        verbose: bool = False,
        debug: bool = False
    ) -> None:
        """
        PASS 2: Resolve citations to existing papers or create new papers.

        Iterates over all papers with citations, resolves each citation to
        existing papers or creates new Paper records, and updates the database.

        Args:
            papers: List of all papers (including those with citations)
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

            if verbose:
                console.print(f"[cyan]Resolving {len(paper.citations)} citations for {paper.doi}[/cyan]")

            try:
                # Resolve each citation
                for citation in paper.citations:
                    resolved_id, created_new = self._link_citation(
                        citation=citation,
                        citing_paper=paper,
                        continue_on_not_found=continue_on_not_found,
                        dry_run=dry_run,
                        verbose=verbose,
                        debug=debug
                    )

                    if resolved_id:
                        citation.resolved_paper = None  # Don't store full Paper object
                        if not hasattr(citation, "resolved_paper_id"):
                            citation.resolved_paper_id = resolved_id
                        results["citations_resolved"] = results.get("citations_resolved", 0) + 1
                        if created_new:
                            results["citations_created_new_paper"] = results.get("citations_created_new_paper", 0) + 1
                    else:
                        results["citations_unresolved"] = results.get("citations_unresolved", 0) + 1

                    if debug:
                        console.print(f"[blue]Citation resolved: {resolved_id}[/blue]")

                # Update paper in database (unless in dry_run mode)
                if not dry_run:
                    self.db.update(paper)

            except Exception as e:
                results["errors"].append(f"Resolve error for {paper.doi}: {str(e)}")
                console.print(f"[red]Error resolving citations for {paper.doi}: {e}[/red]")
                if debug:
                    logger.exception(f"Exception while resolving citations for {paper.doi}")

    def _link_citation(
        self,
        citation: Citation,
        citing_paper: Paper,
        continue_on_not_found: bool = True,
        dry_run: bool = False,
        verbose: bool = False,
        debug: bool = False
    ) -> Tuple[Optional[str], bool]:
        """
        Link a citation to an existing paper or create a new paper.

        Attempts to resolve the citation to an existing paper by DOI or title+year.
        If not found and continue_on_not_found=True, creates a new Paper record.
        Updates the cited_by links bidirectionally.

        Args:
            citation: Citation object to link
            citing_paper: Paper that contains this citation
            continue_on_not_found: If True, create new Paper; if False, leave unresolved
            dry_run: Don't write to database if True
            verbose: Enable verbose output
            debug: Enable debug output

        Returns:
            Tuple of (resolved_paper_id, created_new_paper: bool)
        """
        # Try to resolve by DOI first
        if citation.doi:
            normalized_doi = DOI(citation.doi).stem
            if normalized_doi:
                papers = self.db.get_by_doi(normalized_doi, primary_only=True)
                if papers:
                    paper = papers[0]
                    # Follow duplicate chain to canonical paper
                    while paper.duplicate_of:
                        paper = paper.duplicate_of
                    
                    # Update cited_by link
                    if citing_paper.id not in paper.cited_by:
                        paper.cited_by.append(citing_paper.id)
                        if not dry_run:
                            self.db.update(paper)
                    
                    return paper.id, False

        # If not found by DOI, try title + year matching
        if not citation.doi and citation.title and citation.year:
            paper = self._find_paper_by_title_year(
                citation.title,
                citation.year
            )
            if paper:
                while paper.duplicate_of:
                    paper = paper.duplicate_of
                
                if citing_paper.id not in paper.cited_by:
                    paper.cited_by.append(citing_paper.id)
                    if not dry_run:
                        self.db.update(paper)
                
                return paper.id, False

        # Citation not found in database
        if not continue_on_not_found:
            return None, False

        # Create new Paper from unresolved citation
        try:
            iteration = (citing_paper.discovery.iteration + 1) if citing_paper.discovery else 1
            
            # Generate cite_key: prioritize DOI, fall back to title+year, then UUID
            cite_key = self._generate_cite_key_for_citation(citation)
            
            new_paper = Paper(
                cite_key=cite_key,
                title=citation.title,
                authors=[],
                year=citation.year,
                journal=citation.journal,
                volume=citation.volume,
                number=citation.issue,
                pages=citation.pages,
                publisher=citation.publisher,
                doi=citation.doi,
                discovery=Discovery(
                    method=DiscoveryMethod.BACKWARD_CITATION,
                    iteration=iteration,
                    source=f"citations_from_{citing_paper.id}",
                ),
                citation_count=0,
                reference_count=0,
            )
            
            # Save to database
            if not dry_run:
                self.db.add(new_paper)
            
            # Update citing paper's cited_by
            if citing_paper.id not in new_paper.cited_by:
                new_paper.cited_by.append(citing_paper.id)
                if not dry_run:
                    self.db.update(new_paper)
            
            if verbose:
                console.print(f"[green]Created new Paper from citation: {new_paper.title}[/green]")
            
            return new_paper.id, True

        except Exception as e:
            logger.error(f"Error creating new Paper from citation: {e}")
            return None, False

    def _generate_cite_key_for_citation(self, citation: Citation) -> str:
        """
        Generate cite_key for a citation using DOI > title+year > UUID fallback.

        Args:
            citation: Citation object

        Returns:
            Generated cite key string
        """
        import hashlib
        import uuid
        
        # Priority 1: Use DOI if available
        if citation.doi:
            normalized_doi = DOI(citation.doi).stem
            if normalized_doi:
                return "doi_" + hashlib.md5(normalized_doi.encode()).hexdigest()[:8]
        
        # Priority 2: Use title + year hash
        if citation.title and citation.year:
            hash_input = f"{citation.title}_{citation.year}".lower()
            return hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        # Priority 3: Fall back to random UUID
        return str(uuid.uuid4())[:8]

    def _generate_cite_key(self, title: Optional[str], year: Optional[int]) -> str:
        """
        Generate a unique cite key from title and year.

        Args:
            title: Paper title
            year: Publication year

        Returns:
            Generated cite key (guaranteed unique via UUID suffix)
        """
        import uuid
        
        if not title:
            title = "unknown"
        
        # Extract first word(s) from title
        words = title.lower().split()
        prefix = words[0][:3] if words else "unk"
        
        # Use year or default to current year
        year_str = str(year) if year else str(datetime.now().year)
        
        # Add UUID suffix to guarantee uniqueness (use first 8 chars)
        unique_suffix = str(uuid.uuid4())[:8]
        
        return f"{prefix}{year_str}_{unique_suffix}"

    def _find_paper_by_title_year(
        self,
        title: str,
        year: int,
        tolerance: float = 0.8
    ) -> Optional[Paper]:
        """
        Find paper by title and year with fuzzy matching using indexed candidates.

        Uses database indexes to efficiently retrieve candidate papers by year,
        then performs fuzzy matching only on relevant candidates (not all papers).

        Args:
            title: Paper title
            year: Publication year
            tolerance: Fuzzy match threshold (0-1)

        Returns:
            Paper if found with high confidence, None otherwise
        """
        if not title or not year:
            return None

        try:
            # Get candidates efficiently using year index (O(1) lookup)
            # This avoids scanning all papers in the database
            candidates = self.db.get_candidates_by_year_range(
                year=year,
                tolerance=1,  # ±1 year window
                primary_only=True
            )

            if not candidates:
                return None

            # Simple string similarity - look for papers with very similar titles
            from difflib import SequenceMatcher

            best_match = None
            best_ratio = 0
            
            # Precompute normalized query title (avoid repeated lowercase calls)
            query_normalized = title.lower()

            for candidate in candidates:
                if candidate.title_normalized:
                    # Use precomputed normalized title to avoid redundant .lower() calls
                    ratio = SequenceMatcher(None, query_normalized, candidate.title_normalized).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = candidate

            # Return only if similarity is high
            if best_ratio >= tolerance:
                return best_match

            return None

        except Exception as e:
            logger.error(f"Error querying database for title/year: {e}")
            return None
