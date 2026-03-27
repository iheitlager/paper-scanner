"""
File reader and DOI extraction for PDF documents.

Provides FileReader class for reading PDFs and DOIExtractor for extracting
DOI information from PDF metadata and content.
"""

import hashlib
import logging
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import PDF libraries
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
    # Suppress pypdf debug output aggressively after successful import
    pypdf_logger = logging.getLogger("pypdf")
    pypdf_logger.setLevel(logging.WARNING)
    pypdf_logger.propagate = False
    pypdf_logger.handlers = []

    pypdf_reader_logger = logging.getLogger("pypdf._reader")
    pypdf_reader_logger.setLevel(logging.WARNING)
    pypdf_reader_logger.propagate = False
    pypdf_reader_logger.handlers = []
except ImportError:
    HAS_PYPDF = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

import requests


@contextmanager
def suppress_pypdf_output():
    """Context manager to suppress pypdf debug output to stderr."""
    # Redirect stderr to devnull
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        yield
    finally:
        sys.stderr = old_stderr


def compute_file_sha256(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Compute SHA256 hash of a file.

    Reads file in chunks to handle large files efficiently without
    loading entire file into memory.

    Args:
        file_path: Path to the file
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        SHA256 hash as hexadecimal string

    Raises:
        FileNotFoundError: If file does not exist
        IOError: If file cannot be read
    """
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except IOError as e:
        raise IOError(f"Failed to read file {file_path}: {e}")


class DOIExtractor:
    """
    Extract DOI from PDF using multiple methods.

    Tries extraction methods in order:
    1. PDF metadata extraction (using pypdf)
    2. Content regex search (using pdfplumber or pypdf)
    3. Title lookup via Crossref API (fallback)
    """

    def __init__(self, email: str = "i.heitlager@tue.nl"):
        """
        Initialize DOI extractor.

        Args:
            email: Email for Crossref API user-agent
        """
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'PDFDOIExtractor/1.0 (mailto:{email})'
        })

    def extract_from_pdf(self, pdf_path: Path) -> Optional[str]:
        """
        Extract DOI from PDF using multiple methods.

        Args:
            pdf_path: Path to PDF file

        Returns:
            DOI string if found, None otherwise
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists() or not pdf_path.is_file():
            logger.warning(f"PDF file not found: {pdf_path}")
            return None

        # Try methods in order
        methods = [
            ("Metadata extraction", self._extract_from_metadata),
            ("Content regex search", self._extract_from_content),
            ("Title lookup (Crossref)", self._extract_from_title_lookup),
        ]

        for method_name, method_func in methods:
            try:
                doi = method_func(pdf_path)
                if doi:
                    logger.debug(f"DOI extracted via {method_name}: {doi}")
                    return doi
            except Exception as e:
                logger.debug(f"DOI extraction via {method_name} failed: {e}")

        return None

    def _extract_from_metadata(self, pdf_path: Path) -> Optional[str]:
        """Extract DOI from PDF metadata."""
        if not HAS_PYPDF:
            return None

        try:
            with suppress_pypdf_output():
                with open(pdf_path, 'rb') as f:
                    reader = PdfReader(f)
                    metadata = reader.metadata

                    if metadata:
                        # Check common metadata fields
                        for field in ('/Subject', '/Keywords', '/Producer', '/Title'):
                            value = metadata.get(field, '')
                            if isinstance(value, bytes):
                                value = value.decode('utf-8', errors='ignore')
                            if isinstance(value, str):
                                doi = self._extract_doi_from_text(value)
                                if doi:
                                    return doi

        except Exception as e:
            logger.debug(f"Metadata extraction failed: {e}")

        return None

    def _extract_from_content(self, pdf_path: Path) -> Optional[str]:
        """Extract DOI from PDF text content using regex."""
        # Try pdfplumber first (more reliable)
        if HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    # Search first 3 pages for DOI
                    for page_num, page in enumerate(pdf.pages[:3]):
                        text = page.extract_text()
                        if text:
                            doi = self._extract_doi_from_text(text)
                            if doi:
                                return doi

            except Exception as e:
                logger.debug(f"pdfplumber extraction failed: {e}")

        # Fallback: try pypdf
        if HAS_PYPDF:
            try:
                with suppress_pypdf_output():
                    with open(pdf_path, 'rb') as f:
                        reader = PdfReader(f)
                        # Search first 3 pages
                        for page_num in range(min(3, len(reader.pages))):
                            page = reader.pages[page_num]
                            text = page.extract_text()
                            if text:
                                doi = self._extract_doi_from_text(text)
                                if doi:
                                    return doi

            except Exception as e:
                logger.debug(f"pypdf extraction failed: {e}")

        return None

    def _extract_doi_from_text(self, text: str) -> Optional[str]:
        """
        Extract DOI from plain text using regex.

        Args:
            text: Text to search for DOI

        Returns:
            DOI string if found, None otherwise
        """
        # DOI regex pattern - matches various formats
        patterns = [
            r'(?:doi|DOI)[\s:]*(?:https?://(?:dx\.)?doi\.org/)?(?P<doi>10\.\S+/\S+)',
            r'(?:https?://)?(?:dx\.)?doi\.org/(?P<doi>10\.\S+)',
            r'(?P<doi>10\.\d{4,}/\S+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doi = match.group('doi')
                # Clean up common artifacts (trailing punctuation and brackets)
                doi = re.sub(r'[.,;)\s\]]*$', '', doi)
                # Validate DOI format
                if doi.startswith('10.') and '/' in doi:
                    return doi.lower()

        return None

    def _extract_from_title_lookup(self, pdf_path: Path) -> Optional[str]:
        """
        Try to extract title and lookup DOI via Crossref.

        This is a fallback method when DOI is not directly in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            DOI if found via Crossref lookup, None otherwise
        """
        if not HAS_PDFPLUMBER and not HAS_PYPDF:
            return None

        try:
            # Extract title from first page
            title = None

            if HAS_PDFPLUMBER:
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        first_page_text = pdf.pages[0].extract_text()
                        # Title is usually in first 500 chars, before abstract
                        lines = first_page_text.split('\n')
                        title = lines[0].strip() if lines else None
                except Exception:
                    pass

            if not title and HAS_PYPDF:
                try:
                    with open(pdf_path, 'rb') as f:
                        reader = PdfReader(f)
                        text = reader.pages[0].extract_text()
                        lines = text.split('\n')
                        title = lines[0].strip() if lines else None
                except Exception:
                    pass

            if title and len(title) > 10:
                # Query Crossref API for DOI
                try:
                    url = "https://api.crossref.org/works"
                    params = {
                        'query': title[:100],
                        'rows': 1
                    }
                    response = self.session.get(url, params=params, timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('message', {}).get('items', [])
                        if items:
                            doi = items[0].get('DOI')
                            if doi:
                                return doi.lower()

                except Exception as e:
                    logger.debug(f"Crossref lookup failed: {e}")

        except Exception as e:
            logger.debug(f"Title lookup failed: {e}")

        return None


class FileReader:
    """
    Read PDF file and extract metadata and text.

    Provides methods to:
    - Read PDF file information
    - Extract text content
    - Extract DOI from PDF
    - Get file metadata
    """

    def __init__(self, pdf_path: Path, email: str = "i.heitlager@tue.nl"):
        """
        Initialize file reader.

        Args:
            pdf_path: Path to PDF file
            email: Email for Crossref API (used by DOIExtractor)
        """
        self.pdf_path = Path(pdf_path).resolve()
        self.doi_extractor = DOIExtractor(email=email)
        self._doi = None
        self._text = None

    def exists(self) -> bool:
        """Check if PDF file exists."""
        return self.pdf_path.exists() and self.pdf_path.is_file()

    def get_file_info(self) -> Dict[str, Any]:
        """
        Get file metadata.

        Returns:
            Dictionary with file information
        """
        if not self.exists():
            logger.warning(f"File not found: {self.pdf_path}")
            return {}

        try:
            stat = self.pdf_path.stat()
            return {
                "file_path": str(self.pdf_path),
                "file_directory": str(self.pdf_path.parent),
                "file_name": self.pdf_path.name,
                "file_size_bytes": stat.st_size,
                "file_hash": compute_file_sha256(self.pdf_path),
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed_time": datetime.fromtimestamp(stat.st_atime).isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return {}

    def extract_doi(self) -> Optional[str]:
        """
        Extract DOI from PDF.

        Caches result to avoid re-extraction.

        Returns:
            DOI string if found, None otherwise
        """
        if self._doi is not None:
            return self._doi

        if not self.exists():
            return None

        self._doi = self.doi_extractor.extract_from_pdf(self.pdf_path)
        return self._doi

    def extract_text(self) -> Optional[str]:
        """
        Extract text from PDF.

        Caches result to avoid re-extraction.

        Returns:
            Extracted text or None if extraction fails
        """
        if self._text is not None:
            return self._text

        if not HAS_PDFPLUMBER and not HAS_PYPDF:
            logger.warning("No PDF extraction libraries available")
            return None

        if not self.exists():
            return None

        try:
            # Try pdfplumber first (usually better)
            if HAS_PDFPLUMBER:
                try:
                    with pdfplumber.open(self.pdf_path) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                        self._text = text
                        return text
                except Exception as e:
                    logger.debug(f"pdfplumber extraction failed: {e}")

            # Fallback to pypdf
            if HAS_PYPDF:
                try:
                    with suppress_pypdf_output():
                        with open(self.pdf_path, 'rb') as f:
                            reader = PdfReader(f)
                            text = "\n".join(page.extract_text() or "" for page in reader.pages)
                            self._text = text
                            return text
                except Exception as e:
                    logger.debug(f"pypdf extraction failed: {e}")

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")

        return None

    def get_page_count(self) -> Optional[int]:
        """
        Get number of pages in PDF.

        Returns:
            Page count or None if unable to determine
        """
        if not self.exists():
            return None

        try:
            if HAS_PDFPLUMBER:
                try:
                    with pdfplumber.open(self.pdf_path) as pdf:
                        return len(pdf.pages)
                except Exception:
                    pass

            if HAS_PYPDF:
                try:
                    with open(self.pdf_path, 'rb') as f:
                        reader = PdfReader(f)
                        return len(reader.pages)
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Failed to get page count: {e}")

        return None
