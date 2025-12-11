"""
Abstract parser for cleaning up formatted abstracts.

Handles various markup formats (JATS XML, HTML) and extracts clean text.
"""

import re
from typing import Optional


class AbstractParser:
    """
    Parse and clean abstracts with various markup formats.
    
    Handles:
    - JATS XML tags (jats:title, jats:p, etc.)
    - HTML tags (p, div, etc.)
    - Extra whitespace normalization
    """

    @staticmethod
    def clean(abstract: Optional[str]) -> Optional[str]:
        """
        Clean abstract by removing markup and normalizing whitespace.

        Args:
            abstract: Raw abstract text with potential markup

        Returns:
            Cleaned abstract text, or None if input is None/empty
        """
        if not abstract:
            return None

        abstract = abstract.strip()
        if not abstract:
            return None

        # Remove JATS XML tags
        abstract = AbstractParser._remove_jats_tags(abstract)

        # Remove HTML tags
        abstract = AbstractParser._remove_html_tags(abstract)

        # Normalize whitespace
        abstract = AbstractParser._normalize_whitespace(abstract)

        return abstract if abstract else None

    @staticmethod
    def _remove_jats_tags(text: str) -> str:
        """Remove JATS XML tags while preserving content."""
        # Remove opening and closing JATS tags, add space to separate
        text = re.sub(r'<jats:[^>]+>', ' ', text)
        text = re.sub(r'</jats:[^>]+>', ' ', text)
        return text

    @staticmethod
    def _remove_html_tags(text: str) -> str:
        """Remove HTML tags while preserving content."""
        # Remove HTML tags, add space to separate
        text = re.sub(r'<[^>]+>', ' ', text)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace and remove common prefixes like 'Abstract'."""
        # Replace multiple spaces/newlines/tabs with single space
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove "Abstract" prefix if it's at the start (often from title tags)
        text = re.sub(r'^Abstract\s+', '', text, flags=re.IGNORECASE)
        
        return text
