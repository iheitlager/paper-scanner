"""Citation detection and removal for academic papers.

This module provides utilities to identify and remove citations from academic
paper text while tracking removal statistics (characters, tokens removed).
"""

import re
from typing import Dict, Tuple

import tiktoken


class CitationRemover:
    """Detect and remove citations from extracted text."""

    # Common citation patterns
    CITATION_PATTERNS = [
        # [Author, Year] or [Author et al., Year]
        r'\[\s*[A-Z][a-z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\]',
        # (Author, Year) or (Author et al., Year)
        r'\(\s*[A-Z][a-z]+(?:\s+et\s+al\.?)?\s*,\s*\d{4}\s*\)',
        # Author (Year) - common in-text format
        r'[A-Z][a-z]+\s+\(\d{4}\)',
        # References section headers
        r'^\s*(References|Bibliography|Works Cited|Citations)\s*$',
        # Citation blocks (multiple lines of citations)
        r'\[[\d\s,]+\]',
    ]

    def __init__(self):
        """Initialize citation remover."""
        self.citation_blocks = []

    def remove_citations(self, text: str) -> Tuple[str, Dict]:
        """Remove citations from text and track removal statistics.

        Args:
            text: Input text with citations

        Returns:
            Tuple of (cleaned_text, stats_dict)
        """
        original_length = len(text)
        original_tokens = self._count_tokens(text)

        cleaned = text
        removed_chars = 0
        removed_tokens = 0
        matches_found = 0

        # Apply each pattern
        for pattern in self.CITATION_PATTERNS:
            matches = re.finditer(pattern, cleaned, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                citation_text = match.group(0)
                citation_chars = len(citation_text)
                citation_tokens = self._count_tokens(citation_text)

                self.citation_blocks.append({
                    'text': citation_text[:50] + ('...' if len(citation_text) > 50 else ''),
                    'chars': citation_chars,
                    'tokens': citation_tokens,
                })

                removed_chars += citation_chars
                removed_tokens += citation_tokens
                matches_found += 1

        # Remove all citations
        for pattern in self.CITATION_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)

        # Clean up extra whitespace
        cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
        cleaned = cleaned.strip()

        final_chars = len(cleaned)
        final_tokens = self._count_tokens(cleaned)

        return cleaned, {
            'original_chars': original_length,
            'original_tokens': original_tokens,
            'final_chars': final_chars,
            'final_tokens': final_tokens,
            'removed_chars': removed_chars,
            'removed_tokens': removed_tokens,
            'removed_percentage_chars': round(100 * removed_chars / original_length, 2) if original_length > 0 else 0,
            'removed_percentage_tokens': round(100 * removed_tokens / original_tokens, 2) if original_tokens > 0 else 0,
            'citations_found': matches_found,
        }

    @staticmethod
    def _count_tokens(text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback: rough estimate (1 token ≈ 4 chars)
            return len(text) // 4

    def get_citation_summary(self) -> str:
        """Get summary of removed citations."""
        if not self.citation_blocks:
            return "No citations removed"

        summary = f"Removed {len(self.citation_blocks)} citations:\n"
        for i, citation in enumerate(self.citation_blocks[:5], 1):
            summary += f"  {i}. {citation['text']} ({citation['chars']} chars, {citation['tokens']} tokens)\n"

        if len(self.citation_blocks) > 5:
            summary += f"  ... and {len(self.citation_blocks) - 5} more\n"

        return summary
