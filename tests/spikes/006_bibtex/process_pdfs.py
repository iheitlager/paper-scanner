#!/usr/bin/env python3
"""
PDF to DOI Matcher - Reverse Workflow

Process existing PDFs in papers directory:
1. Extract DOI from PDF metadata or content
2. Match to database records
3. Reformat DOI (replace /.: with _)
4. Rename file with DOI-based name
5. Update database file_path reference

Usage:
    python process_pdfs.py [--trial <filename>] [--db-url <url>]

Examples:
    # Trial run on one file
    python process_pdfs.py --trial "initiating-open-innovation-collaborations-between-incumbents-and-startups-how-can-david-and-goliath-get-along.pdf"
    
    # Process all PDFs
    python process_pdfs.py
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# Try to import PDF libraries
try:
    import pypdf

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

load_dotenv()
console = Console()


class DOIExtractor:
    """Extract DOI from PDF using multiple methods."""

    def __init__(self, email: str = None):
        self.email = email or os.environ.get("RESEARCHER_EMAIL", "iheitlager@tue.nl")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'PDFDOIExtractor/1.0 (mailto:{self.email})'
        })

    def extract_from_pdf(self, pdf_path: Path) -> Optional[str]:
        """
        Extract DOI from PDF using multiple methods.
        
        Returns:
            DOI string if found, None otherwise
        """
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
                    return doi
            except Exception:
                pass

        return None

    def _extract_from_metadata(self, pdf_path: Path) -> Optional[str]:
        """Extract DOI from PDF metadata."""
        if not HAS_PYPDF:
            return None

        try:
            with open(pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
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
        except Exception:
            pass

        return None

    def _extract_from_content(self, pdf_path: Path) -> Optional[str]:
        """Extract DOI from PDF text content using regex."""
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
            except Exception:
                pass

        # Fallback: try PyPDF2
        if HAS_PYPDF:
            try:
                with open(pdf_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                    # Search first 3 pages
                    for page_num in range(min(3, len(reader.pages))):
                        page = reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            doi = self._extract_doi_from_text(text)
                            if doi:
                                return doi
            except Exception:
                pass

        return None

    def _extract_doi_from_text(self, text: str) -> Optional[str]:
        """Extract DOI from plain text using regex."""
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
                doi = re.sub(r'[.,;)\s]*$', '', doi)
                # Validate DOI format
                if doi.startswith('10.') and '/' in doi:
                    return doi

        return None

    def _extract_from_title_lookup(self, pdf_path: Path) -> Optional[str]:
        """
        Try to extract title and lookup DOI via Crossref.
        
        This is a fallback method when DOI is not directly in PDF.
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
                        reader = pypdf.PdfReader(f)
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
                            return doi
                except Exception:
                    pass

        except Exception:
            pass

        return None


