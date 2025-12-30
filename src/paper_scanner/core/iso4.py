"""
ISO4 Generator - Create standardized journal title abbreviations.

ISO4 (International Standard 4) defines rules for abbreviating journal titles.
This module provides a generator that converts full journal names to ISO4 abbreviations.

Reference: https://en.wikipedia.org/wiki/ISO_4
           https://www.issn.org/
"""
from typing import Optional
import re


class ISO4Generator:
    """Generate ISO4 abbreviations from full journal names.
    
    Rules implemented:
    - Remove common stop words (and, or, the, of, etc.)
    - Abbreviate significant words to 3-4 letters
    - Add periods after abbreviations
    - Preserve acronyms (IEEE, ACM, MIS, etc.)
    - Handle special characters (&, -, /)
    """

    # Common stop words to remove
    STOP_WORDS = {
        'and', 'or', 'the', 'a', 'an', 'of', 'in', 'to', 'for', 'on',
        'at', 'by', 'with', 'from', 'as', 'is', 'are', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can',
    }

    # Words that should be abbreviated to 3 letters
    ABBREVIATE_3 = {
        'journal', 'transactions', 'international', 'european',
        'american', 'british', 'proceedings', 'letters', 'studies',
        'systems', 'science', 'management', 'organization', 'business',
        'technology', 'information', 'research', 'review', 'quarterly',
        'annual', 'archive', 'engineering', 'environmental',
    }

    # Words that should be abbreviated to 4 letters
    ABBREVIATE_4 = {
        'advances', 'proceedings', 'development',
    }

    # Known acronyms that should be preserved as-is
    ACRONYMS = {
        'ieee': 'IEEE',
        'acm': 'ACM',
        'mis': 'MIS',
        'vhb': 'VHB',
        'ais': 'AIS',
    }

    # Abbreviations for common words with special handling
    SPECIAL_ABBREVIATIONS = {
        'journal': 'J.',
        'transactions': 'Trans.',
        'international': 'Int.',
        'european': 'Eur.',
        'american': 'Am.',
        'british': 'Br.',
        'proceedings': 'Proc.',
        'letters': 'Lett.',
        'studies': 'Stud.',
        'systems': 'Syst.',
        'science': 'Sci.',
        'management': 'Manag.',
        'organization': 'Organ.',
        'business': 'Bus.',
        'technology': 'Technol.',
        'information': 'Inf.',
        'research': 'Res.',
        'review': 'Rev.',
        'quarterly': 'Q.',
        'annual': 'Ann.',
        'archive': 'Arch.',
        'engineering': 'Eng.',
        'environmental': 'Environ.',
        'engineering': 'Eng.',
        'sustainable': 'Sustain.',
        'sustainability': 'Sustain.',
        'development': 'Dev.',
        'advances': 'Adv.',
        'economics': 'Econ.',
        'electronic': 'Electron.',
        'production': 'Prod.',
    }

    def __init__(self):
        """Initialize ISO4 generator."""
        pass

    def generate(self, journal_name: Optional[str]) -> Optional[str]:
        """Generate ISO4 abbreviation from full journal name.
        
        Args:
            journal_name: Full journal title (e.g., "Journal of Business Research")
        
        Returns:
            ISO4 abbreviation (e.g., "J. Bus. Res.") or None if input is invalid
        
        Examples:
            >>> gen = ISO4Generator()
            >>> gen.generate("Journal of Business Research")
            'J. Bus. Res.'
            >>> gen.generate("Academy of Management Journal")
            'Acad. Manag. J.'
        """
        if not journal_name or not isinstance(journal_name, str):
            return None
        
        # Normalize input
        journal_name = journal_name.strip()
        if not journal_name:
            return None
        
        # Extract words, removing punctuation but preserving structure
        words = self._extract_words(journal_name)
        if not words:
            return None
        
        # Filter stop words and abbreviate
        abbreviated = []
        for word in words:
            abbrev = self._abbreviate_word(word)
            if abbrev:  # Skip None results (stop words)
                abbreviated.append(abbrev)
        
        if not abbreviated:
            return None
        
        # Join with spaces and ensure proper period format
        result = ' '.join(abbreviated)
        
        # Ensure last element has period if it doesn't already
        if not result.endswith('.'):
            result += '.'
        
        return result

    def _extract_words(self, text: str) -> list[str]:
        """Extract words from journal title.
        
        Handles:
        - Hyphens and dashes as separators
        - Ampersands and slashes as connectors (converted to 'and')
        - Special characters removed
        """
        # Replace common separators with spaces
        text = text.replace('-', ' ')
        text = text.replace('&', ' and ')
        text = text.replace('/', ' or ')
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-zA-Z]+\b', text)
        
        return words

    def _abbreviate_word(self, word: str) -> Optional[str]:
        """Abbreviate a single word according to ISO4 rules.
        
        Args:
            word: Single word to abbreviate
        
        Returns:
            Abbreviated word with period, or None if word is a stop word
        """
        if not word:
            return None
        
        word_lower = word.lower()
        
        # Check if it's a stop word
        if word_lower in self.STOP_WORDS:
            return None
        
        # Check if it's a known acronym
        if word_lower in self.ACRONYMS:
            return self.ACRONYMS[word_lower]
        
        # Check for special abbreviations
        if word_lower in self.SPECIAL_ABBREVIATIONS:
            return self.SPECIAL_ABBREVIATIONS[word_lower]
        
        # Default abbreviation logic
        # Short words (3-4 letters) stay as-is
        if len(word) <= 4:
            return word.capitalize() + '.'
        
        # Longer words get abbreviated to 3 letters
        return word[:3].capitalize() + '.'

    def batch_generate(self, journal_names: list[str]) -> dict[str, Optional[str]]:
        """Generate ISO4 abbreviations for multiple journal names.
        
        Args:
            journal_names: List of full journal titles
        
        Returns:
            Dictionary mapping journal name -> ISO4 abbreviation
        """
        return {name: self.generate(name) for name in journal_names}
