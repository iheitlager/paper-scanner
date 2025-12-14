"""
Load files step - Load PDF files from folder, extract DOI, fetch metadata from Crossref

Processes PDF files:
1. Scans folder for PDF files
2. Extracts DOI from each PDF
3. Fetches metadata from Crossref using DOI
4. Transforms metadata into Paper models
5. Stores papers in database
6. Copies PDF to store_path with DOI-based filename
7. Updates PDFInfo with file details
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from rich.console import Console
import shutil
import logging

from ..core.models import Paper, PDFInfo, Discovery, Screening
from ..core.database import PapersDatabase
from ..core.enum import DiscoveryMethod
from ..tools.documents import FileReader

console = Console(file=sys.stderr)



def validate(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate load_files step configuration.

    Args:
        config: Step configuration

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check file_path
    if "file_path" not in config:
        errors.append("'file_path' is required")
    elif not isinstance(config["file_path"], str):
        errors.append("'file_path' must be a string")

    # Check store_path
    if "store_path" not in config:
        errors.append("'store_path' is required")
    elif not isinstance(config["store_path"], str):
        errors.append("'store_path' must be a string")

    # Check expected_count (optional)
    if "expected_count" in config:
        expected = config["expected_count"]
        if not isinstance(expected, int) or expected < 0:
            errors.append("'expected_count' must be a non-negative integer")

    return len(errors) == 0, errors


def _reformat_doi(doi: str) -> str:
    """
    Reformat DOI for filename: replace /.: with _

    Args:
        doi: DOI string

    Returns:
        Reformatted DOI safe for filenames
    """
    import re
    return re.sub(r'[/.:]+', '_', doi)


def execute(
    config: Dict[str, Any],
    papers_db: PapersDatabase,
    verbose: bool = False,
    dry_run: bool = False,
    cache_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Execute load_files step

    Args:
        config: Step configuration
        papers_db: Current papers database
        verbose: Enable verbose output
        dry_run: Don't actually store files or modify database
        cache_dir: Cache directory for Crossref API responses (optional)

    Returns:
        Execution result dictionary
    """

    file_path = Path(config.get("file_path", "")).expanduser()
    store_path = Path(config.get("store_path", "")).expanduser()
    expected_count = config.get("expected_count")

    # Validate paths
    if not file_path.exists() or not file_path.is_dir():
        error_msg = f"File path does not exist or is not a directory: {file_path}"
        console.print(f"[red]✗ {error_msg}[/red]")
        return {
            "status": "error",
            "error": error_msg,
            "papers_loaded": 0,
            "papers_failed": 0
        }

    # Create store path
    store_path.mkdir(parents=True, exist_ok=True)


    # Scan for PDF files
    pdf_files = sorted(file_path.glob("*.pdf"))

    if verbose:
        console.print(f"  [dim]Loading {len(pdf_files)} PDF files from:[/dim] {file_path}")
        console.print(f"  [dim]Storing files to:[/dim] {store_path}")

    if not pdf_files:
        console.print(f"[yellow]⚠️  No PDF files found in {file_path}[/yellow]")
        return {
            "status": "ok",
            "papers_loaded": 0,
            "papers_failed": 0,
            "message": "No PDF files found"
        }

    # Track results
    results = {
        "papers_loaded": 0,
        "papers_failed": 0,
        "files_copied": 0,
        "details": [],
        "status": "ok"
    }

    # Process each PDF
    for i, pdf_path in enumerate(pdf_files, 1):
        file_result = {
            "filename": pdf_path.name,
            "success": False,
            "doi": None,
            "cite_key": None,
            "title": None,
            "error": None,
        }

        try:

            # Step 1: Read file
            file_reader = FileReader(pdf_path)
            if not file_reader.exists():
                file_result["error"] = "PDF file not found"
                results["papers_failed"] += 1
                console.print(f"[yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: not found")
                results["details"].append(file_result)
                continue

            file_info = file_reader.get_file_info()

            # Step 2: Extract DOI
            doi = file_reader.extract_doi()
            if not doi:
                file_result["error"] = "No DOI extracted"
                results["papers_failed"] += 1
                console.print(f"[yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: no DOI")
                results["details"].append(file_result)
                continue

            file_result["doi"] = doi

            # Step 4: Create Discovery object
            discovery = Discovery(
                method=DiscoveryMethod.FILE_PATH,
                source_database="file_path",
            )

            paper = Paper(
                source_key=doi,
                cite_key=pdf_path.stem,
                doi=doi,
                discovery=discovery,
                screening=Screening()
            )

            # Step 6: Add PDFInfo to paper
            page_count = file_reader.get_page_count()
            paper.pdf_info = PDFInfo(
                file_path=str(pdf_path),
                file_name=file_info.get("file_name"),
                file_size_bytes=file_info.get("file_size_bytes"),
                pdf_pages=page_count
            )

            # Step 7: Store in database
            if not dry_run:
                try:
                    papers_db.add(paper)
                except Exception as e:
                    file_result["error"] = "DB storage failed"
                    results["papers_failed"] += 1
                    console.print(f"[red]✗ {i}/{len(pdf_files)}[/red] {pdf_path.name}: DB error")
                    results["details"].append(file_result)
                    continue

            # Step 8: Copy file to store_path
            reformatted_doi = _reformat_doi(doi)
            new_filename = f"{reformatted_doi}.pdf"
            new_filepath = store_path / new_filename

            if not dry_run:
                try:
                    shutil.copy2(pdf_path, new_filepath)
                    results["files_copied"] += 1
                except Exception as e:
                    file_result["error"] = "File copy failed"
                    results["papers_failed"] += 1
                    console.print(f"[red]✗ {i}/{len(pdf_files)}[/red] {pdf_path.name}: copy error")
                    results["details"].append(file_result)
                    continue

            # Success!
            file_result["success"] = True
            results["papers_loaded"] += 1

            if verbose:
                console.print(f"[green]✓ {i}/{len(pdf_files)}[/green] {pdf_path.name} → {new_filename}")

        except Exception as e:
            file_result["error"] = str(e)
            file_result["success"] = False
            console.print(f"[red]✗ {i}/{len(pdf_files)}[/red] {pdf_path.name}: {str(e)[:50]}")
            results["papers_failed"] += 1
            console.print(f"[red]Exception while processing {pdf_path}: {e}[/red]")

        results["details"].append(file_result)

    # Display summary
    if verbose:
        console.print()
        loaded = results["papers_loaded"]
        failed = results["papers_failed"]
        total = len(pdf_files)
        status = "[green]✓[/green]" if failed == 0 else "[yellow]⚠️ [/yellow]"
        console.print(f"{status} [cyan]Summary:[/cyan] {loaded}/{total} loaded, {failed} failed" + 
                     (f", expected {expected_count}" if expected_count and loaded != expected_count else ""))
        console.print()

    return results
