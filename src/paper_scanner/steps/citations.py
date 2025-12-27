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

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import CitationDirection, StepStatus
from paper_scanner.core.models import Citation, Paper, PaperType
from paper_scanner.core.step_result import StepResult
from paper_scanner.tools.fetchers.fetcher import Fetcher

from .base import BaseStep


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

        for key in config.keys():
            # Validate paper_types
            if key =="paper-type":
                if not isinstance(config["paper-type"], list):
                    errors.append("'paper-types' must be a list")
                else:
                    valid_types = [pt.value for pt in PaperType]
                    for pt in config["paper-type"]:
                        if pt not in valid_types:
                            errors.append(f"'{pt}' is not a valid PaperType. Valid: {valid_types}")
            elif key =="continue_on_not_found":
                if not isinstance(config["continue_on_not_found"], bool):
                    errors.append("'continue_on_not_found' must be a boolean")
            elif key =="limit":
                if not isinstance(config["limit"], int) or config["limit"] < 1:
                    errors.append("'limit' must be a positive integer")

            # Validate backward config
            elif key == "backward":
                backward = config["backward"]
                if not isinstance(backward, dict):
                    errors.append("'backward' must be a dictionary")
                else:
                    if "citations" in backward:
                        citations = backward["citations"]
                        if not isinstance(citations, (str, list)):
                            errors.append("'backward.citations' must be a string or list of fetcher names")
                        elif isinstance(citations, list):
                            for src in citations:
                                if not isinstance(src, str):
                                    errors.append(f"'backward.citations' items must be strings, got {type(src).__name__}")
                    if "details" in backward:
                        details = backward["details"]
                        if not isinstance(details, (str, list)):
                            errors.append("'backward.details' must be a string or list of fetcher names")
                        elif isinstance(details, list):
                            for src in details:
                                if not isinstance(src, str):
                                    errors.append(f"'backward.details' items must be strings, got {type(src).__name__}")
                    if "output_errors" in backward:
                        if not isinstance(backward["output_errors"], str) or not Path(backward["output_errors"]).exists():
                            errors.append("'backward.output_errors' must be a valid file path")
                    for key in backward.keys():
                        if key not in ("citations", "details", "output_errors"):
                            errors.append(f"Unknown backward configuration key: '{key}'")

            # Validate forward config
            elif key == "forward":
                forward = config["forward"]
                if not isinstance(forward, dict):
                    errors.append("'forward' must be a dictionary")
                else:
                    if "citations" in forward:
                        citations = forward["citations"]
                        if not isinstance(citations, (str, list)):
                            errors.append("'forward.citations' must be a string or list of fetcher names")
                        elif isinstance(citations, list):
                            for src in citations:
                                if not isinstance(src, str):
                                    errors.append(f"'forward.citations' items must be strings, got {type(src).__name__}")
                    if "details" in forward:
                        details = forward["details"]
                        if not isinstance(details, (str, list)):
                            errors.append("'forward.details' must be a string or list of fetcher names")
                        elif isinstance(details, list):
                            for src in details:
                                if not isinstance(src, str):
                                    errors.append(f"'forward.details' items must be strings, got {type(src).__name__}")
                    if "output_errors" in forward:
                        if not isinstance(forward["output_errors"], str) or not Path(forward["output_errors"]).exists():
                            errors.append("'forward.output_errors' must be a valid file path")
                    for key in forward.keys():
                        if key not in ("citations", "details", "output_errors"):
                            errors.append(f"Unknown forward configuration key: '{key}'")
            else:
                errors.append(f"Unknown configuration key: '{key}'")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> StepResult:
        """
        Execute backward citations extraction for papers in three passes.

        Pass 1: Fetch citations from external sources and store in papers
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

        self.dry_run = dry_run

        # Extract configuration
        backward_config = config.get("backward", {})
        limit = config.get("limit", None)
        forward_config = config.get("forward", {})
        paper_types = config.get("paper-types", ["journal_article"])

        self.iteration = 1

            # Get papers to process (filter by paper_type)
        if paper_types:
            target_papers = self.db.find(
                lambda p: p.paper_type and p.paper_type.value in paper_types,
                primary_only=True
            )
        else:
            target_papers = self.db.all(primary_only=True)

        if limit:
            target_papers = target_papers[:limit]

        self.callback(f"Total papers in DB: {self.db.count(primary_only=True)}\n"
                      f" Target papers to process: {len(target_papers)}", debug=True)

        results = {
            "total_papers": self.db.count(primary_only=True),
            "target_papers": len(target_papers),
            "papers_with_citations": 0,
            "papers_with_cited_by": 0,
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

        if backward_config:
            self.backward_execute(config, target_papers, results)
        elif forward_config:
            self.forward_execute(config, target_papers, results)
        else:
            raise ValueError("CitationsStep requires 'backward' or 'forward' configuration.")

        return_details = StepResult(
            message=f"Papers: ({results['papers_with_citations']}/{results['papers_with_cited_by']}) Citations fetched: {results['citations_fetched']}, resolved: {results['citations_resolved']}, new papers: {results['citations_created_new_paper']}, unresolved: {results['citations_unresolved']}",
            status=StepStatus.SUCCESS if len(results['errors']) == 0 else StepStatus.ERROR,
        )
        if 'details' in results:
            return_details.details = results['details']
            results.pop('details')
        return_details.stats = results
        return return_details

    def backward_execute(self, config: Dict[str, Any], target_papers: List[Paper], results: Dict[str, Any]) -> None:
        """
        Execute backward citations extraction for papers in three passes.

        Pass 1: Fetch citations from external sources and store in papers
        Pass 2: Resolve citations to existing papers or create new papers
        Pass 3: Build citation graph in memory

        Args:
            config: Backward citations configuration
            target_papers: List of papers to process
            results: Results dict to update with statistics
        Returns:
            None
        """

        continue_on_not_found = config.get("continue_on_not_found", True)
        limit = config.get("limit", None)
        paper_types = config.get("paper-types", ["journal_article"])
        backward_config = config.get("backward", {})
        citations = backward_config.get("citations", ["crossref"])
        details = backward_config.get("details", ["crossref"])
        self.output_errors = backward_config.get("output_errors", None)
        if self.output_errors:
            # Clear existing error file
            Path(self.output_errors).write_text("", encoding="utf-8")

        self.callback(f"Citations backward processing\n"
                      f"Paper types to process: {paper_types}\n"
                      f"Citation sources: {citations}\n"
                      f"Details sources: {details}\n"
                      f"Continue on not found: {continue_on_not_found}\n"
                      + (f"Limit papers to process: {limit}" if limit else ""))

        # PASS 1: Fetch citations from external sourcess
        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=citations,
        )
        self._fetch_citations_for_papers(
            target_papers=target_papers,
            fetcher=fetcher,
            results=results,
            limit=limit,
        )

        # PASS 2: Resolve citations and expand database
        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=details
        )
        self._resolve_citations_and_fetch_papers(
            papers=target_papers,
            fetcher=fetcher,
            continue_on_not_found=continue_on_not_found,
            results=results,
        )
        # PASS 3: Build citation graph in memory
        all_papers = self.db.all(primary_only=False)
        self._link_citations(
            papers=all_papers,
            results=results,
        )

        return None

    def forward_execute(self, config: Dict[str, Any], target_papers: List[Paper], results: Dict[str, Any]) -> None:
        """
        Execute forward citations extraction for papers in three passes.

        Pass 1: Fetch citations from external sources and store in papers
        Pass 2: Resolve citations to existing papers or create new papers
        Pass 3: Build citation graph in memory

        Args:
            forward_config: Forward citations configuration
            target_papers: List of papers to process
            results: Results dict to update with statistics
        Returns:
            None
        """

        forward_config = config.get("forward", {})
        continue_on_not_found = config.get("continue_on_not_found", True)
        paper_types = config.get("paper-types", ["journal_article"])
        limit = config.get("limit", None)
        paper_types = config.get("paper-types", ["journal_article"])
        citations = forward_config.get("citations", ["crossref"])
        details = forward_config.get("details", ["crossref"])
        self.output_errors = forward_config.get("output_errors", None)
        if self.output_errors:
            # Clear existing error file
            Path(self.output_errors).write_text("", encoding="utf-8")

        self.callback(f"Citations forward processing\n"
                      f"Paper types to process: {paper_types}\n"
                      f"Citation sources: {citations}\n"
                      f"Details sources: {details}\n"
                      f"Continue on not found: {continue_on_not_found}\n"
                      + (f"Limit papers to process: {limit}" if limit else ""))

        # PASS 1: Fetch citations from external sourcess
        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=citations,
        )
        self._fetch_cited_by_for_papers(
            target_papers=target_papers,
            fetcher=fetcher,
            results=results,
            limit=limit,
        )

        # PASS 2: Resolve citations and expand database
        # Initialize fetcher
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=details,
        )
        self._resolve_cited_by_and_fetch_papers(
            papers=target_papers,
            fetcher=fetcher,
            continue_on_not_found=continue_on_not_found,
            results=results,
        )
        # PASS 3: Build citation graph in memory
        all_papers = self.db.all(primary_only=False)
        self._link_citations(
            papers=all_papers,
            results=results,
        )

        return None


    def _fetch_citations_for_papers(
        self,
        target_papers: List[Paper],
        fetcher: "Fetcher",
        results: Dict[str, Any],
        limit: Optional[int] = None,
    ) -> None:
        """
        PASS 1: Fetch citations from external sourcess and store in papers.

        Iterates over target papers, fetches citations from configured sourcess,
        and stores them in each paper's citations list.

        Args:
            target_papers: List of papers to fetch citations for
            fetcher: Fetcher instance to use for citation retrieval
            results: Results dict to update with statistics
            limit: Optional limit on number of citations to process
        """
        for i, paper in enumerate(target_papers, 1):
            if not paper.doi:
                continue

            try:
                # Fetch citations from external sources or cache
                citations, cache_hit = fetcher.fetch_citations(paper.doi)

                if cache_hit:
                    results["cache_hits"] += 1
                    cache = "💾"
                else:
                    results["cache_misses"] += 1
                    cache = "🌐"

                if not citations:
                    self.callback(f"[yellow][{i}/{len(target_papers)}] No citations found for {paper.doi}")
                    continue

                if limit:
                    citations = citations[:limit]
                results["papers_with_citations"] += 1
                results["citations_fetched"] += len(citations)

                self.callback(
                    f"[cyan][{i}/{len(target_papers)}]{cache}Fetched {len(citations)} "
                    f"citations for {paper.doi}[/cyan]", debug=True
                )

                # Store citations in paper
                paper.citations.extend(citations)


            except Exception as e:
                results["errors"].append(f"Fetch error for {paper.doi}: {str(e)}")
                self.callback(f"[red]Error fetching citations for {paper.doi}: {e}[/red]")


    def _fetch_cited_by_for_papers(
        self,
        target_papers: List[Paper],
        fetcher: "Fetcher",
        results: Dict[str, Any],
        limit: Optional[int] = None,
    ) -> None:
        """
        PASS 1: Fetch cited_by from external sources and store in papers.

        Iterates over target papers, fetches cited_by from configured sources,
        and stores them in each target paper's citations list. Download the paper
        if does not exist in the database.

        Args:
            target_papers: List of papers to fetch cited_by for
            fetcher: Fetcher instance to use for citation retrieval
            results: Results dict to update with statistics
            limit: Optional limit on number of citations to process
        """
        for i, paper in enumerate(target_papers, 1):
            if not paper.doi:
                continue

            try:
                # Fetch citations from external sources or cache
                citations, cache_hit = fetcher.fetch_cited_by(paper.doi, limit)

                if cache_hit:
                    results["cache_hits"] += 1
                    cache = "💾"
                else:
                    results["cache_misses"] += 1
                    cache = "🌐"

                if not citations:
                    self.callback(f"[yellow][{i}/{len(target_papers)}] No cited_by found for {paper.doi}")
                    continue

                if limit:
                    citations = citations[:limit]
                results["papers_with_cited_by"] += 1
                results["citations_fetched"] += len(citations)

                self.callback(f"[cyan][{i}/{len(target_papers)}]{cache}Fetched {len(citations)}\n"
                              f"citations for {paper.doi}[/cyan]", debug=True)

                # Store citations in paper
                paper.cited_by.extend(citations)


            except Exception as e:
                results["errors"].append(f"Fetch error for {paper.doi}: {str(e)}")
                self.callback(f"[red]Error fetching citations for {paper.doi}: {e}[/red]")

    def _resolve_citations_and_fetch_papers(
        self,
        papers: List[Paper],
        fetcher: "Fetcher",
        continue_on_not_found: bool = True,
        results: Optional[Dict[str, Any]] = None,
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
            results: Results dict to update with statistics (optional)
        """
        if results is None:
            results = {}

        missed_citations = {}
        for paper in papers:
            if not paper.citations:
                continue

            self.callback(f"[cyan]Resolving {len(paper.citations)} citations for {paper.doi}[/cyan]", debug=True)

            # Resolve each citation
            for citation in paper.citations:
                if citation.resolved:
                    continue  # Already resolved
                resolved_paper, created_new = self._resolve_citation(
                    citation=citation,
                    citing_paper=paper,
                    fetcher=fetcher,
                    continue_on_not_found=continue_on_not_found,
                    results=results,
                )

                if resolved_paper:
                    # Store full Paper object for Pass 3 linking
                    citation.resolved_paper = resolved_paper
                    citation.resolved = True
                    results["citations_resolved"] = results.get("citations_resolved", 0) + 1
                    if created_new:
                        results["citations_created_new_paper"] = results.get("citations_created_new_paper", 0) + 1
                else:
                    if self.output_errors:
                        citation_dict = citation.model_dump(exclude_none=True)
                        missed_citations.setdefault(paper.id, []).append(citation_dict)
                    results["citations_unresolved"] = results.get("citations_unresolved", 0) + 1
                    self.callback(f"[red]Unresolved citation {citation.doi} in paper {paper.doi}[/red]")
                    self.callback(f"[blue]{citation}[/blue]", debug=True)
        if self.output_errors and missed_citations:
            with open(self.output_errors, "a", encoding="utf-8") as f:
                for paper_id, citation in missed_citations.items():
                    f.write(json.dumps({"paper_id": paper_id, "citation": citation}) + "\n")
                self.callback(f"[yellow]Wrote {len(missed_citations)} unresolved citations to {self.output_errors}[/yellow]", debug=True)


    def _resolve_cited_by_and_fetch_papers(
        self,
        papers: List[Paper],
        fetcher: "Fetcher",
        continue_on_not_found: bool = True,
        results: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        PASS 2: Resolve cited_by to existing papers or create new papers.

        Iterates over all papers with cited_by, resolves each citation to
        existing papers or creates new Paper records, and fetches metadata
        for enrichment. Updates Citation.resolved_paper with full Paper object.

        Args:
            papers: List of all papers (including those with citations)
            fetcher: Fetcher instance to use for metadata enrichment
            continue_on_not_found: If True, create new Paper for unresolved citations
            results: Results dict to update with statistics (optional)
        """
        if results is None:
            results = {}

        missed_citations = {}
        for paper in papers:
            if not paper.cited_by:
                continue

            self.callback(f"[cyan]Resolving {len(paper.citations)} citations for {paper.doi}[/cyan]", debug=True)

            # Resolve each citation
            for citation in paper.cited_by:
                if citation.resolved:
                    continue  # Already resolved

                resolved_paper, created_new = self._resolve_citation(
                    citation=citation,
                    citing_paper=paper,
                    fetcher=fetcher,
                    continue_on_not_found=continue_on_not_found,
                    results=results,
                )

                if resolved_paper:
                    # Store full Paper object for Pass 3 linking
                    citation.resolved_paper = resolved_paper
                    citation.resolved = True
                    results["citations_resolved"] = results.get("citations_resolved", 0) + 1
                    if created_new:
                        results["citations_created_new_paper"] = results.get("citations_created_new_paper", 0) + 1
                else:
                    if self.output_errors:
                        citation_dict = citation.model_dump(exclude_none=True)
                        missed_citations.setdefault(paper.doi, []).append(citation_dict)
                    results["citations_unresolved"] = results.get("citations_unresolved", 0) + 1
                    
                    self.callback(f"[red]Unresolved citation {citation.doi} in paper {paper.doi}[/red]")
                    self.callback(f"[blue]{citation}[/blue]", debug=True)
        if self.output_errors and missed_citations:
            with open(self.output_errors, "a", encoding="utf-8") as f:
                for paper_id, citation in missed_citations.items():
                    f.write(json.dumps({"paper_id": paper_id, "citation": citation}) + "\n")
            self.callback(f"[yellow]Wrote {len(missed_citations)} paper with unresolved citations to {self.output_errors}[/yellow]")
        results['details'] = missed_citations

    def _resolve_citation(
        self,
        citation: Citation,
        citing_paper: Paper,
        fetcher: "Fetcher",
        continue_on_not_found: bool = True,
        results: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Paper], bool]:
        """
        Resolve a citation to an existing paper or create a new paper. This works
        for citations in both directions (backward and forward).

        Attempts to resolve the citation to an existing paper by DOI or title+year.
        If found, fetches full metadata via fetcher.fetch_paper() for enrichment.
        If not found and continue_on_not_found=True, creates a new Paper record.
        Citation graph linking (cited_by) is deferred to Pass 3.

        Args:
            citation: Citation object to link
            citing_paper: Paper that contains this citation
            fetcher: Fetcher instance for metadata enrichment
            continue_on_not_found: If True, create new Paper; if False, leave unresolved
            results: Results dict to update with cache statistics (optional)

        Returns:
            Tuple of (resolved_paper, created_new_paper: bool)
        """
        if results is None:
            results = {}
        results["cache_hits"] = 0
        results["cache_misses"] = 0

        # Try to resolve by DOI first
        if citation.doi:
            normalized_doi = DOI(citation.doi).stem
            papers = self.db.get_by_doi(normalized_doi, primary_only=True)
            if papers:
                paper = papers[0]
                self.callback(f"[green]Paper already in database: {normalized_doi}[/green]", debug=True)
                return paper, False
            else:
                enriched_paper, cache_hit, handler = fetcher.fetch_paper(normalized_doi)
                # enriched_paper.discovery.iteration = self.iteration

                # Track cache statistics
                if cache_hit:
                    results["cache_hits"] += 1
                    cache = "💾"
                else:
                    results["cache_misses"] += 1
                    cache = "🌐"
                # Only add if fetcher successfully returned a paper
                if enriched_paper:
                    self.db.add(enriched_paper)
                    self.callback(f"[green]{cache}Retrieved metadata for citation DOI {normalized_doi}[/green] with '{handler}'", debug=True)
                    return enriched_paper, True
                else:
                    self.callback(f"[yellow]Could not fetch paper for DOI {normalized_doi}[/yellow]", debug=True)
                    return None, False

        # Citation not found in database
        # TODO: Implement title+year and/or other resolutions if needed
        if continue_on_not_found:
            return None, False
        else:
            raise ValueError(f"Citation {citation.doi} could not be resolved and 'continue_on_not_found' is False.")

    def _link_citations(
        self,
        papers: List[Paper],
        results: Dict[str, Any],
    ) -> None:
        """
        PASS 3: Build citation graph in memory (cited_papers, cited_by_papers).

        Iterates over all papers and their citations forward and backward,
        linking resolved citations bidirectionally by updating cited_papers and
        cited_by_papers lists.
        This call is idempotent and can be run multiple times without duplicating links.

        Args:
            papers: List of all papers
            results: Results dict to update with statistics
        """
        for paper in papers:
            for citation in paper.citations:
                resolved_paper = citation.resolved_paper
                if not resolved_paper:
                    continue
                if not citation.direction == CitationDirection.BACKWARD:
                    raise ValueError(f"Citation direction must be BACKWARD in citations, got {citation.direction}")

                # Link cited paper
                if resolved_paper.id not in [p.id for p in paper.cited_papers]:
                    paper.cited_papers.append(resolved_paper)
                    results["forward_links_created"] += 1

                # Link citing paper
                if paper.id not in [p.id for p in resolved_paper.cited_by_papers]:
                    resolved_paper.cited_by_papers.append(paper)
                    results["reverse_links_created"] += 1

            for citation in paper.cited_by:
                resolved_paper = citation.resolved_paper
                if not resolved_paper:
                    continue
                if not citation.direction == CitationDirection.FORWARD:
                    raise ValueError(f"Citation direction must be FORWARD in cited_by citations, got {citation.direction}")

                # Link citing paper
                if resolved_paper.id not in [p.id for p in paper.cited_by_papers]:
                    paper.cited_by_papers.append(resolved_paper)
                    results["reverse_links_created"] += 1

                # Link cited paper
                if paper.id not in [p.id for p in resolved_paper.cited_papers]:
                    resolved_paper.cited_papers.append(paper)
                    results["forward_links_created"] += 1
