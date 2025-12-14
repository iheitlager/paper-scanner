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

IMPORTANT: Changes are made to the in-memory database. To persist them across
runs, add a 'checkpoint' or 'export' step after this step in your workflow.

Within a single run, all subsequent steps will see the updated metadata.
Across runs, you need to save a checkpoint.

Example workflow:
  - load_files: Load PDFs
  - retrieve_metadata: Fetch metadata from APIs
  - checkpoint: Save state (so next run can resume)
  - export: Export to final format
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

console = Console(file=sys.stderr)
logger = logging.getLogger(__name__)


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
    config: Dict[str, Any],
    db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False,
    cache_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Execute metadata retrieval for all papers in database.

    Args:
        config: Step configuration
        db: Papers database
        verbose: Enable verbose output
        dry_run: Don't write to database if True
        cache_dir: Optional cache directory for fetchers

    Returns:
        Results dict with statistics
    """
    methods = config.get("methods", ["crossref"])
    continue_on_not_found = config.get("continue_on_not_found", True)

    # Initialize fetcher with specified methods
    # cache_dir must be provided from outside (CLI framework)
    if cache_dir is None:
        raise ValueError("cache_dir must be provided to retrieve_metadata step")
    
    fetcher = Fetcher(cache_dir=cache_dir, methods=methods)

    # Get all papers
    papers = db.all(primary_only=True)

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
                try:
                    db.update(paper)
                    logger.info(f"Database updated for {paper.doi}")
                    if verbose:
                        console.print(f"  [dim]Database updated[/dim]")
                except Exception as e:
                    logger.error(f"Failed to update database for {paper.doi}: {e}")
                    results["errors"].append(f"{paper.doi}: Database update failed: {e}")
                    raise
            else:
                logger.info(f"Would update database for {paper.doi} (dry_run mode)")
                
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
    console.print(f"  Updated: {results['updated_papers']} (database updated)")
    console.print(f"  Skipped (no DOI): {results['skipped_no_doi']}")
    console.print(f"  Not found: {results['not_found']}")
    console.print(f"  Cache hits: {results['cache_hits']}")
    console.print(f"  Cache misses: {results['cache_misses']}")
    if results["errors"]:
        console.print(f"[red]  Errors: {len(results['errors'])}[/red]")
    
    if results["updated_papers"] > 0:
        console.print(f"\n[green]✓ Changes are in the in-memory database.[/green]")
        console.print(f"[yellow]→ To persist across runs, add a 'checkpoint' or 'export' step after this step.[/yellow]")

    return results


def _merge_paper_metadata(target: Paper, source: Paper) -> None:
    """
    Merge metadata from enriched Paper into target Paper.

    Only updates fields that are empty in the target.
    """
    merged_fields = []
    
    if not target.abstract and source.abstract:
        target.abstract = source.abstract
        merged_fields.append("abstract")

    if not target.keywords and source.keywords:
        target.keywords = source.keywords
        merged_fields.append(f"keywords({len(source.keywords)})")

    if not target.topics and source.topics:
        target.topics = source.topics
        merged_fields.append(f"topics({len(source.topics)})")

    if not target.authors and source.authors:
        target.authors = source.authors
        merged_fields.append(f"authors({len(source.authors)})")

    if not target.year and source.year:
        target.year = source.year
        merged_fields.append("year")

    if not target.journal and source.journal:
        target.journal = source.journal
        merged_fields.append("journal")

    if not target.publisher and source.publisher:
        target.publisher = source.publisher
        merged_fields.append("publisher")

    if not target.volume and source.volume:
        target.volume = source.volume
        merged_fields.append("volume")

    if not target.number and source.number:
        target.number = source.number
        merged_fields.append("number")

    if not target.pages and source.pages:
        target.pages = source.pages
        merged_fields.append("pages")

    if not target.publication_date and source.publication_date:
        target.publication_date = source.publication_date
        merged_fields.append("publication_date")

    if not target.paper_type and source.paper_type:
        target.paper_type = source.paper_type
        merged_fields.append("paper_type")

    if not target.language and source.language:
        target.language = source.language
        merged_fields.append("language")

    if not target.oa_status and source.oa_status:
        target.oa_status = source.oa_status
        merged_fields.append("oa_status")

    if source.raw_json and not target.raw_json:
        target.raw_json = source.raw_json
        merged_fields.append("raw_json")

    # Update timestamps
    target.updated_at = datetime.now()
    
    # Log what was merged
    if merged_fields:
        logger.info(f"Merged {len(merged_fields)} fields for {target.doi}: {', '.join(merged_fields)}")
    else:
        logger.info(f"No fields merged for {target.doi} (all fields already populated in target)")