class PDFDatabaseManager:
    """Manage PDF processing and database updates."""

    def __init__(self, db_url: str, papers_dir: str = "../papers"):
        self.db_url = db_url
        self.papers_dir = Path(papers_dir).expanduser()
        self.conn = None
        self.extractor = DOIExtractor()

    def connect(self) -> bool:
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(self.db_url)
            return True
        except psycopg2.Error as e:
            console.print(f"[red]❌ Connection failed: {e}[/red]")
            return False

    def disconnect(self) -> None:
        """Close connection."""
        if self.conn:
            self.conn.close()

    def get_pdf_files(self) -> list:
        """Get all PDF files in papers directory."""
        if not self.papers_dir.exists():
            return []

        return sorted(self.papers_dir.glob("*.pdf"))

    def find_doi_in_database(self, doi: str) -> Optional[Dict]:
        """Find paper record by DOI (case-insensitive)."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT 
            p.id,
            p.citekey,
            p.doi,
            p.title,
            p.year,
            p.file_path,
            p.file_name
        FROM papers p
        WHERE LOWER(p.doi) = LOWER(%s)
        LIMIT 1
        """

        try:
            cursor.execute(query, (doi,))
            result = cursor.fetchone()
            cursor.close()
            return dict(result) if result else None
        except psycopg2.Error as e:
            console.print(f"[red]Database query error: {e}[/red]")
            cursor.close()
            return None

    def reformat_doi(self, doi: str) -> str:
        """Reformat DOI: replace /.: with _"""
        return re.sub(r'[/.:]+', '_', doi)

    def process_pdf(self, pdf_path: Path, dry_run: bool = False) -> Dict:
        """
        Process a single PDF:
        1. Extract DOI
        2. Look up in database
        3. Rename file with DOI
        4. Update database record
        
        Returns: status dictionary
        """
        result = {
            'filename': pdf_path.name,
            'success': False,
            'doi_extracted': None,
            'doi_found': None,
            'db_match': False,
            'file_path_was_set': False,
            'renamed': False,
            'db_updated': False,
            'error': None,
            'actions': []
        }

        # Step 1: Extract DOI from PDF
        console.print("[cyan]Extracting DOI...[/cyan]")
        doi = self.extractor.extract_from_pdf(pdf_path)

        if not doi:
            result['error'] = 'Could not extract DOI from PDF'
            console.print(f"[red]✗ {result['error']}[/red]")
            return result

        result['doi_extracted'] = doi
        console.print(f"[green]✓ DOI extracted:[/green] {doi}")

        # Step 2: Look up in database
        console.print("[cyan]Looking up in database...[/cyan]")
        db_record = self.find_doi_in_database(doi)

        if not db_record:
            result['error'] = f'DOI not found in database: {doi}'
            console.print(f"[yellow]⚠️  {result['error']}[/yellow]")
            return result

        result['db_match'] = True
        result['doi_found'] = db_record['doi']
        result['file_path_was_set'] = bool(db_record['file_path'])
        console.print(f"[green]✓ Database match found:[/green] {db_record['citekey']}")

        # Step 3: Prepare new filename
        reformatted_doi = self.reformat_doi(doi)
        new_filename = f"{reformatted_doi}.pdf"
        new_filepath = self.papers_dir / new_filename

        # Step 4: Check if already renamed
        if pdf_path.name == new_filename:
            result['actions'].append('File already has DOI-based name')
            console.print("[blue]ℹ️  File already named with DOI[/blue]")
        else:
            # Rename file
            if not dry_run:
                try:
                    pdf_path.rename(new_filepath)
                    result['renamed'] = True
                    result['actions'].append(f'Renamed: {pdf_path.name} → {new_filename}')
                    console.print("[green]✓ File renamed[/green]")
                except Exception as e:
                    result['error'] = f'Failed to rename file: {e}'
                    console.print(f"[red]✗ {result['error']}[/red]")
                    return result

        # Step 5: Update database if file_path not set or file changed
        if not result['file_path_was_set'] or result['renamed']:
            cursor = self.conn.cursor()

            update_query = """
            UPDATE papers
            SET file_path = %s, updated_at = NOW()
            WHERE id = %s
            """

            try:
                if not dry_run:
                    cursor.execute(update_query, (str(new_filepath), db_record['id']))
                    self.conn.commit()

                result['db_updated'] = True
                result['actions'].append(f'Updated DB: file_path → {new_filepath}')
                console.print("[green]✓ Database record updated[/green]")
            except psycopg2.Error as e:
                result['error'] = f'Failed to update database: {e}'
                console.print(f"[red]✗ {result['error']}[/red]")
                self.conn.rollback()
                cursor.close()
                return result
            finally:
                cursor.close()

        result['success'] = True
        console.print("[bold green]✓ Processing complete![/bold green]")
        return result

    def process_all_pdfs(self, trial_filename: Optional[str] = None, dry_run: bool = False) -> Dict:
        """
        Process all PDFs or single trial file.
        
        Args:
            trial_filename: If provided, process only this file
            dry_run: If True, don't make changes
            
        Returns: summary statistics
        """
        pdfs = self.get_pdf_files()

        if not pdfs:
            console.print("[yellow]⚠️  No PDF files found in papers directory[/yellow]")
            return {}

        # Filter to trial file if specified
        if trial_filename:
            pdfs = [p for p in pdfs if p.name == trial_filename]
            if not pdfs:
                console.print(f"[red]✗ Trial file not found: {trial_filename}[/red]")
                return {}

        # Display header
        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print("[bold cyan]📄 PDF DOI PROCESSOR[/bold cyan]")
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print()

        if dry_run:
            console.print("[bold yellow]⚠️  DRY RUN MODE - No changes will be made[/bold yellow]")
            console.print()

        console.print(f"[bold]Source directory:[/bold] {self.papers_dir.resolve()}")
        console.print(f"[bold]PDFs to process:[/bold] {len(pdfs)}")
        console.print()

        # Process PDFs
        stats = {
            'total': len(pdfs),
            'processed': 0,
            'renamed': 0,
            'db_updated': 0,
            'db_match': 0,
            'errors': 0,
            'details': []
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("", total=len(pdfs))

            for i, pdf_path in enumerate(pdfs, 1):
                # Display current file
                status_text = f"""[cyan]{pdf_path.name:<60}[/cyan] ({i}/{len(pdfs)})
  [dim]Processing...[/dim]"""
                progress.update(task, description=status_text)

                console.print()
                console.print(f"[bold]File {i}/{len(pdfs)}:[/bold] {pdf_path.name}")
                console.print("-" * 80)

                result = self.process_pdf(pdf_path, dry_run=dry_run)

                stats['details'].append(result)

                if result['success']:
                    stats['processed'] += 1
                    if result['renamed']:
                        stats['renamed'] += 1
                    if result['db_updated']:
                        stats['db_updated'] += 1
                    if result['db_match']:
                        stats['db_match'] += 1
                else:
                    stats['errors'] += 1

                # Update progress display
                status_text = f"""[cyan]{pdf_path.name:<60}[/cyan] ({i}/{len(pdfs)})
  [dim]Status: {"✓ Success" if result["success"] else "✗ Failed"}[/dim]"""
                progress.update(task, description=status_text)
                progress.advance(task)

        # Display summary
        self._display_summary(stats, dry_run)

        return stats

    def _display_summary(self, stats: Dict, dry_run: bool) -> None:
        """Display processing summary."""
        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print("[bold cyan]📊 PROCESSING SUMMARY[/bold cyan]")
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
        console.print()

        # Summary table
        table = Table(show_header=False, border_style="blue")
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Count", justify="right", style="bold yellow")

        table.add_row("[bold]Total PDFs[/bold]", str(stats['total']))
        table.add_row("[green]✓ Successfully Processed[/green]", str(stats['processed']))
        table.add_row("[cyan]Files Renamed[/cyan]", str(stats['renamed']))
        table.add_row("[blue]Database Records Updated[/blue]", str(stats['db_updated']))
        table.add_row("[magenta]Database Matches Found[/magenta]", str(stats['db_match']))
        table.add_row("[red]✗ Errors[/red]", str(stats['errors']))

        console.print(table)

        # Detailed results
        if stats['details']:
            console.print()
            console.print("[bold]Detailed Results:[/bold]")
            console.print()

            results_table = Table(show_header=True, header_style="bold magenta", border_style="magenta")
            results_table.add_column("Filename", style="cyan", width=40)
            results_table.add_column("DOI", style="green", width=30)
            results_table.add_column("Status", style="yellow", width=12)
            results_table.add_column("Actions", style="white", width=35)

            for detail in stats['details']:
                status = "✓ OK" if detail['success'] else "✗ Error"
                status_color = "green" if detail['success'] else "red"

                actions_str = "\n".join(detail['actions']) if detail['actions'] else (
                    detail['error'] if detail['error'] else "N/A"
                )

                # Truncate filename and DOI for display
                filename_display = detail['filename'][:40]
                doi_display = (detail['doi_extracted'] or "N/A")[:30]

                results_table.add_row(
                    f"[{status_color}]{filename_display}[/{status_color}]",
                    f"[dim]{doi_display}[/dim]",
                    f"[{status_color}]{status}[/{status_color}]",
                    actions_str
                )

            console.print(results_table)

        console.print()
        console.print("[bold cyan]" + "="*80 + "[/bold cyan]")

        if dry_run:
            console.print("[bold yellow]DRY RUN - No changes were made[/bold yellow]")

        console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Process PDFs: Extract DOI, match to database, rename files, update records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trial on single file
  python process_pdfs.py --trial "initiating-open-innovation-collaborations-between-incumbents-and-startups-how-can-david-and-goliath-get-along.pdf"
  
  # Process all PDFs
  python process_pdfs.py
  
  # Dry run to see what would change
  python process_pdfs.py --dry-run
        """
    )

    parser.add_argument(
        "--trial",
        help="Process only this specific filename (trial mode)"
    )

    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfuser@localhost/pdfdb"),
        help="PostgreSQL connection URL (default: env DATABASE_URL or localhost)"
    )

    parser.add_argument(
        "--papers-dir",
        default="../papers",
        help="Path to papers directory (default: ../papers)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    # Check for PDF parsing libraries
    if not HAS_PYPDF and not HAS_PDFPLUMBER:
        console.print("[red]✗ Error: PyPDF2 or pdfplumber required[/red]")
        console.print("  Install with: pip install PyPDF2 pdfplumber")
        sys.exit(1)

    # Create manager
    manager = PDFDatabaseManager(args.db_url, args.papers_dir)

    try:
        if not manager.connect():
            sys.exit(1)

        stats = manager.process_all_pdfs(trial_filename=args.trial, dry_run=args.dry_run)

        sys.exit(0 if stats.get('errors', 0) == 0 else 1)

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]⏸️  Processing interrupted (CTRL-C)[/bold yellow]")
        console.print()
        sys.exit(0)

    finally:
        manager.disconnect()


if __name__ == "__main__":
    main()
