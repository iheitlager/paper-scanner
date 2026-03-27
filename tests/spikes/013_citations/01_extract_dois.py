#!/usr/bin/env python3
"""
Script to extract DOIs from PDF files in tests/data directory.
Tests both FileReader and pdfplumber extraction methods with detailed debugging.
"""

import re
import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pdfplumber
from rich.console import Console
from rich.table import Table

from paper_scanner.tools.documents import FileReader

console = Console()

def extract_doi_from_text(text: str) -> Optional[str]:
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
            # Clean up common artifacts
            doi = re.sub(r'[.,;)\s\]]*$', '', doi)
            # Validate DOI format
            if doi.startswith('10.') and '/' in doi:
                return doi.lower()

    return None

def extract_doi_with_pdfplumber(pdf_path: Path) -> Optional[str]:
    """
    Extract DOI using pdfplumber (alternative method for debugging).

    Args:
        pdf_path: Path to PDF file

    Returns:
        DOI string if found, None otherwise
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Search first 3 pages for DOI
            for page_num, page in enumerate(pdf.pages[:3]):
                text = page.extract_text()
                if text:
                    doi = extract_doi_from_text(text)
                    if doi:
                        return doi
    except Exception as e:
        console.print(f"    [dim]pdfplumber failed: {e}[/dim]")

    return None

def main():
    """Scan PDFs and extract DOIs."""
    pdf_dir = Path(__file__).parent.parent.parent / "data"

    if not pdf_dir.exists():
        console.print(f"[red]✗[/red] Directory not found: {pdf_dir}")
        return

    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]⚠️  No PDF files found in {pdf_dir}[/yellow]")
        return

    console.print(f"\n[bold]Extracting DOIs from {len(pdf_files)} PDF files[/bold]\n")

    # Create table
    table = Table(title="DOI Extraction Results")
    table.add_column("Filename", style="cyan")
    table.add_column("FileReader DOI", style="green")
    table.add_column("pdfplumber DOI", style="blue")
    table.add_column("Status", style="magenta")

    success_count = 0
    fail_count = 0
    anomalies = []

    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            file_reader = FileReader(pdf_path)

            if not file_reader.exists():
                table.add_row(pdf_path.name, "-", "-", "[red]File not found[/red]")
                fail_count += 1
                continue

            # Try FileReader first
            doi_filereader = file_reader.extract_doi()

            # Try pdfplumber as fallback
            doi_pdfplumber = extract_doi_with_pdfplumber(pdf_path)

            # Determine status
            if doi_filereader and doi_pdfplumber:
                if doi_filereader == doi_pdfplumber:
                    status = "[green]✓ Match[/green]"
                else:
                    status = "[yellow]⚠️  Mismatch[/yellow]"
                    anomalies.append((pdf_path.name, doi_filereader, doi_pdfplumber))
                table.add_row(pdf_path.name, doi_filereader, doi_pdfplumber, status)
                success_count += 1
            elif doi_filereader:
                status = "[yellow]⚠️  FileReader only[/yellow]"
                table.add_row(pdf_path.name, doi_filereader, "-", status)
                success_count += 1
            elif doi_pdfplumber:
                status = "[cyan]ℹ️  pdfplumber only[/cyan]"
                table.add_row(pdf_path.name, "-", doi_pdfplumber, status)
                anomalies.append((pdf_path.name, "NONE", doi_pdfplumber))
                success_count += 1
            else:
                table.add_row(pdf_path.name, "-", "-", "[red]✗ No DOI found[/red]")
                fail_count += 1

        except Exception as e:
            table.add_row(pdf_path.name, "-", "-", f"[red]Error: {str(e)[:30]}[/red]")
            fail_count += 1

    console.print(table)
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total: {len(pdf_files)}")
    console.print(f"  [green]Success: {success_count}[/green]")
    console.print(f"  [red]Failed: {fail_count}[/red]")

    if anomalies:
        console.print(f"\n[yellow][bold]⚠️  Differences/Issues detected ({len(anomalies)}):[/bold][/yellow]")
        for filename, fr_doi, pdf_doi in anomalies:
            if fr_doi == "NONE":
                console.print(f"  • {filename}:")
                console.print("      FileReader: NOT FOUND")
                console.print(f"      pdfplumber: {pdf_doi}")
            else:
                console.print(f"  • {filename}:")
                console.print(f"      FileReader: {fr_doi}")
                console.print(f"      pdfplumber: {pdf_doi}")

    console.print()

if __name__ == "__main__":
    main()
