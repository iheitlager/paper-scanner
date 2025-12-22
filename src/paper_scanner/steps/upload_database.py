"""
PostgreSQL database upload step.

Loads papers from in-memory database into PostgreSQL with conflict handling.
Supports dry-run, conflict resolution strategies, and detailed reporting.

Configuration example:
```yaml
# Option 1: Pass full database URL
- step: Upload to PostgreSQL
  builtin.upload_database:
    database_url: "postgresql://user:password@localhost:5432/pdfdb"

# Option 2: Load from environment variables (via dotenv)
- step: Upload to PostgreSQL
  builtin.upload_database:
    db_username: "$DB_USER"          # or env var name
    db_password: "$DB_PASSWORD"
    db_host: "$DB_HOST"
    db_port: "$DB_PORT"
    db_name: "$DB_NAME"
    conflict_strategy: "skip"
```
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from rich.console import Console

from paper_scanner.core.enum import StepStatus
from paper_scanner.io.sql import (DatabaseConnectionPool, PaperToRowConverter,
                                  PaperUploader)
from paper_scanner.steps.base import BaseStep

console = Console(file=sys.stderr)


class UploadDatabaseStep(BaseStep):
    """
    Upload papers from in-memory database to PostgreSQL.
    
    Handles:
    - Connection pooling and transaction management
    - Conflict detection (cite_key, DOI duplicates)
    - Dry-run mode for validation
    - Detailed conflict reporting
    """

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate upload_database step configuration.

        Supports two modes:
        1. database_url: Full PostgreSQL connection string
        2. Individual components: db_username, db_password, db_host, db_port, db_name

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check that either database_url OR all individual components are provided
        has_database_url = "database_url" in config
        has_components = all(
            key in config
            for key in ("db_username", "db_password", "db_host", "db_port", "db_name")
        )

        if not (has_database_url or has_components):
            errors.append(
                "Must provide either 'database_url' OR all of: "
                "'db_username', 'db_password', 'db_host', 'db_port', 'db_name'"
            )

        # Validate database URL format if provided
        if has_database_url:
            database_url = config.get("database_url", "")
            if database_url and not database_url.startswith(("postgresql://", "$")):
                errors.append(
                    "Invalid database_url format. Expected: postgresql://user:pass@host:port/db "
                    "or environment variable like $DATABASE_URL"
                )

        # Validate batch size if provided
        if "batch_size" in config:
            try:
                batch_size = int(config["batch_size"])
                if batch_size < 1:
                    errors.append("batch_size must be positive integer")
            except (ValueError, TypeError):
                errors.append("batch_size must be integer")

        # Validate conflict strategy
        conflict_strategy = config.get("conflict_strategy", "skip")
        if conflict_strategy not in ("skip", "update", "raise"):
            errors.append(
                f"Invalid conflict_strategy: {conflict_strategy}. Must be: skip, update, raise"
            )

        return (len(errors) == 0, errors)

    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute database upload.

        Args:
            step_config: Step configuration with database_url OR individual components
            verbose: Enable verbose output
            dry_run: Validate without uploading
            debug: Enable debug logging

        Returns:
            Dictionary with upload results
        """
        # Load environment variables from .env file
        load_dotenv()

        # Parse configuration and build database_url
        database_url = self._get_database_url(step_config)
        if not database_url:
            return {
                "status": StepStatus.ERROR,
                "message": "Could not construct database URL from configuration",
                "error": "Missing database_url or incomplete component parameters",
                "count": 0,
            }

        conflict_strategy = step_config.get("conflict_strategy", "skip")
        batch_size = int(step_config.get("batch_size", 100))
        verbose_conflicts = step_config.get("verbose_conflicts", False)

        if verbose:
            console.print(f"[cyan]Uploading papers to PostgreSQL[/cyan]")
            console.print(
                f"[dim]Database: {database_url.split('@')[-1] if '@' in database_url else 'unknown'}[/dim]"
            )
            console.print(
                f"[dim]Conflict strategy: {conflict_strategy}[/dim]"
            )
            console.print(
                f"[dim]Dry-run: {dry_run}[/dim]"
            )

        try:
            # Get papers from in-memory database
            papers = self.db.all(primary_only=False)
            total_papers = len(papers)

            if total_papers == 0:
                return {
                    "status": StepStatus.WARNING,
                    "message": "No papers in database to upload",
                    "count": 0,
                }

            if verbose:
                console.print(
                    f"[cyan]Found {total_papers} papers to upload[/cyan]"
                )

            # Dry-run mode: just validate conversion
            if dry_run:
                errors = self._validate_papers(papers, verbose)
                if errors:
                    return {
                        "status": StepStatus.WARNING,
                        "message": f"Validation errors in {len(errors)} papers",
                        "count": total_papers,
                        "errors": errors[:10],  # Show first 10 errors
                        "total_errors": len(errors),
                    }
                return {
                    "status": StepStatus.SUCCESS,
                    "message": f"Dry-run: validated {total_papers} papers (no upload)",
                    "count": total_papers,
                    "details": {
                        "mode": "dry-run",
                        "validation": "passed",
                    }
                }

            # Real execution: connect and upload
            pool = DatabaseConnectionPool(database_url)
            pool.initialize()

            try:
                uploader = PaperUploader(pool)

                # Upload papers in batches
                all_stats = {
                    "inserted": 0,
                    "updated": 0,
                    "skipped": 0,
                    "errors": [],
                    "error_count": 0,
                }

                for i in range(0, total_papers, batch_size):
                    batch = papers[i : i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (total_papers + batch_size - 1) // batch_size

                    if verbose:
                        console.print(
                            f"[cyan]Uploading batch {batch_num}/{total_batches} "
                            f"({len(batch)} papers)[/cyan]"
                        )

                    # Upload batch
                    stats = uploader.insert_papers(
                        batch,
                        conflict_strategy=conflict_strategy,
                        dry_run=False,
                    )

                    # Aggregate stats
                    all_stats["inserted"] += stats["inserted"]
                    all_stats["updated"] += stats["updated"]
                    all_stats["skipped"] += stats["skipped"]
                    all_stats["error_count"] += stats["error_count"]
                    all_stats["errors"].extend(stats["errors"])

                    if verbose and stats["error_count"] > 0:
                        console.print(
                            f"[yellow]Batch {batch_num}: "
                            f"{stats['error_count']} errors[/yellow]"
                        )

                # Build result
                result = {
                    "status": StepStatus.SUCCESS if all_stats["error_count"] == 0 else StepStatus.WARNING,
                    "message": self._build_message(all_stats, conflict_strategy),
                    "count": all_stats["inserted"] + all_stats["updated"],
                    "details": {
                        "total_papers": total_papers,
                        "inserted": all_stats["inserted"],
                        "updated": all_stats["updated"],
                        "skipped": all_stats["skipped"],
                        "errors": all_stats["error_count"],
                        "conflict_strategy": conflict_strategy,
                    }
                }

                # Add error details if requested and errors exist
                if verbose_conflicts and all_stats["errors"]:
                    result["error_samples"] = all_stats["errors"][:5]
                    result["total_error_count"] = all_stats["error_count"]

                if all_stats["error_count"] > 0 and all_stats["error_count"] == total_papers:
                    # All papers failed
                    result["status"] = StepStatus.ERROR
                    result["error"] = "All papers failed to upload"

                return result

            finally:
                pool.close()

        except Exception as e:
            error_msg = str(e)
            if debug:
                raise

            return {
                "status": StepStatus.ERROR,
                "message": f"Database upload failed: {error_msg}",
                "error": error_msg,
                "count": 0,
            }

    def _validate_papers(self, papers: List, verbose: bool = False) -> List[str]:
        """
        Validate that papers can be converted to SQL rows.

        Args:
            papers: List of Paper models
            verbose: Enable verbose output

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []

        for i, paper in enumerate(papers):
            try:
                # Try to convert to SQL row
                PaperToRowConverter.paper_to_row(paper)
            except Exception as e:
                error_msg = f"Paper {i} ({paper.cite_key}): {str(e)}"
                errors.append(error_msg)
                if verbose:
                    console.print(
                        f"[red]Validation error: {error_msg}[/red]"
                    )

        return errors

    def _build_message(self, stats: Dict[str, Any], strategy: str) -> str:
        """Build human-readable summary message"""
        parts = []

        if stats["inserted"] > 0:
            parts.append(f"inserted {stats['inserted']}")

        if stats["updated"] > 0:
            parts.append(f"updated {stats['updated']}")

        if stats["skipped"] > 0:
            parts.append(f"skipped {stats['skipped']}")

        if stats["error_count"] > 0:
            parts.append(f"errors: {stats['error_count']}")

        summary = ", ".join(parts) if parts else "no changes"
        return f"Upload complete: {summary} (strategy: {strategy})"

    def _get_database_url(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Construct or retrieve database URL from configuration.

        Supports two modes:
        1. Direct: database_url parameter (with optional env var substitution)
        2. Components: db_username, db_password, db_host, db_port, db_name

        Environment variable values are loaded via dotenv.

        Args:
            config: Step configuration

        Returns:
            Full PostgreSQL connection string or None if invalid
        """
        # Mode 1: Direct database_url
        if "database_url" in config:
            database_url = config.get("database_url", "")

            # Handle environment variable reference
            if database_url.startswith("$"):
                env_var = database_url[1:]
                database_url = os.environ.get(env_var)
                if not database_url:
                    return None

            return database_url

        # Mode 2: Build from components
        username = self._resolve_env_var(config.get("db_username"))
        password = self._resolve_env_var(config.get("db_password"))
        host = self._resolve_env_var(config.get("db_host"))
        port = self._resolve_env_var(config.get("db_port"))
        db_name = self._resolve_env_var(config.get("db_name"))

        if not all([username, password, host, port, db_name]):
            return None

        # Build URL
        database_url = f"postgresql://{username}:{password}@{host}:{port}/{db_name}"
        return database_url

    @staticmethod
    def _resolve_env_var(value: Optional[str]) -> Optional[str]:
        """
        Resolve value as either literal or environment variable reference.

        Args:
            value: Either a literal value or "$ENV_VAR_NAME"

        Returns:
            Resolved value or None if not found
        """
        if not value:
            return None

        if value.startswith("$"):
            env_var = value[1:]
            resolved = os.environ.get(env_var)
            return resolved

        return value
