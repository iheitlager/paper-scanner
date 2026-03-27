"""
Database management CLI tasks.

Provides commands for database statistics and management.
Uses environment variables for sensitive configuration (via dotenv).

Configuration supports two modes:
1. Direct database URL:
   --database-url "postgresql://user:password@localhost:5432/pdfdb"

2. Environment variables:
   Sets DATABASE_URL via .env file or command line
   Falls back to individual components: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
"""

import os
import sys
from pathlib import Path
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table


def execute_db_stats(
    database_url: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    console: Optional[Console] = None,
    verbose: bool = False,
) -> int:
    """
    Display database statistics overview.

    Shows record counts for main tables: papers and citations.
    Supports configuration via:
    - Explicit database_url parameter
    - Environment variables (DATABASE_URL or individual components)

    Args:
        database_url: PostgreSQL connection URL (optional, uses env if not provided)
        cache_dir: Cache directory (unused but for consistency with task interface)
        console: Optional Rich console instance (uses stderr by default)
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if console is None:
        console = Console(file=sys.stderr)

    try:
        # Load environment variables from .env file
        load_dotenv()

        # Get database URL
        if not database_url:
            database_url = _get_database_url(database_url)

        if not database_url:
            console.print("[red]Error: Could not determine database URL[/red]")
            console.print("[dim]Provide --database-url or set DATABASE_URL environment variable[/dim]")
            return 1

        if verbose:
            console.print(f"[dim]Connecting to database: {database_url.split('@')[-1] if '@' in database_url else 'unknown'}[/dim]")

        # Connect to database
        try:
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
        except psycopg2.Error as e:
            console.print("[red]Error: Failed to connect to database[/red]")
            console.print(f"[dim]{str(e)}[/dim]")
            return 1

        try:
            if verbose:
                console.print("[cyan]Querying database statistics...[/cyan]")

            # Query record counts
            cursor.execute("SELECT COUNT(*) FROM papers")
            papers_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM citation_edges")
            citations_count = cursor.fetchone()[0]

            # Get additional statistics
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT year) as unique_years,
                    MIN(year) as earliest_year,
                    MAX(year) as latest_year,
                    COUNT(CASE WHEN manually_validated THEN 1 END) as validated_count
                FROM papers
                WHERE year IS NOT NULL
            """)
            stats = cursor.fetchone()
            unique_years, earliest_year, latest_year, validated_count = stats or (0, None, None, 0)

            cursor.execute("""
                SELECT COUNT(*) FROM paper_screening
                WHERE final_decision IS NOT NULL
            """)
            screened_count = cursor.fetchone()[0]

            # Create table
            table = Table(title="Database Statistics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", style="green", justify="right")

            table.add_row("Papers", str(papers_count))
            table.add_row("Citation Edges", str(citations_count))
            table.add_row("Screened Papers", str(screened_count))
            table.add_row("Validated Papers", str(validated_count))

            if unique_years and unique_years > 0:
                table.add_row("Year Range", f"{earliest_year} - {latest_year}")
                table.add_row("Unique Years", str(unique_years))

            console.print()
            console.print(table)
            console.print()

            if verbose:
                console.print("[green]✓ Database statistics retrieved successfully[/green]")

            return 0

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def _get_database_url(explicit_url: Optional[str] = None) -> Optional[str]:
    """
    Construct or retrieve database URL from configuration.

    Supports three modes:
    1. Explicit parameter (passed directly)
    2. DATABASE_URL environment variable
    3. Individual components: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

    Environment variables are loaded via dotenv.

    Args:
        explicit_url: Explicitly provided database URL

    Returns:
        Full PostgreSQL connection string or None if invalid
    """
    # Mode 1: Explicit URL provided
    if explicit_url:
        if explicit_url.startswith("$"):
            # Environment variable reference
            env_var = explicit_url[1:]
            url = os.environ.get(env_var)
            return url
        return explicit_url

    # Mode 2: DATABASE_URL environment variable
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # Mode 3: Build from components
    username = _resolve_env_var(os.environ.get("DB_USER"))
    password = _resolve_env_var(os.environ.get("DB_PASSWORD"))
    host = _resolve_env_var(os.environ.get("DB_HOST"))
    port = _resolve_env_var(os.environ.get("DB_PORT"))
    db_name = _resolve_env_var(os.environ.get("DB_NAME"))

    if all([username, password, host, port, db_name]):
        return f"postgresql://{username}:{password}@{host}:{port}/{db_name}"

    return None


