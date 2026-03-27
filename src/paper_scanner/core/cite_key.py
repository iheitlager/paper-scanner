"""
Citation key generation and collision resolution utilities.

Provides functions to generate BibTeX-style citation keys in the format
'LastnameYear' with automatic collision handling.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from paper_scanner.core.database import PapersDatabase

from paper_scanner.core.doi import DOI
from paper_scanner.core.models import Paper


def generate_cite_key(paper: Paper) -> str:
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


def make_collision_suffix(index: int) -> str:
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


def resolve_collision(base_key: str, existing_keys: dict) -> str:
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
        suffix = make_collision_suffix(collision_index)
        candidate_key = f"{base_key}{suffix}"

        if candidate_key not in existing_keys:
            return candidate_key

        collision_index += 1


def fix_cite_key_collisions(papers: List[Paper], existing_db: "PapersDatabase") -> int:
    """
    Fix cite_key collisions for a list of papers.

    Checks each paper's cite_key against the database and other papers
    in the list. If a collision is detected, appends a suffix (a, b, c, ..., aa, ab, ...)
    until the key is unique.

    Args:
        papers: List of papers to fix cite_keys for
        existing_db: Existing papers database to check against

    Returns:
        Number of cite_keys that were fixed (had collisions)
    """
    # Build dict of existing keys from database
    existing_keys = {}
    for paper in existing_db.papers:
        if paper.cite_key:
            existing_keys[paper.cite_key] = True

    seen_keys = set()
    fixed_count = 0

    for paper in papers:
        original_key = paper.cite_key

        # Use resolve_collision to get unique key
        unique_key = resolve_collision(original_key, {**existing_keys, **{k: True for k in seen_keys}})

        # If the key was changed, increment fixed count
        if unique_key != original_key:
            fixed_count += 1

        paper.cite_key = unique_key
        seen_keys.add(unique_key)

    return fixed_count


def generate_doi_based_cite_key(doi: str) -> str:
    """
    Generate a deterministic cite key from DOI using MD5 hash.

    Deterministic and unique: same DOI always produces same cite_key.
    Falls back to random UUID if no DOI provided.

    Args:
        doi: Digital Object Identifier

    Returns:
        Generated cite key string (e.g., "doi_a1b2c3d4" or UUID-based key)
    """
    import uuid

    if doi:
        # Hash the normalized DOI for reproducibility
        hash_input = DOI(doi).md5
        return "doi_" + hash_input[:8]

    # Fallback: random UUID if no DOI
    return str(uuid.uuid4())[:8]
