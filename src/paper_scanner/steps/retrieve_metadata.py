"""
Retrieve metadata step - Enrich Paper records with complete metadata from external APIs.

Walks over all Paper records in the database and fetches complete bibliographic
metadata from configured sources (Crossref, OpenAlex, etc.), translating API
responses into Paper model fields.

Process:
1. Get all Paper records from database
2. For each paper with a DOI:
   - Check cache first
   - Fetch from primary source (Crossref by default)
   - Translate API response to Paper fields
   - Update database record
   - Track cache hits/misses
"""

import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Paper
from paper_scanner.core.step_result import StepResult
from paper_scanner.tools.fetchers.fetcher import Fetcher

from .base import BaseStep

console = Console(file=sys.stderr)

class RetrieveMetadataStep(BaseStep):
    """Retrieve and enrich metadata for papers from external sources."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate retrieve_metadata step configuration.

        Args:
            config: Step configuration with:
                - methods: List of fetcher names to use (e.g., ["crossref"])
                - continue_on_not_found: bool (default True)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check methods
        if "methods" not in config:
            errors.append("'methods' is required (e.g., ['crossref', 'openalex'])")
        elif not isinstance(config["methods"], list) or len(config["methods"]) == 0:
            errors.append("'methods' must be a non-empty list of fetcher names")
        if "continue_on_not_found" in config:
            continue_on_not_found = config["continue_on_not_found"]
            if not isinstance(continue_on_not_found, bool):
                errors.append("'continue_on_not_found' must be a boolean")
        if "overwrite" in config:
            overwrite = config["overwrite"]
            if not isinstance(overwrite, bool):
                errors.append("'overwrite' must be a boolean")

        return len(errors) == 0, errors

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute metadata retrieval for all papers in database.

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't write to database if True
            debug: Enable debug output

        Returns:
            Results dict with statistics
        """
        methods = config.get("methods", ["crossref"])
        continue_on_not_found = config.get("continue_on_not_found", True)
        overwrite = config.get("overwrite", True)

        self.callback(f"Using methods: {methods}", debug=True)

        # Initialize fetcher with specified methods
        fetcher = Fetcher(cache_dir=self.cache_dir, methods=methods, verbose=verbose, debug=debug)

        # Get all papers
        papers = self.db.all(primary_only=True)

        stats = {
            "total_papers": len(papers),
            "updated_papers": 0,
            "skipped_no_doi": 0,
            "not_found": 0,
            "errors": [],
            "cache_hits": 0,
            "api_calls": 0,
        }
        errors = []

        for i, paper in enumerate(papers, 1):
            if not paper.doi:
                stats["skipped_no_doi"] += 1
                self.callback(f"[yellow]⚠️[{i}/{len(papers)}][/yellow] Skipping: no DOI", debug=True)
                continue

            # Fetch metadata
            enriched_paper, cache_hit, handler = fetcher.fetch_paper(paper.doi)
            if cache_hit:
                cache = "💾"
                stats["cache_hits"] += 1
            else:
                cache = "🌐"
                stats["api_calls"] += 1

            self.callback(f"[{i}/{len(papers)}]{cache}Fetching metadata for {paper.doi}...", debug=True)

            if enriched_paper is None:
                stats["not_found"] += 1
                self.callback("[yellow]Not found[/yellow]", debug=True)
                if not continue_on_not_found:
                    errors.append(f"{paper.doi}: Not found in any source")
                continue
            else:
                self.callback(f"[dim]Fetched metadata: {enriched_paper} from[/dim] '{handler}'", debug=True)

            # Merge enriched metadata into existing paper
            _merge_paper_metadata(paper, enriched_paper, overwrite=overwrite)

            # Update database (unless in dry_run mode)
            if not dry_run:
                self.db.update(paper)
            stats["updated_papers"] += 1

        result = StepResult(
            status = StepStatus.SUCCESS if len(errors) == 0 else StepStatus.ERROR,
            stats = stats,
            message = f"Metadata retrieval complete: {stats['updated_papers']} updated, {stats['not_found']} not found, {stats['skipped_no_doi']} skipped.",
            details = "\n".join(errors) if errors else None
        )
        return result


def _merge_paper_metadata(target: Paper, source: Paper, overwrite: bool = False) -> None:
    """
    Merge metadata from enriched Paper into target Paper.

    Only updates fields that are empty in the target.
    """
    if (overwrite or not target.abstract) and source.abstract:
        target.abstract = source.abstract

    if (overwrite or not target.title) and source.title:
        target.title = source.title

    if (overwrite or not target.keywords) and source.keywords:
        target.keywords = source.keywords

    if (overwrite or not target.topics) and source.topics:
        target.topics = source.topics

    if (overwrite or not target.authors) and source.authors:
        target.authors = source.authors

    if (overwrite or not target.year) and source.year:
        target.year = source.year

    if (overwrite or not target.journal) and source.journal:
        target.journal = source.journal

    if (overwrite or not target.url) and source.url:
        target.url = source.url

    if (overwrite or not target.isbn) and source.isbn:
        target.isbn = source.isbn

    if (overwrite or not target.issn) and source.issn:
        target.issn = source.issn

    if (overwrite or not target.pmid) and source.pmid:
        target.pmid = source.pmid

    if (overwrite or not target.publisher) and source.publisher:
        target.publisher = source.publisher

    if (overwrite or not target.volume) and source.volume:
        target.volume = source.volume

    if (overwrite or not target.number) and source.number:
        target.number = source.number

    if (overwrite or not target.pages) and source.pages:
        target.pages = source.pages

    if (overwrite or not target.publication_date) and source.publication_date:
        target.publication_date = source.publication_date

    if (overwrite or not target.paper_type) and source.paper_type:
        target.paper_type = source.paper_type

    if (overwrite or not target.oa_status) and source.oa_status:
        target.oa_status = source.oa_status

    if (overwrite or not target.raw_json) and source.raw_json:
        target.raw_json = source.raw_json

    # Update timestamps
    target.updated_at = datetime.now()
