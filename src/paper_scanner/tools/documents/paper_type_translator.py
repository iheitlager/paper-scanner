"""
Paper type translator for converting between different publication type formats.

Provides translation from Crossref API paper types, BibTeX types, and other
formats to the standardized PaperType enum used throughout the application.
"""

import logging
from typing import Optional

from paper_scanner.core.enum import PaperType

logger = logging.getLogger(__name__)


class PaperTypeTranslator:
    """
    Translates publication types from various sources to standardized PaperType enum.
    
    Handles types from:
    - Crossref API (journal-article, proceedings-article, book-chapter, etc.)
    - BibTeX types (@article, @book, @inproceedings, etc.)
    - Custom formats
    """
    
    # Mapping from Crossref API types to PaperType
    CROSSREF_TO_PAPER_TYPE = {
        "journal-article": PaperType.ARTICLE,
        "journal_article": PaperType.ARTICLE,
        "article": PaperType.ARTICLE,
        
        "proceedings-article": PaperType.CONFERENCE,
        "proceedings_article": PaperType.CONFERENCE,
        "conference-paper": PaperType.CONFERENCE,
        "conference_paper": PaperType.CONFERENCE,
        "inproceedings": PaperType.CONFERENCE,
        
        "book": PaperType.BOOK,
        
        "book-chapter": PaperType.BOOK_CHAPTER,
        "book_chapter": PaperType.BOOK_CHAPTER,
        "chapter": PaperType.BOOK_CHAPTER,
        
        "thesis": PaperType.THESIS,
        "dissertation": PaperType.THESIS,
        "phdthesis": PaperType.THESIS,
        "mastersthesis": PaperType.THESIS,
        
        "report": PaperType.TECHNICAL_REPORT,
        "technical-report": PaperType.TECHNICAL_REPORT,
        "technical_report": PaperType.TECHNICAL_REPORT,
        "techreport": PaperType.TECHNICAL_REPORT,
        
        "working-paper": PaperType.WORKING_PAPER,
        "working_paper": PaperType.WORKING_PAPER,
        "workingpaper": PaperType.WORKING_PAPER,
        
        "preprint": PaperType.PREPRINT,
        "arxiv": PaperType.PREPRINT,
        
        "patent": PaperType.PATENT,
        
        "dataset": PaperType.DATASET,
        
        "misc": PaperType.OTHER,
        "other": PaperType.OTHER,
        "unknown": PaperType.OTHER,
    }
    
    # Mapping from BibTeX types to PaperType
    BIBTEX_TO_PAPER_TYPE = {
        "article": PaperType.ARTICLE,
        "journal_article": PaperType.JOURNAL_ARTICLE,
        
        "inproceedings": PaperType.CONFERENCE,
        "conference": PaperType.CONFERENCE,
        
        "book": PaperType.BOOK,
        
        "inbook": PaperType.BOOK_CHAPTER,
        "incollection": PaperType.BOOK_CHAPTER,
        
        "phdthesis": PaperType.THESIS,
        "mastersthesis": PaperType.THESIS,
        "thesis": PaperType.THESIS,
        
        "techreport": PaperType.TECHNICAL_REPORT,
        "report": PaperType.REPORT,
        
        "dataset": PaperType.DATASET,
        
        "preprint": PaperType.PREPRINT,
        
        "misc": PaperType.OTHER,
    }
    
    @staticmethod
    def from_crossref(crossref_type: Optional[str]) -> PaperType:
        """
        Translate Crossref API paper type to PaperType enum.
        
        Args:
            crossref_type: Type string from Crossref API (e.g., "journal-article")
            
        Returns:
            Corresponding PaperType enum value, defaults to OTHER if not found
            
        Examples:
            >>> PaperTypeTranslator.from_crossref("journal-article")
            PaperType.ARTICLE
            
            >>> PaperTypeTranslator.from_crossref("proceedings-article")
            PaperType.CONFERENCE
            
            >>> PaperTypeTranslator.from_crossref("book-chapter")
            PaperType.BOOK_CHAPTER
        """
        if not crossref_type:
            return PaperType.OTHER
        
        # Normalize: lowercase and replace spaces with hyphens
        normalized = str(crossref_type).lower().strip()
        
        if normalized in PaperTypeTranslator.CROSSREF_TO_PAPER_TYPE:
            return PaperTypeTranslator.CROSSREF_TO_PAPER_TYPE[normalized]
        
        logger.debug(f"Unknown Crossref paper type: {crossref_type}, defaulting to OTHER")
        return PaperType.OTHER
    
    @staticmethod
    def from_bibtex(bibtex_type: Optional[str]) -> PaperType:
        """
        Translate BibTeX entry type to PaperType enum.
        
        Args:
            bibtex_type: BibTeX type (e.g., "@article", "inproceedings")
            
        Returns:
            Corresponding PaperType enum value, defaults to OTHER if not found
            
        Examples:
            >>> PaperTypeTranslator.from_bibtex("article")
            PaperType.ARTICLE
            
            >>> PaperTypeTranslator.from_bibtex("@inproceedings")
            PaperType.CONFERENCE
            
            >>> PaperTypeTranslator.from_bibtex("phdthesis")
            PaperType.THESIS
        """
        if not bibtex_type:
            return PaperType.OTHER
        
        # Normalize: remove @ prefix if present, lowercase
        normalized = str(bibtex_type).lower().strip().lstrip("@")
        
        if normalized in PaperTypeTranslator.BIBTEX_TO_PAPER_TYPE:
            return PaperTypeTranslator.BIBTEX_TO_PAPER_TYPE[normalized]
        
        logger.debug(f"Unknown BibTeX paper type: {bibtex_type}, defaulting to OTHER")
        return PaperType.OTHER
    
    @staticmethod
    def from_generic(paper_type: Optional[str]) -> PaperType:
        """
        Translate generic paper type string to PaperType enum.
        
        Attempts to match against known types in any format. Tries Crossref
        mapping first, then BibTeX mapping, then direct enum value matching.
        
        Args:
            paper_type: Paper type string from any source
            
        Returns:
            Corresponding PaperType enum value, defaults to OTHER if not found
            
        Examples:
            >>> PaperTypeTranslator.from_generic("journal-article")
            PaperType.ARTICLE
            
            >>> PaperTypeTranslator.from_generic("ARTICLE")
            PaperType.ARTICLE
            
            >>> PaperTypeTranslator.from_generic("article")
            PaperType.ARTICLE
        """
        if not paper_type:
            return PaperType.OTHER
        
        normalized = str(paper_type).lower().strip()
        
        # Try Crossref mapping first
        if normalized in PaperTypeTranslator.CROSSREF_TO_PAPER_TYPE:
            return PaperTypeTranslator.CROSSREF_TO_PAPER_TYPE[normalized]
        
        # Try BibTeX mapping
        normalized_bibtex = normalized.lstrip("@")
        if normalized_bibtex in PaperTypeTranslator.BIBTEX_TO_PAPER_TYPE:
            return PaperTypeTranslator.BIBTEX_TO_PAPER_TYPE[normalized_bibtex]
        
        # Try direct enum value matching
        try:
            # Check if it matches an enum value
            for paper_type_enum in PaperType:
                if paper_type_enum.value == normalized:
                    return paper_type_enum
        except Exception:
            pass
        
        logger.debug(f"Unknown paper type: {paper_type}, defaulting to OTHER")
        return PaperType.OTHER
    
    @staticmethod
    def to_enum(paper_type: Optional[str], source: str = "generic") -> PaperType:
        """
        Convert paper type to PaperType enum using specified source format.
        
        Args:
            paper_type: Paper type string
            source: Source format - "crossref", "bibtex", or "generic" (default)
            
        Returns:
            Corresponding PaperType enum value
            
        Examples:
            >>> PaperTypeTranslator.to_enum("journal-article", source="crossref")
            PaperType.ARTICLE
            
            >>> PaperTypeTranslator.to_enum("@article", source="bibtex")
            PaperType.ARTICLE
        """
        if source == "crossref":
            return PaperTypeTranslator.from_crossref(paper_type)
        elif source == "bibtex":
            return PaperTypeTranslator.from_bibtex(paper_type)
        else:
            return PaperTypeTranslator.from_generic(paper_type)
