"""PDF text extraction using pdfplumber.

This module provides text extraction from academic PDFs with section detection
and canonical structure normalization.
"""

import logging
from typing import Dict, Optional

from paper_scanner.tools.embedding.sections import (
    detect_sections,
    group_sections_hierarchically,
    validate_paper_structure,
)

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text and structure from PDFs using pdfplumber."""

    def __init__(self):
        """Initialize PDF extractor."""
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if pdfplumber is available."""
        try:
            import pdfplumber  # noqa: F401
            return True
        except ImportError:
            return False

    def extract(self, pdf_path: str) -> Optional[Dict]:
        """Extract text and structure from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with text, detected sections (raw and hierarchical), coverage stats
            or None if extraction fails
        """
        if not self.available:
            logger.error("pdfplumber not available")
            return None

        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                text = self._extract_text(pdf)
                
                # Use sections.py for detection and canonicalization
                raw_sections = detect_sections(text)
                hierarchical = group_sections_hierarchically(raw_sections)
                coverage = validate_paper_structure(hierarchical)
                
                return {
                    'tool': 'pdfplumber',
                    'pdf_path': pdf_path,
                    'text': text,
                    'raw_sections': raw_sections,
                    'hierarchical_sections': hierarchical,
                    'coverage': coverage,
                    'canonical_sections_found': len([s for s in coverage['found']]),
                }
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return None

    @staticmethod
    def _extract_text(pdf) -> str:
        """Extract text from all pages.
        
        Args:
            pdf: pdfplumber PDF object
            
        Returns:
            Combined text from all pages
        """
        full_text = ""
        
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n\n"
        
        return full_text
