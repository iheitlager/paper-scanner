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
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from rich.console import Console
import logging

from paper_scanner.core.models import Paper
from paper_scanner.core.database import PapersDatabase
from paper_scanner.tools.fetchers.fetcher import Fetcher
from .base import BaseStep

console = Console(file=sys.stderr)
logger = logging.getLogger(__name__)


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

        # Initialize fetcher with specified methods
        fetcher = Fetcher(cache_dir=self.cache_dir, methods=methods)

        # Get all papers
        papers = self.db.all(primary_only=True)

        results = {
            "total_papers": len(papers),
            "updated_papers": 0,
            "skipped_no_doi": 0,
            "not_found": 0,
            "errors": [],
            "cache_hits": 0,
            "cache_misses": 0,
        }

        for i, paper in enumerate(papers, 1):
            if not paper.doi:
                results["skipped_no_doi"] += 1
                console.print(f"[yellow][{i}/{len(papers)}] Skipping: no DOI")
                continue

            try:
                console.print(
                    f"[cyan][{i}/{len(papers)}] Fetching metadata for[/cyan] [white]{paper.doi}...",
                    end=" ",
                )

                # Fetch metadata
                enriched_paper, cache_hit = fetcher.fetch_metadata(paper.doi)

                if enriched_paper is None:
                    results["not_found"] += 1
                    console.print("[yellow]Not found")
                    if not continue_on_not_found:
                        results["errors"].append(f"{paper.doi}: Not found in any source")
                    continue

                # Merge enriched metadata into existing paper
                _merge_paper_metadata(paper, enriched_paper)

                # Update database (unless in dry_run mode)
                if not dry_run:
                    self.db.update(paper)
                results["updated_papers"] += 1

                # Track cache hit/miss
                if cache_hit:
                    results["cache_hits"] += 1
                    console.print("[green]Updated (from cache)")
                else:
                    results["cache_misses"] += 1
                    console.print("[green]Updated (from API)")

            except Exception as e:
                console.print(f"[red]Error: {str(e)}")
                results["errors"].append(f"{paper.doi}: {str(e)}")
                logger.exception(f"Error fetching metadata for {paper.doi}")

        # Print summary
        console.print("\n" + "=" * 60)
        console.print(f"[bold]Metadata Retrieval Summary[/bold]")
        console.print(f"  Total papers: {results['total_papers']}")
        console.print(f"  Updated: {results['updated_papers']}")
        console.print(f"  Skipped (no DOI): {results['skipped_no_doi']}")
        console.print(f"  Not found: {results['not_found']}")
        console.print(f"  Cache hits: {results['cache_hits']}")
        console.print(f"  Cache misses: {results['cache_misses']}")
        if results["errors"]:
            console.print(f"[red]  Errors: {len(results['errors'])}[/red]")

        return results


def _merge_paper_metadata(target: Paper, source: Paper) -> None:
    """
    Merge metadata from enriched Paper into target Paper.

    Only updates fields that are empty in the target.
    """
    if not target.abstract and source.abstract:
        target.abstract = source.abstract

    if not target.keywords and source.keywords:
        target.keywords = source.keywords

    if not target.topics and source.topics:
        target.topics = source.topics

    if not target.authors and source.authors:
        target.authors = source.authors

    if not target.year and source.year:
        target.year = source.year

    if not target.journal and source.journal:
        target.journal = source.journal

    if not target.publisher and source.publisher:
        target.publisher = source.publisher

    if not target.volume and source.volume:
        target.volume = source.volume

    if not target.number and source.number:
        target.number = source.number

    if not target.pages and source.pages:
        target.pages = source.pages

    if not target.publication_date and source.publication_date:
        target.publication_date = source.publication_date

    if not target.paper_type and source.paper_type:
        target.paper_type = source.paper_type

    if not target.language and source.language:
        target.language = source.language

    if not target.oa_status and source.oa_status:
        target.oa_status = source.oa_status

    if source.raw_json and not target.raw_json:
        target.raw_json = source.raw_json

    # Update timestamps
    target.updated_at = datetime.now()
