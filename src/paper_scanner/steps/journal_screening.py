"""
Journal screening step for validating and enriching paper journal metadata.

Performs journal-based paper filtering and metadata enrichment:
- Matches paper journal names against curated journal definitions
- Validates journal presence in defined views (Academy, AIS Basket, VHB rankings, Innovation)
- Enriches papers with standardized journal acronyms and ISO4 abbreviations
- Supports both exact matching and ISO4 generation fallback
- Populates paper.screening.journal_screening with results

Configuration supports:
- journal_definitions_path: Path to YAML definitions file (default: etc/journal_definitions.yml)
- required_views: Filter papers to only those in specified journal views
- generate_iso4: Generate ISO4 abbreviations for unmatched journals (default: true)
- skip_missing: Skip papers with missing journal names instead of failing (default: false)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Paper, ProcessingMetadata, Screening, JournalScreeningResult
from paper_scanner.core.step_result import StepResult
from paper_scanner.tools.documents.journals import JournalLookup
from .base import BaseStep

console = Console(file=sys.stderr)


class JournalScreeningStep(BaseStep):
    """Journal-based screening and metadata enrichment step."""

    def __init__(self, general_config: Dict[str, Any], db: PapersDatabase, cache_dir: Path, **kwargs):
        """Initialize journal screening step.
        
        Args:
            general_config: Project-level configuration
            db: Papers database instance
            cache_dir: Cache directory for step artifacts
        """
        super().__init__(general_config, db, cache_dir, **kwargs)
        self.journal_lookup: Optional[JournalLookup] = None

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate journal_screening step configuration.
        
        Args:
            config: Step configuration with optional keys:
                - journal_definitions_path: str - Path to YAML definitions file
                - required_views: list[str] - Filter to journals in these views
                - generate_iso4: bool - Generate ISO4 for unmatched journals (default: true)
                - skip_missing: bool - Skip papers with missing journals (default: false)
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate journal_definitions_path if provided
        if "journal_definitions_path" in config:
            path = config["journal_definitions_path"]
            if not isinstance(path, str):
                errors.append("'journal_definitions_path' must be a string")
            elif not Path(path).exists():
                errors.append(f"Journal definitions file not found: {path}")

        # Validate required_views if provided
        if "required_views" in config:
            views = config["required_views"]
            if not isinstance(views, list):
                errors.append("'required_views' must be a list of strings")
            elif not all(isinstance(v, str) for v in views):
                errors.append("All items in 'required_views' must be strings")

        # Validate generate_iso4 if provided
        if "generate_iso4" in config and not isinstance(config["generate_iso4"], bool):
            errors.append("'generate_iso4' must be a boolean")

        # Validate skip_missing if provided
        if "skip_missing" in config and not isinstance(config["skip_missing"], bool):
            errors.append("'skip_missing' must be a boolean")

        return (len(errors) == 0, errors)

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """Execute journal screening step.
        
        Args:
            config: Step-specific configuration
            verbose: Enable verbose output
            dry_run: Perform dry run without modifying database
            debug: Enable debug logging
        
        Returns:
            StepResult with screening results and statistics
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Load journal definitions
            defs_path = config.get("journal_definitions_path")
            self.journal_lookup = JournalLookup(defs_path) if defs_path else JournalLookup()
            
            if verbose:
                console.print(f"[cyan]Loaded {self.journal_lookup.get_journal_count()} journal definitions")

            # Parse configuration (support both 'required_views' and 'include' for compatibility)
            required_views = config.get("required_views") or config.get("include", [])
            generate_iso4 = config.get("generate_iso4", True)
            skip_missing = config.get("skip_missing", False)

            # Get all papers from database
            papers = self.db.all(primary_only=True)
            total_papers = len(papers)

            if verbose:
                console.print(f"[cyan]Screening {total_papers} papers by journal")

            stats = {
                "total_papers": total_papers,
                "papers_matched": 0,
                "papers_with_iso4": 0,
                "papers_skipped": 0,
                "papers_with_errors": 0,
                "journals_count": self.journal_lookup.get_journal_count(),
            }

            # Process each paper
            for paper in papers:
                if not paper.journal:
                    if skip_missing:
                        stats["papers_skipped"] += 1
                        continue
                    else:
                        stats["papers_with_errors"] += 1
                        if debug:
                            console.print(f"[yellow]Paper {paper.id} has no journal name")
                        continue

                try:
                    # Try to lookup journal
                    journal_name, acronym, iso4 = self.journal_lookup.lookup(paper.journal)
                    stats["papers_matched"] += 1

                    # Check required views if specified
                    if required_views:
                        in_views = any(
                            journal_name in self.journal_lookup.list_journals()
                            for _ in required_views
                        )
                        if not in_views:
                            stats["papers_skipped"] += 1
                            continue

                    # Update paper with enriched metadata
                    if not dry_run:
                        paper.journal = journal_name
                        if not paper.screening:
                            paper.screening = Screening()

                        paper.screening.journal_screening = JournalScreeningResult(
                            journal_name=journal_name,
                            acronym=acronym,
                            iso4=iso4,
                            lookup_type="exact_match",
                            metadata=ProcessingMetadata(
                                timestamp=datetime.now(timezone.utc),
                                success=True
                            )
                        )

                        # Update in database
                        self.db.update(paper)

                        if iso4:
                            stats["papers_with_iso4"] += 1

                except ValueError:
                    # Journal not found
                    if generate_iso4:
                        try:
                            # Try with ISO4 generation fallback
                            iso4_generated = self.journal_lookup.iso4_gen.generate(paper.journal) or paper.journal
                            stats["papers_matched"] += 1
                            stats["papers_with_iso4"] += 1

                            if not dry_run:
                                if not paper.screening:
                                    paper.screening = Screening()

                                paper.screening.journal_screening = JournalScreeningResult(
                                    journal_name=paper.journal,
                                    iso4=iso4_generated,
                                    lookup_type="iso4_generation",
                                    metadata=ProcessingMetadata(
                                        timestamp=datetime.now(timezone.utc),
                                        success=True
                                    )
                                )

                                self.db.update(paper)

                        except Exception as e:
                            stats["papers_with_errors"] += 1
                    else:
                        stats["papers_with_errors"] += 1

            # Calculate execution time
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Build result message
            message = (
                f"Screened {stats['papers_matched']} papers by journal, "
                f"{stats['papers_with_iso4']} with ISO4, "
                f"{stats['papers_with_errors']} with errors"
            )

            if dry_run:
                message += " (dry run)"

            return StepResult(
                status=StepStatus.SUCCESS if stats["papers_with_errors"] == 0 else StepStatus.WARNING,
                message=message,
                stats=stats,
                details=(
                    f"## Journal Screening Results\n\n"
                    f"- **Total papers**: {total_papers}\n"
                    f"- **Papers matched**: {stats['papers_matched']}\n"
                    f"- **Papers with ISO4**: {stats['papers_with_iso4']}\n"
                    f"- **Papers skipped**: {stats['papers_skipped']}\n"
                    f"- **Papers with errors**: {stats['papers_with_errors']}\n"
                    f"- **Duration**: {duration:.2f}s\n"
                ),
            )

        except FileNotFoundError as e:
            return StepResult(
                status=StepStatus.ERROR,
                message=f"Journal definitions file not found: {e}",
                stats={},
                error=str(e),
            )
        except Exception as e:
            return StepResult(
                status=StepStatus.ERROR,
                message=f"Error during journal screening: {e}",
                stats={},
                error=str(e),
            )
