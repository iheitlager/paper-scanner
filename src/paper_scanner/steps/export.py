"""
Database output step for paper scanner

Exports papers database to various formats (JSONL, BibTeX)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import ConfigurationError
from paper_scanner.core.step_result import StepResult

from ..io.bibtex import papers_to_bibtex
from ..io.json import papers_to_jsonl
from .base import BaseStep

VALID_FORMATS = {"json", "jsonl", "bibtex"}
VALID_FLAGS = {"true", "false", "only", "all", "no"}


class ExportStep(BaseStep):
    """Export papers database to various formats."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate export step configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check format
        if "format" in config:
            fmt = config["format"]
            if fmt.lower() not in VALID_FORMATS:
                errors.append(f"'format' must be one of {VALID_FORMATS}, got '{fmt}'")

        # Check output (new parameter) or output_path (legacy)
        has_output = "output" in config
        has_output_path = "output_path" in config

        if not has_output and not has_output_path:
            errors.append("Either 'output' or 'output_path' is required")
        elif has_output:
            if not isinstance(config["output"], str):
                errors.append("'output' must be a string")
            elif config["output"] != "stdout" and not config["output"]:
                errors.append("'output' must be either 'stdout' or a file path")
        elif has_output_path:
            if not isinstance(config["output_path"], str):
                errors.append("'output_path' must be a string")

        # Check boolean fields
        if "exclude_none" in config and not isinstance(config["exclude_none"], bool):
            errors.append("'exclude_none' must be a boolean")
        if "overwrite" in config and not isinstance(config["overwrite"], bool):
            errors.append("'overwrite' must be a boolean")

        # Check flag options
        if "doi" in config:
            c = config["doi"]
            if c not in VALID_FLAGS:
                errors.append(f"'doi' must be one of {VALID_FLAGS}, got {c}")
        if "duplicates" in config:
            c = config["duplicates"]
            if c not in VALID_FLAGS:
                errors.append(f"'duplicates' must be one of {VALID_FLAGS}, got {c}")
        if "includes" in config:
            c = config["includes"]
            if c not in VALID_FLAGS:
                errors.append(f"'includes' must be one of {VALID_FLAGS}, got {c}")

        return len(errors) == 0, errors

    @staticmethod
    def _translate_flag(flag: Any) -> str:
        """Translate boolean flag to string representation."""
        if isinstance(flag, bool):
            return "true" if flag else "false"
        return str(flag).lower()

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Execute database export step

        Args:
            config: Step configuration (includes format and output/output_path)
            verbose: Enable verbose output
            dry_run: Don't actually write files
            debug: Enable debug output

        Returns:
            Dictionary with execution results
        """

        self.output_format = config.get("format", "jsonl").lower()
        self.exclude_none = config.get("exclude_none", True)
        self.overwrite = config.get("overwrite", False)  # Default to False - fail on existing files

        # Support both 'output' (new) and 'output_path' (legacy)
        output_target = config.get("output") or config.get("output_path")
        self.is_stdout = output_target == "stdout"

        duplicates_flag = self._translate_flag(config.get("duplicates", "no"))  # false, true, or "only"
        includes_flag = self._translate_flag(config.get("includes", "only")) # 'only', 'all', 'none'
        doi_flag = self._translate_flag(config.get("doi", "only"))  # 'only', 'true', 'false', 'none'

        if not output_target:
            raise ConfigurationError("Either 'output' or 'output_path' is required")
        if self.output_format not in ("jsonl", "bibtex", "json"):
            raise ConfigurationError(f"Unsupported format: {self.output_format}. Supported: jsonl, json, bibtex")

        # Expand tilde and resolve the path (only if not stdout)
        output_path = None
        if output_target and not self.is_stdout:
            self.output_path = str(Path(output_target).expanduser().resolve())
            # Create output directory if needed (only for file output)
            if not self.is_stdout and self.output_path:
                path = Path(self.output_path)
                path.parent.mkdir(parents=True, exist_ok=True)

                # Check if file exists and overwrite is False
                if path.exists() and not self.overwrite:
                    raise ConfigurationError(f"File already exists and overwrite=False: {self.output_path}")

        def predicate(p) -> bool:
            """Predicate to filter papers based on DOI flag."""
            c = True
            if doi_flag in ["only", "true", True]:
                # export if doi is set or 'only' if doi is set
                c &= p.doi is not None
            elif doi_flag in ["false", False]:
                # export if doi is not set
                c &= p.doi is None
            # else do not care about doi

            if duplicates_flag in ["only", "true", True]:
                # export only duplicates
                c &= p.duplicate_of is not None
            elif duplicates_flag == ["no", "false", False]:
                # export only unique papers (default)
                c &= p.duplicate_of is None
            # else do not care

            if includes_flag in ["only", "true", True]:
                # export only papers that were included
                c &= p.is_included is True
            elif includes_flag == ["no", "false", False]:
                # export only papers that were excluded
                c &= p.is_included is False
            # else export all papers

            return c

        papers_to_export = self.db.find(predicate)

        results = {
            "format": self.output_format,
            "duplicates": duplicates_flag,
            "includes": includes_flag,
            "doi": doi_flag,
            "output_path": "<stdout>" if self.is_stdout else self.output_path,
        }

        stats = {
            "count": len(papers_to_export),
        }

        if not dry_run:
            if self.output_format == "jsonl":
                self._export_to_jsonl(papers_to_export)

            elif self.output_format == "json":
                self._export_json(papers_to_export)

            elif self.output_format == "bibtex":
                self._export_bibtex(papers_to_export)

            message = f"Exported {len(papers_to_export)} papers to {self.output_format} at {output_path or 'stdout'}"
        else:
            message = f"Dry run: would export {len(papers_to_export)} papers to {self.output_format} at {output_path or 'stdout'}"

        return StepResult(
            status=StepStatus.SUCCESS,
            step=self.name,
            message=message,
            stats=stats,
            details=results,
        )


    def _export_bibtex(self, papers: List[Any]) -> None:
        """Export papers to BibTeX file."""

        bibtex_content = papers_to_bibtex(papers)

        if self.is_stdout:
            with Console(file=sys.stdout, force_terminal=True) as console:
                console.print(bibtex_content)
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(bibtex_content)

    def _export_jsonl(self, papers: List[Any]) -> None:
        """Export papers to JSONL file."""

        jsonl_content = papers_to_jsonl(papers, exclude_none=self.exclude_none)

        if self.is_stdout:
            with Console(file=sys.stdout, force_terminal=True) as console:
                console.print(jsonl_content)
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(jsonl_content)

    def _export_json(self, papers: List[Any]) -> None:
        """Export papers to JSON file."""
        papers_dicts = [p.model_dump(mode='json', exclude_none=self.exclude_none) for p in papers]
        json_content = json.dumps(papers_dicts, indent=2, default=str)

        if self.is_stdout:
            with Console(file=sys.stdout, force_terminal=True) as console:
                console.print(json_content)
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
