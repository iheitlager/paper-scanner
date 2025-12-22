"""
Fix cite keys step for paper scanner

Recreates citation keys for all primary papers in the format 'LastnameYear'.
Handles collisions by appending characters (a, b, c, ..., z, aa, ab, ...).
Only processes primary papers (excluding duplicates).
"""

import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from paper_scanner.core.enum import StepStatus
from paper_scanner.core.models import Paper
from .base import BaseStep

# Initialize rich console
console = Console(file=sys.stderr)


def _generate_cite_key(paper: Paper) -> str:
    """
    Generate a citation key in format 'LastnameYear' for a paper.
    
    Args:
        paper: Paper to generate cite_key for
        
    Returns:
        Citation key base (without collision suffix)
        
    Raises:
        ValueError: If paper lacks necessary data (authors or year)
    """
    if not paper.authors:
        raise ValueError(f"Paper {paper.id} has no authors")
    
    if not paper.year:
        raise ValueError(f"Paper {paper.id} has no publication year")
    
    # Get first author's last name
    first_author = paper.authors[0]
    last_name = first_author.family_name.replace(" ", "").replace("-", "")
    
    if not last_name:
        raise ValueError(f"Paper {paper.id} first author has no family name")
    
    # Format: LastnameYear
    base_key = f"{last_name}{paper.year}"
    return base_key


def _make_collision_suffix(index: int) -> str:
    """
    Generate a collision suffix for cite key.
    
    Follows pattern: a, b, c, ..., z, aa, ab, ..., az, ba, ...
    
    Args:
        index: Collision index (0-based, 0 -> "a", 26 -> "aa", etc.)
        
    Returns:
        Suffix string
    """
    if index < 26:
        # Single letter: a-z
        return chr(ord('a') + index)
    else:
        # Multiple letters: aa, ab, ac, ...
        # Convert to base-26, similar to Excel column naming
        suffix = ""
        num = index - 26
        while True:
            suffix = chr(ord('a') + (num % 26)) + suffix
            num = num // 26
            if num == 0:
                break
            num -= 1
        # Prepend 'a' for multi-letter suffixes starting from 'aa'
        return 'a' + suffix


def _resolve_collision(base_key: str, existing_keys: dict) -> str:
    """
    Resolve collision by appending suffix.
    
    Args:
        base_key: Base citation key (without suffix)
        existing_keys: Dict mapping cite_key -> True for existing keys
        
    Returns:
        Unique citation key
    """
    if base_key not in existing_keys:
        return base_key
    
    # Try appending suffixes
    collision_index = 0
    while True:
        suffix = _make_collision_suffix(collision_index)
        candidate_key = f"{base_key}{suffix}"
        
        if candidate_key not in existing_keys:
            return candidate_key
        
        collision_index += 1


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
        step_config: Dict[str, Any],
        verbose: bool = False,
        dry_run: bool = False,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute fix cite keys step.
        
        Recreates citation keys for all primary papers in format 'LastnameYear'.
        Updates papers in the database.
        
        Args:
            step_config: Step configuration (unused)
            verbose: Enable verbose output
            dry_run: Don't actually update papers
            debug: Enable debug output
            
        Returns:
            Result dictionary with status, count, and errors
        """
        if verbose:
            console.print("[bold cyan]Fixing citation keys...[/bold cyan]")
        
        # Track results
        updated_papers = []
        skipped_papers = []
        errors = []
        
        # Get all primary papers (duplicate_of is None)
        primary_papers = self.db.all(primary_only=True)
        
        if verbose:
            console.print(f"Processing {len(primary_papers)} primary papers")
        
        # Track all existing cite_keys for collision detection
        used_keys = {paper.cite_key for paper in primary_papers}
        
        # First pass: generate new keys and detect collisions
        new_keys_map = {}  # paper.id -> new_cite_key
        
        for paper in primary_papers:
            try:
                # Generate base key
                base_key = _generate_cite_key(paper)
                
                # Resolve collisions with newly generated keys in this batch
                new_key = base_key
                collision_count = 0
                
                while new_key in used_keys and new_key != paper.cite_key:
                    suffix = _make_collision_suffix(collision_count)
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
                            suffix = _make_collision_suffix(collision_index)
                            candidate = f"{base_key}{suffix}"
                            if candidate not in used_keys and candidate not in new_keys_map.values():
                                new_key = candidate
                                break
                            collision_index += 1
                    
                    new_keys_map[paper.id] = new_key
                    updated_papers.append(paper.id)
                    if debug:
                        console.print(f"[dim]{paper.cite_key} -> {new_key}[/dim]")
                else:
                    skipped_papers.append(paper.id)
                
                # Add new key to used_keys set
                if new_key not in used_keys:
                    used_keys.add(new_key)
                
            except ValueError as e:
                errors.append(str(e))
                skipped_papers.append(paper.id)
        
        # Second pass: update papers in database
        if not dry_run and new_keys_map:
            for paper in primary_papers:
                if paper.id in new_keys_map:
                    new_key = new_keys_map[paper.id]
                    # Create updated paper with new cite_key
                    updated_paper = paper.model_copy(update={"cite_key": new_key})
                    self.db.update(updated_paper)
            
            if verbose:
                console.print(f"[green]Updated {len(new_keys_map)} papers[/green]")
        
        if verbose:
            if skipped_papers:
                console.print(f"[yellow]Skipped {len(skipped_papers)} papers[/yellow]")
            if errors:
                console.print(f"[red]{len(errors)} errors[/red]")
        
        # Return results
        return {
            "status": "success" if not errors else "warning",
            "step": "fix_cite_keys",
            "count": len(updated_papers),
            "skipped": len(skipped_papers),
            "errors": errors,
            "papers_count": self.db.count(),
        }