def _resolve_env_var(value: Optional[str]) -> Optional[str]:
    """
    Resolve value as either literal or environment variable reference.

    Args:
        value: Either a literal value or "$ENV_VAR_NAME"

    Returns:
        Resolved value or None if not found
    """
    if not value:
        return None

    if value.startswith("$"):
        env_var = value[1:]
        resolved = os.environ.get(env_var)
        return resolved

    return value


# All tables that can be cleared (from init-db.sql schema)
CLEARABLE_TABLES = [
    "paper_cluster_assignments",
    "paper_clusters",
    "paper_tags",
    "tags",
    "processing_logs",
    "chunk_embeddings",
    "paper_embeddings",
    "paper_chunks",
    "paper_analysis",
    "citation_edges",
    "paper_screening",
    "papers",
]


def execute_db_clear(
    target: str = "all",
    database_url: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    console: Optional[Console] = None,
    verbose: bool = False,
    dry_run: bool = False,
) -> int:
    """
    Clear records from database tables.

    Supports clearing:
    - "all": All tables (respecting foreign key dependencies)
    - Specific table name: Only that table

    Args:
        target: "all" or specific table name
        database_url: PostgreSQL connection URL (optional, uses env if not provided)
        cache_dir: Cache directory (unused but for consistency with task interface)
        console: Optional Rich console instance (uses stderr by default)
        verbose: Enable verbose output
        dry_run: Show what would be cleared without actually doing it

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if console is None:
        console = Console(file=sys.stderr)

    try:
        # Load environment variables from .env file
        load_dotenv()

        # Validate target
        if target != "all" and target not in CLEARABLE_TABLES:
            console.print(f"[red]Error: Unknown table '{target}'[/red]")
            console.print(f"[dim]Available tables: {', '.join(CLEARABLE_TABLES)}[/dim]")
            return 1

        # Get database URL
        if not database_url:
            database_url = _get_database_url(database_url)

        if not database_url:
            console.print("[red]Error: Could not determine database URL[/red]")
            console.print("[dim]Provide --database-url or set DATABASE_URL environment variable[/dim]")
            return 1

        if verbose:
            console.print(f"[dim]Connecting to database: {database_url.split('@')[-1] if '@' in database_url else 'unknown'}[/dim]")

        # Connect to database
        try:
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
        except psycopg2.Error as e:
            console.print("[red]Error: Failed to connect to database[/red]")
            console.print(f"[dim]{str(e)}[/dim]")
            return 1

        try:
            tables_to_clear = CLEARABLE_TABLES if target == "all" else [target]

            if dry_run:
                console.print("[yellow]DRY RUN:[/yellow] The following tables would be cleared:")
                for table in tables_to_clear:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    console.print(f"  [cyan]{table}[/cyan]: {count} records")
                console.print("[dim]Run without --dry-run to actually clear these tables[/dim]")
                return 0

            if verbose:
                console.print(f"[cyan]Clearing {len(tables_to_clear)} table(s)...[/cyan]")

            # Disable foreign key constraints temporarily
            cursor.execute("SET session_replication_role = 'replica'")

            cleared_tables = []
            total_records = 0

            for table in tables_to_clear:
                try:
                    # Get count before clearing
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]

                    if count > 0:
                        cursor.execute(f"DELETE FROM {table}")
                        cleared_tables.append((table, count))
                        total_records += count

                        if verbose:
                            console.print(f"[green]✓[/green] Cleared {count} records from [cyan]{table}[/cyan]")
                except psycopg2.Error as e:
                    console.print(f"[red]Error clearing {table}:[/red] {str(e)}")
                    cursor.execute("SET session_replication_role = 'origin'")
                    conn.rollback()
                    return 1

            # Re-enable foreign key constraints
            cursor.execute("SET session_replication_role = 'origin'")
            conn.commit()

            # Display summary
            console.print()
            if cleared_tables:
                table = Table(title="Database Clear Summary", show_header=True, header_style="bold cyan")
                table.add_column("Table", style="cyan")
                table.add_column("Records Cleared", style="green", justify="right")

                for table_name, count in cleared_tables:
                    table.add_row(table_name, str(count))

                console.print(table)
                console.print(f"[green]Total: {total_records} records cleared[/green]")
            else:
                console.print("[dim]No records to clear[/dim]")
            console.print()

            return 0

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


