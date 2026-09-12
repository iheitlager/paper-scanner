"""
Download PDFs step for paper scanner.

Downloads PDF files for papers where PDFInfo is None or file_path is None/empty.
Supports multiple sources (unpaywall, crossref) with retry logic and error handling.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.doi import DOI
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import PDFInfo
from paper_scanner.core.step_result import StepResult
from paper_scanner.tools.fetchers.fetcher import Fetcher

from .base import BaseStep

VALID_SOURCES = {"crossref", "openalex", "core", "publisher"}
VALID_FLAGS = {"true", "false", "only", "all", "no"}


class DownloadPDFsStep(BaseStep):
    """Download PDF files for papers from various sources."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate download_pdfs step configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate timeout
        if "timeout" in config:
            timeout = config["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append("'timeout' must be a positive number")

        # Validate store_path
        if "store_path" not in config:
            errors.append("'store_path' is required")
        elif not isinstance(config["store_path"], str):
            errors.append("'store_path' must be a string")

        # Validate sources
        if "sources" in config:
            sources = config["sources"]
            if not isinstance(sources, list):
                errors.append("'sources' must be a list")
            elif not sources:
                errors.append("'sources' list cannot be empty")
            else:
                invalid_sources = [s for s in sources if s not in VALID_SOURCES]
                if invalid_sources:
                    errors.append(
                        f"Invalid sources: {invalid_sources}. Valid: {VALID_SOURCES}"
                    )
        else:
            errors.append("'sources' is required")

        if "includes" in config:
            c = config["includes"]
            if c not in VALID_FLAGS:
                errors.append(f"'includes' must be one of {VALID_FLAGS}, got {c}")

        # Validate output_errors (optional)
        if "output_errors" in config:
            if not isinstance(config["output_errors"], str):
                errors.append("'output_errors' must be a string")

        return len(errors) == 0, errors

    @staticmethod
    def _translate_flag(flag: Any) -> Optional[bool]:
        """Translate boolean flag to string representation."""
        if flag in ["only", "true", True]:
            return True
        elif flag in ["no", "false", False]:
            return False
        return None

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute PDF download step.

        Downloads PDFs for papers with missing PDFInfo or file_path.
        Tries sources in order with retry logic.

        Args:
            config: Step configuration
            verbose: Enable verbose output
            dry_run: Don't actually download files
            debug: Enable debug output

        Returns:
            Dictionary with execution results
        """
        # Parse configuration
        timeout = config.get("timeout", 30)
        store_path = Path(config["store_path"]).expanduser()
        sources = config.get("sources", ["crossref"])
        output_errors = config.get("output_errors")
        includes_flag = self._translate_flag(config.get("includes", "only")) # 'only', 'all', 'none'

        # Create store directory
        store_path.mkdir(parents=True, exist_ok=True)

        # Initialize Fetcher with specified sources
        fetcher = Fetcher(
            cache_dir=self.cache_dir,
            methods=sources,
        )

        # Get papers from in-memory database
        def predicate(p) -> bool:
            """Predicate to filter papers based on DOI flag."""
            if  p.pdf_info is not None and p.pdf_info.file_path:
                return False
            c = True
            if includes_flag == True:
                # export only papers that were included
                c &= p.is_included is True
            elif includes_flag == False:
                # export only papers that were excluded
                c &= p.is_included is False
            # else export all papers

            return c

        papers = self.db.find(predicate, primary_only=True)

        if not papers:
            return StepResult(
                status=StepStatus.SUCCESS,
                stats={
                    "count": 0,
                    "papers_total": self.db.count(primary_only=True),
                    "skipped": self.db.count(primary_only=True),
                    "errors": 0,
                },
                message="No papers needing PDF downloads",
            )

        # Download PDFs with progress
        downloaded = 0
        skipped = 0
        errors = []
        error_details = []

        for paper in papers:
            try:
                # Skip if no DOI
                if not paper.doi:
                    skipped += 1
                    continue

                # Try to download PDF
                pdf_info = fetcher.fetch_pdf(paper.doi, timeout=timeout)

                if pdf_info and pdf_info.file_path:
                    pdf_path = Path(pdf_info.file_path)
                    # Move to store directory
                    if not dry_run:
                        dest_name = f"{DOI(paper.doi).safe}.pdf"
                        dest_path = store_path / dest_name
                        shutil.copy2(pdf_path, dest_path)

                        # Update paper with PDF info from fetcher
                        # (preserves handler_name as download_source)
                        paper.pdf_info = PDFInfo(
                            file_path=str(dest_path),
                            file_size_bytes=dest_path.stat().st_size,
                            download_source=pdf_info.download_source,
                            download_url=pdf_info.download_url,
                        )

                    downloaded += 1

                else:
                    skipped += 1

            except Exception as e:
                errors.append(str(e))
                error_details.append({
                    "paper": paper.cite_key,
                    "doi": paper.doi,
                    "error": str(e),
                })

        # Write error log if requested
        if output_errors and error_details:
            error_path = Path(output_errors).expanduser()
            error_path.parent.mkdir(parents=True, exist_ok=True)
            with open(error_path, "w") as f:
                for detail in error_details:
                    f.write(json.dumps(detail) + "\n")

        return StepResult(
            status=StepStatus.SUCCESS if not error_details else StepStatus.ERROR,
            stats = {
                "count": downloaded,
                "papers_total": self.db.count(primary_only=True),
                "skipped": skipped,
                "errors": len(error_details),
            },
            error= "\n".join(detail["error"] for detail in error_details) if error_details else None, 
            details = { 
                "store_path":str(store_path),
                "sources":sources
            },
            message=f"Downloaded {downloaded} PDFs, skipped {skipped}",
        )
