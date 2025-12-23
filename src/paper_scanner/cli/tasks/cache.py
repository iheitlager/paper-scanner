"""
Cache task - Manage cache operations

This task handles cache operations like clearing checkpoints and other
cache management functions.
"""

import shutil
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from paper_scanner.tools.cache import PDFCache
from paper_scanner.tools.documents import FileReader

console = Console(file=sys.stderr)


def _get_dir_size(path: Path) -> int:
    """Get total size of directory in bytes"""
    if not path.exists():
        return 0
    total_size = 0
    for item in path.rglob("*"):
        if item.is_file():
            total_size += item.stat().st_size
    return total_size


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size"""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def _collapse_home(path: Path) -> str:
    """Convert home directory path to use ~ notation"""
    try:
        home = Path.home()
        if path.is_relative_to(home):
            return f"~/{path.relative_to(home)}"
    except (ValueError, AttributeError):
        pass
    return str(path)

def _count_files(path: Path) -> int:
    """Count number of files in directory"""
    if not path.exists():
        return 0
    return len(list(path.rglob("*")))

def execute_cache_info(
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
) -> int:
    """
    Display cache information.

    Args:
        cache_dir: Cache directory (default: ~/.paper-scanner)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success)
    """
    import os

    # Determine cache_dir
    if cache_dir is None:
        cache_dir = Path(os.getenv("CACHE_DIR", ""))
        if not cache_dir or str(cache_dir) == ".":
            cache_dir = None

    if cache_dir is None:
        cache_dir = Path("~/.paper-scanner").expanduser()
    else:
        cache_dir = cache_dir.expanduser()

    if verbose:
        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]\n")

    # Create table for cache info
    table = Table(title="Cache Contents", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")

    # Cache folders to display
    cache_folders = [
        ("checkpoints", "checkpoints"),
        ("crossref", "crossref"),
        ("openalex", "openalex"),
        ("pdfs", "pdfs"),
    ]

    total_files = 0
    total_size = 0

    for name, folder in cache_folders:
        folder_dir = cache_dir / folder
        folder_files = _count_files(folder_dir)
        folder_size = _get_dir_size(folder_dir)
        table.add_row(
            name,
            f"{_collapse_home(folder_dir)}/",
            str(folder_files),
            _format_size(folder_size),
        )
        total_files += folder_files
        total_size += folder_size

    # Total
    table.add_row(
        "[bold]Total[/bold]",
        "",
        f"[bold]{total_files}[/bold]",
        f"[bold]{_format_size(total_size)}[/bold]",
    )

    console.print(table)
    return 0


def execute_cache_clear(
    target: str,
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
) -> int:
    """
    Clear cache contents.

    Args:
        target: What to clear ('checkpoints', etc.)
        cache_dir: Cache directory (default: ~/.paper-scanner)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import os

    # Determine cache_dir
    if cache_dir is None:
        cache_dir = Path(os.getenv("CACHE_DIR", ""))
        if not cache_dir or str(cache_dir) == ".":
            cache_dir = None

    if cache_dir is None:
        cache_dir = Path("~/.paper-scanner").expanduser()
    else:
        cache_dir = cache_dir.expanduser()

    if verbose:
        console.print(f"Cache directory: [cyan]{cache_dir}[/cyan]")
        console.print(f"Target: [yellow]{target}[/yellow]")

    if target == "checkpoints":
        checkpoints_dir = cache_dir / "checkpoints"

        if checkpoints_dir.exists():
            shutil.rmtree(checkpoints_dir)
            console.print(f"[green]✓ Cleared checkpoints[/green]: {_collapse_home(checkpoints_dir)}")
        else:
            console.print("[green]✓ No checkpoints to clear[/green] (directory is clean)")

        return 0

    elif target == "pdfs":
        pdfs_dir = cache_dir / "pdfs"

        if pdfs_dir.exists():
            shutil.rmtree(pdfs_dir)
            console.print(f"[green]✓ Cleared PDFs[/green]: {_collapse_home(pdfs_dir)}")
        else:
            console.print("[green]✓ No PDFs to clear[/green] (directory is clean)")

        return 0

    return 1


def execute_cache_load(
    folder_path: str,
    cache_dir: Optional[Path] = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Load PDFs from folder into cache, indexed by DOI.

    Pre-fills PDF cache from local folder to avoid API downloads during
    later processing. Extracts DOI from each PDF and caches it.

    Args:
        folder_path: Path to folder containing PDF files
        cache_dir: Cache directory (default: ~/.paper-scanner)
        verbose: Enable verbose output
        dry_run: Don't actually cache files

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import os

    # Determine cache_dir
    if cache_dir is None:
        cache_dir = Path(os.getenv("CACHE_DIR", ""))
        if not cache_dir or str(cache_dir) == ".":
            cache_dir = None

    if cache_dir is None:
        cache_dir = Path("~/.paper-scanner").expanduser()
    else:
        cache_dir = cache_dir.expanduser()

    # Validate and expand folder path
    folder = Path(folder_path).expanduser()

    if not folder.exists() or not folder.is_dir():
        console.print(f"[red]✗ Error[/red]: Folder does not exist or is not a directory: {folder}")
        return 1

    # Scan for PDF files
    pdf_files = sorted(folder.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]⚠ No PDF files found[/yellow] in {_collapse_home(folder)}")
        return 0

    if verbose:
        console.print(f"Loading {len(pdf_files)} PDFs into cache...\n")

    # Initialize cache
    pdf_cache = PDFCache(cache_dir=cache_dir / "pdfs")

    # Track results
    cached = 0
    skipped = 0
    errors = 0
    failed_items = []

    # Process each PDF
    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            # Read file and extract DOI
            file_reader = FileReader(pdf_path)

            if not file_reader.exists():
                skipped += 1
                if verbose:
                    console.print(
                        f" [dim]{i}/{len(pdf_files)}[/dim] {pdf_path.name}: [yellow]PDF not found[/yellow]"
                    )
                continue

            # Extract DOI
            doi = file_reader.extract_doi()

            if not doi:
                skipped += 1
                if verbose:
                    console.print(
                        f" [dim]{i}/{len(pdf_files)}[/dim] {pdf_path.name}: [dim]skipped (no DOI)[/dim]"
                    )
                continue

            # Cache the PDF
            if not dry_run:
                pdf_cache.set(doi, pdf_path, move=False)

            cached += 1

            if verbose:
                console.print(
                    f" [green]✓[/green] {i}/{len(pdf_files)} {pdf_path.name} → {doi}"
                )

        except Exception as e:
            errors += 1
            failed_items.append((pdf_path.name, str(e)[:80]))
            if verbose:
                console.print(
                    f" [red]✗[/red] {i}/{len(pdf_files)} {pdf_path.name}: [red]{str(e)[:50]}[/red]"
                )

    # Summary
    console.print()
    if errors == 0:
        console.print(
            f"[green]✓ Success[/green]: Cached {cached} PDFs, skipped {skipped} (no DOI)"
        )
    else:
        console.print(
            f"[yellow]⚠ Completed with errors[/yellow]: {cached} cached, {skipped} skipped, {errors} errors"
        )
        if verbose and failed_items:
            console.print("\n[red]Failed items:[/red]")
            for name, error in failed_items:
                console.print(f"  • {name}: {error}")

    return 1 if errors > 0 else 0
