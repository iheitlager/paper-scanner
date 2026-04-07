"""
Extractor implementations for spike 020.

This package contains different approaches for extracting metadata from academic PDFs:
- regex_extractor: PyPDF + regex patterns
- scibert_extractor: SciBERT ML model
- claude_extractor: Claude API
- markdown_extractor: PDF-to-Markdown conversion
"""

from pathlib import Path

SPIKE_DIR = Path(__file__).parent.parent
CORPUS_DIR = SPIKE_DIR.parent.parent / "corpus"
