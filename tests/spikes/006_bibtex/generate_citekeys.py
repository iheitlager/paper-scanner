#!/usr/bin/env python3
"""
Generate Citekeys for Papers

Creates citekeys for papers where:
- file_path is NOT NULL (file exists)
- citekey is NULL (not yet assigned)

Naming strategy:
1. If authors exist: {first_author_lastname}{year}
2. If no authors: {random_8_char_code}

Usage:
    python generate_citekeys.py [--db-url <url>] [--dry-run]

Examples:
    # Generate citekeys
    python generate_citekeys.py

    # Dry run to see what would be generated
    python generate_citekeys.py --dry-run

    # Custom database
    python generate_citekeys.py --db-url "postgresql://user:pass@host/db"
"""

import argparse
import os
import random
import string
import sys

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()


class CitekeyGenerator:
    """Generate and assign citekeys for papers."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None

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

    def get_papers_needing_citekeys(self):
        """Get all papers where file_path is set but citekey is NULL."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        query = """
        SELECT
            id,
            file_path,
            file_name,
            title,
            year,
            authors,
            doi,
            citekey
        FROM papers
        WHERE file_path IS NOT NULL
          AND (citekey IS NULL OR citekey = '')
        ORDER BY year DESC, id ASC
        """

        try:
            cursor.execute(query)
            papers = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in papers] if papers else []
        except psycopg2.Error as e:
            console.print(f"[red]Query failed: {e}[/red]")
            cursor.close()
            return []

    def generate_citekey(self, paper: dict) -> str:
        """
        Generate a citekey for a paper.

        Strategy (in order):
        1. If authors exist: {first_author_lastname}{year}
        2. If DOI exists: Use last part of DOI
        3. If file exists: Use first part of filename
        4. Otherwise: Generate random 8-character code
        """
        # Try 1: Use first author and year
        authors = paper.get("authors")
        year = paper.get("year")

        if authors and isinstance(authors, list) and len(authors) > 0:
            first_author = authors[0]
            if isinstance(first_author, dict):
                last_name = first_author.get("last_name", "").lower()
                if last_name and year:
                    return f"{last_name}{year}"
                elif last_name:
                    return last_name

        # Try 2: Use DOI
        doi = paper.get("doi")
        if doi:
            # Use last meaningful part of DOI, simplified
            parts = doi.split("/")
            if len(parts) > 1:
                doi_part = parts[-1].replace(".", "").replace("(", "").replace(")", "")[:12]
                if doi_part:
                    return f"doi{doi_part}"

        # Try 3: Use file path
        file_path = paper.get("file_path")
        if file_path:
            # Extract filename without extension and clean it
            filename = file_path.split("/")[-1].replace(".pdf", "")
            # Take first 12 chars of filename
            if filename and len(filename) > 3:
                return filename[:12]

        # Fallback: Generate random code with year if available
        if year:
            random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
            return f"auto{year}{random_part}"
        else:
            random_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
            return f"auto{random_code}"

    def update_citekey(self, paper_id: int, citekey: str, dry_run: bool = False) -> bool:
        """Update citekey in database."""
        if dry_run:
            return True

        cursor = self.conn.cursor()

        query = """
        UPDATE papers
        SET citekey = %s, updated_at = NOW()
        WHERE id = %s
        """

        try:
            cursor.execute(query, (citekey, paper_id))
            self.conn.commit()
            cursor.close()
            return True
        except psycopg2.Error as e:
            console.print(f"[red]Error updating paper {paper_id}: {e}[/red]")
            self.conn.rollback()
            cursor.close()
            return False

    def process_papers(self, dry_run: bool = False) -> dict:
        """
        Generate and assign citekeys for all papers that need them.

        Returns: statistics dictionary
        """
        papers = self.get_papers_needing_citekeys()

        if not papers:
            console.print("[yellow]⚠️  No papers found needing citekeys[/yellow]")
            return {"total": 0, "processed": 0, "failed": 0}

        console.print()
        console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
        console.print("[bold cyan]🔑 CITEKEY GENERATOR[/bold cyan]")
        console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
        console.print()

        if dry_run:
            console.print("[bold yellow]⚠️  DRY RUN MODE - No changes will be made[/bold yellow]")
            console.print()

        console.print(f"[bold]Papers to process:[/bold] {len(papers)}")
        console.print()

        # Create results table
        table = Table(show_header=True, header_style="bold cyan", border_style="cyan")
        table.add_column("Paper ID", style="green", width=10)
        table.add_column("Title", style="white", width=50)
        table.add_column("Year", justify="right", width=6)
        table.add_column("Generated Citekey", style="yellow", width=25)
        table.add_column("Status", style="magenta", width=10)

        stats = {"total": len(papers), "processed": 0, "failed": 0}

        for paper in papers:
            paper_id = paper["id"]
            title = paper["title"]
            if title and len(title) > 50:
                title = title[:47] + "..."

            generated_citekey = self.generate_citekey(paper)

            # Try to update
            success = self.update_citekey(paper_id, generated_citekey, dry_run=dry_run)

            if success:
                stats["processed"] += 1
                status = "✓ OK" if not dry_run else "✓ Preview"
                status_color = "green"
            else:
                stats["failed"] += 1
                status = "✗ Failed"
                status_color = "red"

            table.add_row(
                str(paper_id),
                title or "(no title)",
                str(paper.get("year") or "-"),
                generated_citekey,
                f"[{status_color}]{status}[/{status_color}]",
            )

        console.print(table)
        console.print()

        # Summary
        console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
        console.print("[bold cyan]📊 SUMMARY[/bold cyan]")
        console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
        console.print()

        summary_table = Table(show_header=False, border_style="blue")
        summary_table.add_column("Metric", style="cyan", width=25)
        summary_table.add_column("Count", justify="right", style="bold yellow")

        summary_table.add_row("[bold]Total papers processed[/bold]", str(stats["total"]))
        summary_table.add_row("[green]✓ Successfully updated[/green]", str(stats["processed"]))
        if stats["failed"] > 0:
            summary_table.add_row("[red]✗ Failed[/red]", str(stats["failed"]))

        console.print(summary_table)
        console.print()

        if dry_run:
            console.print("[bold yellow]DRY RUN - No changes were made[/bold yellow]")

        console.print()

        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate citekeys for papers with file_path but no citekey",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate citekeys
  python generate_citekeys.py

  # Dry run to preview
  python generate_citekeys.py --dry-run

  # Custom database
  python generate_citekeys.py --db-url "postgresql://user:pass@host/db"

Naming strategy:
  1. If authors exist: {first_author_lastname}{year}
     Example: smith2023, johnson2022

  2. If no authors: {random_code}
     Example: auto2023abc1, autoPQR8T2X
        """,
    )

    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"),
        help="PostgreSQL connection URL (default: env DATABASE_URL or localhost)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Create generator
    generator = CitekeyGenerator(args.db_url)

    try:
        if not generator.connect():
            sys.exit(1)

        stats = generator.process_papers(dry_run=args.dry_run)

        sys.exit(0 if stats["failed"] == 0 else 1)

    except KeyboardInterrupt:
        console.print()
        console.print("[bold yellow]⏸️  Interrupted (CTRL-C)[/bold yellow]")
        console.print()
        sys.exit(0)

    finally:
        generator.disconnect()


if __name__ == "__main__":
    main()
