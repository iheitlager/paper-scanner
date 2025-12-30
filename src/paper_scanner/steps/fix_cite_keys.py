"""
Fix cite keys step for paper scanner

Recreates citation keys for all primary papers in the format 'LastnameYear'.
Handles collisions by appending characters (a, b, c, ..., z, aa, ab, ...).
Only processes primary papers (excluding duplicates).
"""

import sys
from typing import Any, Dict, List, Tuple

from rich.console import Console

from paper_scanner.core.cite_key import generate_cite_key, make_collision_suffix
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.step_result import StepResult

from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


class FixCiteKeysStep(BaseStep):
    """Step that regenerates cite keys for all primary papers."""

    @staticmethod
    def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate fix_cite_keys step configuration.

        Args:
            config: Step configuration (optional, has no required fields)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        # No configuration required
        return True, []

    def execute(
        self,
        config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> StepResult:
        """
        Execute fix cite keys step.

        Recreates citation keys for all primary papers in format 'LastnameYear'.
        Updates papers in the database.

        Args:
            config: Step configuration (unused)
            verbose: Enable verbose output
            dry_run: Don't actually update papers
            debug: Enable debug output

        Returns:
            StepResult with status, count of updated/skipped papers, and any errors
        """
        # Track results
        updated_papers = []
        skipped_papers = []
        error_messages = []

        # Get all primary papers (duplicate_of is None)
        primary_papers = self.db.all(primary_only=True)

        # Track all existing cite_keys for collision detection
        used_keys = {paper.cite_key for paper in primary_papers}

        # First pass: generate new keys and detect collisions
        new_keys_map = {}  # paper.id -> new_cite_key

        for paper in primary_papers:
            try:
                # Generate base key
                base_key = generate_cite_key(paper)

                # Resolve collisions with newly generated keys in this batch
                new_key = base_key
                collision_count = 0

                while new_key in used_keys and new_key != paper.cite_key:
                    suffix = make_collision_suffix(collision_count)
                    new_key = f"{base_key}{suffix}"
                    collision_count += 1

                # Track the new key
                if new_key != paper.cite_key:
                    # Check if this new key was already assigned to another paper
                    if new_key in new_keys_map.values():
                        # Collision with another paper in this batch
                        # Find unused key
                        collision_index = 0
                        while True:
                            suffix = make_collision_suffix(collision_index)
                            candidate = f"{base_key}{suffix}"
                            if candidate not in used_keys and candidate not in new_keys_map.values():
                                new_key = candidate
                                break
                            collision_index += 1

                    new_keys_map[paper.id] = new_key
                    updated_papers.append(paper.id)
                    self.callback(f"{paper.cite_key} -> {new_key}", debug=True)
                else:
                    skipped_papers.append(paper.id)

                # Add new key to used_keys set
                if new_key not in used_keys:
                    used_keys.add(new_key)

            except ValueError as e:
                error_messages.append(str(e))
                skipped_papers.append(paper.id)

        # Second pass: update papers in database (fatal if DB write fails)
        if not dry_run and new_keys_map:
            for paper in primary_papers:
                if paper.id in new_keys_map:
                    new_key = new_keys_map[paper.id]
                    # Create updated paper with new cite_key
                    updated_paper = paper.model_copy(update={"cite_key": new_key})
                    self.db.update(updated_paper)


        # Determine final status
        total_papers = len(primary_papers)
        errors_count = len(error_messages)

        if errors_count > 0:
            status = StepStatus.WARNING if len(updated_papers) > 0 else StepStatus.ERROR
            message = f"Fixed {len(updated_papers)} cite keys but {errors_count} error(s) occurred"
            details = ["Errors:\n" + "\n".join(f"  - {err}" for err in error_messages)]
        else:
            status = StepStatus.SUCCESS
            message = f"Fixed {len(updated_papers)} cite keys out of {total_papers} papers"
            details = None

        return StepResult(
            status=status,
            message=message,
            stats={
                "count": total_papers,
                "updated": len(updated_papers),
                "skipped": len(skipped_papers),
                "errors": errors_count,
                "papers_count": self.db.count(),
            },
            details=details
        )
