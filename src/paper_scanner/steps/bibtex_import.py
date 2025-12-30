"""
BibTeX import step for paper scanner

Sequentially imports BibTeX files and adds papers to the database
"""

import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..core.database import PapersDatabase
from ..core.enum import DiscoveryMethod, StepStatus
from ..core.models import Paper
from ..core.step_result import StepResult
from ..core.exceptions import ConfigurationError
from ..io.bibtex import bibtex_file_to_papers, load_type_mapping_config
from .base import BaseStep

# Valid source types
VALID_SOURCE_TYPES = {"scopus", "web_of_science", "ieee_xplore", "other"}


def _fix_cite_key_collisions(papers: List[Paper], existing_db: PapersDatabase) -> int:
    """
    Fix cite_key collisions by adding _XX suffix to duplicates.

    For each paper with a cite_key that collides with existing entries in the database
    or with other papers in the import, add a _XX suffix where XX is a decimal number
    starting from 01 and incrementing until the key is unique.

    Args:
        papers: List of papers to fix
        existing_db: Existing papers database to check against

    Returns:
        Number of cite_keys that were fixed (had collisions)
    """
    seen_keys = set()
    fixed_count = 0

    for paper in papers:
        original_key = paper.cite_key
        unique_key = original_key
        counter = 1

        # Check if the key already exists in the database or was already processed
        while existing_db.get_by_cite_key(unique_key) is not None or unique_key in seen_keys:
            unique_key = f"{original_key}_{counter:02d}"
            counter += 1

        # If the key was changed, increment fixed count
        if unique_key != original_key:
            fixed_count += 1

        paper.cite_key = unique_key
        seen_keys.add(unique_key)

    return fixed_count


class BibtexImportStep(BaseStep):
    """BibTeX import step for adding papers from BibTeX files."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate bibtex_import step configuration.

        Args:
            config: Step configuration

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        for key in config.keys():
            if key == "limit":
                limit = config["limit"]
                if not isinstance(limit, int) or limit <= 0:
                    errors.append("'limit' must be a positive integer")
            elif key == "randomize":
                randomize = config["randomize"]
                if not isinstance(randomize, bool):
                    errors.append("'randomize' must be a boolean")
            elif key == "random_seed":
                seed = config["random_seed"]
                if not isinstance(seed, int):
                    errors.append("'random_seed' must be an integer")
            elif key == "file_path":
                file_path = config["file_path"]
                if not isinstance(file_path, str):
                    errors.append("'file_path' must be a string")
            elif key == "source_type":
                source_type = config["source_type"]
                if source_type not in VALID_SOURCE_TYPES:
                    errors.append(f"'source_type' must be one of {VALID_SOURCE_TYPES}, got '{source_type}'")
            elif key == "expected_count":
                expected = config["expected_count"]
                if not isinstance(expected, int) or expected < 0:
                    errors.append("'expected_count' must be a non-negative integer")
            elif key == "fix_cite_key":
                fix_cite_key = config["fix_cite_key"]
                if not isinstance(fix_cite_key, bool):
                    errors.append("'fix_cite_key' must be a boolean")
            elif key == "type_mapping_config_path":
                if not isinstance(config["type_mapping_config_path"], str):
                    errors.append("'type_mapping_config_path' must be a string")
            else:
                errors.append(f"Unknown configuration key: '{key}'")

        if 'file_path' not in config:
            errors.append("missing required 'file_path' in configuration")
        return len(errors) == 0, errors


    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False
    ) -> StepResult:
        """
        Execute BibTeX import step

        Args:
            config: Step configuration (includes batch_id and imports list)
            verbose: Enable verbose output
            dry_run: Don't actually import, just show what would happen
            debug: Enable debug output

        Returns:
            StepResult with execution status and statistics

        Raises:
            StepFatalError: If type mapping config cannot be loaded, or BibTeX parsing fails
        """
        randomize = config.get("randomize", False)
        random_seed = config.get("random_seed", None)
        limit = config.get("limit", None)
        type_mapping_config_path = config.get("type_mapping_config_path")
        file_path = config.get("file_path")
        source_type = config.get("source_type", "manual")
        expected_count = config.get("expected_count")
        fix_cite_key = config.get("fix_cite_key", False)

        # Track statistics
        details = []
        fixed_count = 0

        # Load type mapping configuration (fatal if fails)
        type_mapping_config = None
        if type_mapping_config_path:
            self.callback(f"Loading type mapping config from: {type_mapping_config_path}", debug=True)
            type_mapping_config = load_type_mapping_config(type_mapping_config_path)
        else:
            # Use default location
            self.callback("Using default type mapping configuration", debug=True)
            type_mapping_config = load_type_mapping_config()

        # Process each import

        # Validate file exists and is readable
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise ConfigurationError(f"File not found or not a file: {file_path}")

        # Parse BibTeX file - fatal if parsing fails
        papers = bibtex_file_to_papers(
            str(path),
            source_type=source_type,
            discovery_method=DiscoveryMethod.KEYWORD_SEARCH,
            type_mapping_config=type_mapping_config
        )

        # Apply limit after randomization
        if limit:
            if randomize:
                if random_seed is not None:
                    random.seed(random_seed)
                random.shuffle(papers)
                details.append(f"Randomized papers (seed={random_seed})" if random_seed is not None else "Randomized papers")
            papers = papers[:limit]

        # Fix cite_key collisions if requested
        if fix_cite_key:
            fixed_count = _fix_cite_key_collisions(papers, self.db)

        count = len(papers)
        if dry_run:
            self.callback(f"[yellow][DRY RUN][/yellow] Would import {count} papers", debug=True)
        else:
            # Add to database - fatal if write fails
            self.db.add_many(papers)

        if expected_count:
            self.callback(f"Expected: {expected_count}, Would get: {count}", debug=True)

        # All files processed successfully
        status = StepStatus.SUCCESS
        message = f"Imported {count} papers from {file_path}"
        if fixed_count > 0:
            message += f" ({fixed_count} cite_key collisions fixed)"

        return StepResult(
            status=status,
            message=message,
            stats={
                "count": count,
            },
            details=details
        )
