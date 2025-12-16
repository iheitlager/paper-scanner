"""
Paper step - create Paper objects from DOI specifications.

Accepts an array of paper specifications with required DOI and optional
cite_key, paper_type, and study_type fields. Auto-generates cite_key from
DOI MD5 hash if not provided.
"""

import sys
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from rich.console import Console
from pathlib import Path

from paper_scanner.core.models import Paper, Discovery
from paper_scanner.core.enum import PaperType, StudyType, DiscoveryMethod
from paper_scanner.core.doi import DOI
from paper_scanner.core.database import PapersDatabase
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


class PaperStep(BaseStep):
    """Create Paper objects from DOI specifications."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate paper step configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Must have 'papers' key
        if "papers" not in config:
            errors.append("'papers' key is required")
            return False, errors

        papers_config = config["papers"]

        # Must be a list
        if not isinstance(papers_config, list):
            errors.append("'papers' must be a list of paper specifications")
            return False, errors

        # Must have at least one paper
        if len(papers_config) == 0:
            errors.append("'papers' list cannot be empty")
            return False, errors

        # Validate each paper specification
        for idx, paper_spec in enumerate(papers_config):
            if not isinstance(paper_spec, dict):
                errors.append(f"Paper {idx}: specification must be a dictionary")
                continue

            # Check required 'doi' field
            if "doi" not in paper_spec:
                errors.append(f"Paper {idx}: 'doi' is required")
                continue

            doi_str = paper_spec["doi"]
            if not isinstance(doi_str, str):
                errors.append(f"Paper {idx}: 'doi' must be a string")
                continue

            # Validate DOI format
            try:
                DOI(doi_str)
            except ValueError as e:
                errors.append(f"Paper {idx}: Invalid DOI - {str(e)}")

            # Validate optional cite_key (must be string)
            if "cite_key" in paper_spec and not isinstance(paper_spec["cite_key"], str):
                errors.append(f"Paper {idx}: 'cite_key' must be a string")

            # Validate optional paper_type (must be valid enum value)
            if "paper_type" in paper_spec:
                paper_type_val = paper_spec["paper_type"]
                if not isinstance(paper_type_val, str):
                    errors.append(f"Paper {idx}: 'paper_type' must be a string (enum value)")
                else:
                    try:
                        PaperType(paper_type_val)
                    except ValueError:
                        errors.append(
                            f"Paper {idx}: 'paper_type' '{paper_type_val}' is not a valid PaperType"
                        )

            # Validate optional study_type (must be valid enum value)
            if "study_type" in paper_spec:
                study_type_val = paper_spec["study_type"]
                if not isinstance(study_type_val, str):
                    errors.append(f"Paper {idx}: 'study_type' must be a string (enum value)")
                else:
                    try:
                        StudyType(study_type_val)
                    except ValueError:
                        errors.append(
                            f"Paper {idx}: 'study_type' '{study_type_val}' is not a valid StudyType"
                        )

        return len(errors) == 0, errors

    def execute(
        self,
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute paper step - create Paper objects from specifications.

        Args:
            step_config: Step configuration with 'papers' array
            verbose: Enable verbose output
            dry_run: If True, don't persist papers to database
            debug: Enable debug output

        Returns:
            Execution result with created papers
        """
        papers_config = step_config.get("papers", [])
        created_papers: List[Paper] = []
        errors: List[str] = []

        try:
            for idx, paper_spec in enumerate(papers_config):
                try:
                    # Extract fields
                    doi_str = paper_spec["doi"]
                    cite_key = paper_spec.get("cite_key")
                    paper_type_str = paper_spec.get("paper_type")
                    study_type_str = paper_spec.get("study_type")

                    # Validate and normalize DOI
                    doi_obj = DOI(doi_str)
                    normalized_doi = doi_obj.stem

                    # Generate cite_key if not provided
                    if not cite_key:
                        cite_key = f"doi_{doi_obj.md5[:8]}"

                    # Parse optional paper_type
                    paper_type = None
                    if paper_type_str:
                        paper_type = PaperType(paper_type_str)

                    # Parse optional study_type (for future use)
                    study_type = None
                    if study_type_str:
                        study_type = StudyType(study_type_str)

                    # Create Paper object
                    paper = Paper(
                        cite_key=cite_key,
                        doi=normalized_doi,
                        paper_type=paper_type,
                        discovery=Discovery(method=DiscoveryMethod.MANUAL),
                    )

                    # Note: screening.categorization left as None for later enhancement by analysis steps
                    # If study_type was provided, caller can enhance categorization later

                    created_papers.append(paper)

                    if verbose:
                        console.print(
                            f"  [green]✓[/green] Paper {idx + 1}: {cite_key} ({normalized_doi})"
                        )

                except Exception as e:
                    error_msg = f"Paper {idx}: {str(e)}"
                    errors.append(error_msg)
                    if debug:
                        raise

            # Persist papers to database if not dry_run
            if not dry_run:
                for paper in created_papers:
                    self.db.add(paper)

            result = {
                "status": "success" if not errors else "partial",
                "count": len(created_papers),
                "papers": [p.id for p in created_papers],
            }

            if errors:
                result["errors"] = errors

            console.print(f"[bold green]Created {len(created_papers)} paper(s)[/bold green]")

            if errors and verbose:
                console.print(f"[yellow]Errors: {len(errors)}[/yellow]")
                for error in errors:
                    console.print(f"  [red]✗[/red] {error}")

            return result

        except Exception as e:
            error_msg = str(e)
            if debug:
                raise
            return {
                "status": "error",
                "count": 0,
                "error": error_msg,
            }
