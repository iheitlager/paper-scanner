"""Shared helpers for LLM-based pipeline steps."""

import os
from typing import Any, Callable, Dict, List, Optional

from paper_scanner.core.models import Paper


def resolve_llm_input(
    paper: Paper,
    use_pdf: bool,
    format_paper_text: Callable[[Paper], str],
) -> str:
    """Resolve the input to send to the LLM: PDF path or formatted text.

    Args:
        paper: The paper to process.
        use_pdf: Whether to prefer sending the PDF natively.
        format_paper_text: Fallback function to format paper as text.

    Returns:
        PDF file path (if use_pdf and file exists) or formatted text string.
    """
    if use_pdf:
        pdf_path = paper.pdf_info.file_path if paper.pdf_info else None
        if pdf_path and os.path.exists(pdf_path):
            return pdf_path
    return format_paper_text(paper)


def validate_use_pdf(config: Dict[str, Any], errors: List[str]) -> None:
    """Validate the use_pdf config option, appending errors if invalid."""
    if "use_pdf" in config and not isinstance(config["use_pdf"], bool):
        errors.append("'use_pdf' must be a boolean")
