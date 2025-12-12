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
from ..core.enum import DiscoveryMethod, PaperType
from ..tools.documents import FileReader, AbstractParser, PaperTypeTranslator
from ..tools.fetchers.crossref_fetcher import PoliteCrossrefClient
from ..io.json import dict_to_paper

console = Console(file=sys.stderr)

# Valid source types
VALID_SOURCE_TYPES = {"crossref", "other"}


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

    # Check source (optional, defaults to crossref)
    if "source" in config:
        sources = config["source"]
        if not isinstance(sources, list):
            errors.append("'source' must be a list")
        else:
            for source in sources:
                if source not in VALID_SOURCE_TYPES:
                    errors.append(f"'source' must contain {VALID_SOURCE_TYPES}, got '{source}'")

    # Check download_details (optional)
    if "download_details" in config and not isinstance(config["download_details"], bool):
        errors.append("'download_details' must be a boolean")

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


def _crossref_work_to_paper(
    work: Dict[str, Any],
    doi: str,
    discovery: Discovery
) -> Optional[Paper]:
    """
    Convert Crossref work metadata to Paper model.

    Args:
        work: Crossref work data from API
        doi: DOI (already validated)
        discovery: Discovery metadata

    Returns:
        Paper model or None if conversion fails
    """
    try:
        from ..io.bibtex import parse_authors, parse_keywords

        # Extract title
        title = ""
        if isinstance(work.get("title"), list) and work["title"]:
            title = work["title"][0]
        elif isinstance(work.get("title"), str):
            title = work["title"]

        if not title:
            console.print(f"[yellow]⚠️  No title found for DOI {doi}[/yellow]")
            return None

        # Create cite_key from DOI
        cite_key = _reformat_doi(doi)

        # Extract authors
        authors = []
        for author in work.get("author", []):
            if isinstance(author, dict):
                family_name = author.get("family", "")
                given_name = author.get("given", "")
                if family_name:
                    authors.append({
                        "family_name": family_name,
                        "given_name": given_name,
                        "full_name": f"{given_name} {family_name}" if given_name else family_name
                    })

        # Convert author dicts to Author objects
        author_objs = []
        for auth in authors:
            from ..core.models import Author
            author_objs.append(Author(
                family_name=auth["family_name"],
                given_name=auth.get("given_name"),
                full_name=auth["full_name"]
            ))

        # Extract year
        year = None
        if "published-print" in work:
            date_parts = work["published-print"].get("date-parts", [[]])[0]
            if date_parts:
                try:
                    year = int(date_parts[0])
                except (ValueError, TypeError):
                    pass
        elif "published-online" in work:
            date_parts = work["published-online"].get("date-parts", [[]])[0]
            if date_parts:
                try:
                    year = int(date_parts[0])
                except (ValueError, TypeError):
                    pass

        # Extract journal
        journal = None
        if isinstance(work.get("container-title"), list):
            container_titles = work.get("container-title", [])
            journal = container_titles[0] if container_titles else None
        else:
            journal = work.get("container-title")

        # Extract volume, issue, pages
        volume = work.get("volume")
        number = work.get("issue")
        pages = None
        if "page" in work:
            pages = work["page"]

        # Extract publisher
        publisher = work.get("publisher")

        # Extract abstract (may not be available)
        abstract = work.get("abstract")
        # Clean abstract if present (remove JATS/HTML markup)
        if abstract:
            abstract = AbstractParser.clean(abstract)

        # Get paper type from Crossref and translate to PaperType enum
        crossref_type = work.get("type", "article")
        paper_type = PaperTypeTranslator.from_crossref(crossref_type).value

        # Create Paper model
        paper = Paper(
            cite_key=cite_key,
            source_key=doi,
            title=title,
            abstract=abstract,
            authors=author_objs,
            year=year,
            journal=journal,
            publisher=publisher,
            volume=volume,
            number=number,
            pages=pages,
            paper_type=paper_type,
            doi=doi,
            url=work.get("URL"),
            discovery=discovery,
            screening=Screening(),
            raw_json=work
        )

        return paper

    except Exception as e:
        console.print(f"[red]✗ Failed to convert Crossref work to Paper for {doi}: {e}[/red]")
        return None


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
    sources = config.get("source", ["crossref"])
    download_details = config.get("download_details", True)
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

    # Create Crossref client if needed
    crossref_client = None
    if "crossref" in sources:
        try:
            crossref_client = PoliteCrossrefClient(cache_dir=cache_dir)
            if verbose:
                console.print("[cyan]Crossref client initialized[/cyan]")
                if cache_dir:
                    console.print(f"[dim]  Cache: {cache_dir}/crossref[/dim]")
        except Exception as e:
            error_msg = f"Failed to initialize Crossref client: {e}"
            console.print(f"[red]✗ {error_msg}[/red]")
            return {
                "status": "error",
                "error": error_msg,
                "papers_loaded": 0,
                "papers_failed": 0
            }

    # Scan for PDF files
    pdf_files = sorted(file_path.glob("*.pdf"))

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

            # Step 3: Fetch from Crossref
            work_data = None
            if crossref_client:
                try:
                    work_data = crossref_client.get_work(doi)
                except Exception as e:
                    file_result["error"] = f"Crossref fetch failed"
                    results["papers_failed"] += 1
                    console.print(f"[yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: Crossref error")
                    results["details"].append(file_result)
                    continue

            if not work_data or "message" not in work_data:
                file_result["error"] = "No metadata in Crossref"
                results["papers_failed"] += 1
                console.print(f"[yellow]⚠️  {i}/{len(pdf_files)}[/yellow] {pdf_path.name}: no metadata")
                results["details"].append(file_result)
                continue

            work = work_data["message"]

            # Step 4: Create Discovery object
            discovery = Discovery(
                method=DiscoveryMethod.LITERATURE_REVIEW_MINING,
                source_database="crossref",
                discovered_by="load_files"
            )

            # Step 5: Convert to Paper model
            paper = _crossref_work_to_paper(work, doi, discovery)
            if not paper:
                file_result["error"] = "Failed to create Paper"
                results["papers_failed"] += 1
                console.print(f"[red]✗ {i}/{len(pdf_files)}[/red] {pdf_path.name}: model error")
                results["details"].append(file_result)
                continue

            file_result["cite_key"] = paper.cite_key
            file_result["title"] = paper.title

            # Step 6: Add PDFInfo to paper
            page_count = file_reader.get_page_count()
            paper.pdf_info = PDFInfo(
                file_path=str(pdf_path),
                file_name=file_info.get("file_name"),
                file_size_bytes=file_info.get("file_size_bytes"),
                pdf_pages=page_count,
                download_source="local",
                downloaded_at=datetime.now()
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
            
            # Add cache signal
            cache_signal = "[dim]💾[/dim]" if crossref_client.last_cache_hit else "[cyan]🌐[/cyan]"
            console.print(f"[green]✓ {i}/{len(pdf_files)}[/green] {cache_signal} {pdf_path.name} → {new_filename}")

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
