"""
Citation key generation and collision resolution utilities.

Provides functions to generate BibTeX-style citation keys in the format
'LastnameYear' with automatic collision handling.
"""

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
