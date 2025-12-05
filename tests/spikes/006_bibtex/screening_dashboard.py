#!/usr/bin/env python3
"""
Screening Dashboard - Visual Overview of Paper Screening Results

Displays comprehensive statistics about the paper screening pipeline
with rich formatting, colors, and tables for easy interpretation.

Usage:
    python screening_dashboard.py [--db-url <url>] [--refresh]
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Load environment
load_dotenv()

# Initialize console
console = Console()


class ScreeningDashboard:
    """Display screening pipeline statistics."""

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

    def get_stats(self) -> Dict:
        """Get comprehensive screening statistics."""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        stats = {}

        # Total papers
        cursor.execute("SELECT COUNT(*) as count FROM papers;")
        stats['total_papers'] = cursor.fetchone()['count']

        # Papers by source
        cursor.execute("""
        SELECT 
            COALESCE(source_details->>'source', 'Unknown') as source,
            COUNT(*) as count
        FROM papers
        GROUP BY source_details->>'source'
        ORDER BY count DESC;
        """)
        sources = cursor.fetchall()
        stats['sources'] = {row['source']: row['count'] for row in sources}

        # Stage 1 stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN screening_stage = 'stage1_pass' THEN 1 END) as passed,
            COUNT(CASE WHEN screening_stage = 'stage1_fail' THEN 1 END) as failed,
            MIN(stage1_processed_at) as earliest,
            MAX(stage1_processed_at) as latest
        FROM paper_screening
        WHERE stage1_processed_at IS NOT NULL;
        """)
        s1 = cursor.fetchone()
        stats['stage1'] = {
            'processed': s1['total'] or 0,
            'passed': s1['passed'] or 0,
            'failed': s1['failed'] or 0,
            'earliest': s1['earliest'],
            'latest': s1['latest']
        }

        # Stage 2 stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN screening_stage = 'stage2_pass' THEN 1 END) as included,
            COUNT(CASE WHEN screening_stage = 'stage2_review' THEN 1 END) as review,
            COUNT(CASE WHEN screening_stage = 'stage2_fail' THEN 1 END) as excluded,
            ROUND(AVG(semantic_similarity)::numeric, 4) as avg_similarity,
            MIN(semantic_similarity) as min_similarity,
            MAX(semantic_similarity) as max_similarity,
            MIN(stage2_processed_at) as earliest,
            MAX(stage2_processed_at) as latest,
            COUNT(CASE WHEN needs_manual_review = true THEN 1 END) as manual_review_count
        FROM paper_screening
        WHERE stage2_processed_at IS NOT NULL;
        """)
        s2 = cursor.fetchone()
        stats['stage2'] = {
            'processed': s2['total'] or 0,
            'included': s2['included'] or 0,
            'review': s2['review'] or 0,
            'excluded': s2['excluded'] or 0,
            'avg_similarity': float(s2['avg_similarity']) if s2['avg_similarity'] else 0,
            'min_similarity': float(s2['min_similarity']) if s2['min_similarity'] else 0,
            'max_similarity': float(s2['max_similarity']) if s2['max_similarity'] else 0,
            'earliest': s2['earliest'],
            'latest': s2['latest'],
            'manual_review_count': s2['manual_review_count'] or 0
        }

        # Similarity distribution
        cursor.execute("""
        SELECT 
            COUNT(CASE WHEN semantic_similarity >= 0.65 THEN 1 END) as high,
            COUNT(CASE WHEN semantic_similarity >= 0.55 AND semantic_similarity < 0.65 THEN 1 END) as medium,
            COUNT(CASE WHEN semantic_similarity >= 0.45 AND semantic_similarity < 0.55 THEN 1 END) as low,
            COUNT(CASE WHEN semantic_similarity < 0.45 THEN 1 END) as very_low
        FROM paper_screening
        WHERE semantic_similarity IS NOT NULL;
        """)
        dist = cursor.fetchone()
        stats['similarity_dist'] = {
            'high': dist['high'] or 0,
            'medium': dist['medium'] or 0,
            'low': dist['low'] or 0,
            'very_low': dist['very_low'] or 0
        }

        # Overall status
        cursor.execute("""
        SELECT 
            COUNT(CASE WHEN final_decision = 'included' THEN 1 END) as final_included,
            COUNT(CASE WHEN final_decision = 'excluded' THEN 1 END) as final_excluded,
            COUNT(CASE WHEN final_decision = 'pending_review' THEN 1 END) as final_pending
        FROM paper_screening;
        """)
        final = cursor.fetchone()
        stats['final'] = {
            'included': final['final_included'] or 0,
            'excluded': final['final_excluded'] or 0,
            'pending': final['final_pending'] or 0
        }

        cursor.close()
        return stats

    def format_time_ago(self, dt: Optional[datetime]) -> str:
        """Format datetime as time ago."""
        if not dt:
            return "Never"
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:
            mins = int(diff.total_seconds() / 60)
            return f"{mins}m ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}d ago"

    def display_overview(self, stats: Dict) -> None:
        """Display overview panel."""
        console.print()
        
        total = stats['total_papers']
        s1_processed = stats['stage1']['processed']
        s2_processed = stats['stage2']['processed']
        
        s1_pct = f"{100*s1_processed/total:.1f}%" if total > 0 else "0%"
        s2_pct = f"{100*s2_processed/total:.1f}%" if total > 0 else "0%"
        
        # Build source breakdown
        source_text = ""
        if stats.get('sources'):
            for source, count in sorted(stats['sources'].items(), key=lambda x: x[1], reverse=True):
                pct = f"{100*count/total:.1f}%" if total > 0 else "0%"
                source_text += f"\n  • {source}: {count:,} ({pct})"
        
        overview_text = f"""
[bold cyan]📊 PAPER SCREENING PIPELINE OVERVIEW[/bold cyan]

Total Papers in Database:        [bold]{total:,}[/bold]{source_text}

Stage 1 (Keyword Filtering):     [bold yellow]{s1_processed:,}[/bold yellow] processed ({s1_pct})
Stage 2 (Semantic Filtering):    [bold cyan]{s2_processed:,}[/bold cyan] processed ({s2_pct})
"""
        
        console.print(Panel(overview_text.strip(), expand=False, border_style="cyan"))

    def display_stage1(self, stats: Dict) -> None:
        """Display Stage 1 results."""
        s1 = stats['stage1']
        total = s1['processed']
        
        if total == 0:
            console.print("[yellow]⚠️  Stage 1 not yet executed[/yellow]\n")
            return
        
        passed_pct = 100 * s1['passed'] / total
        failed_pct = 100 * s1['failed'] / total
        
        # Create summary text
        summary = f"""
[bold green]✓ Stage 1: Coarse Filter (Keyword-Based)[/bold green]
[dim]Goal: Remove obviously irrelevant papers (Precision ~70%, Recall ~95%)[/dim]

[bold]Results:[/bold]
  [green]✓ PASSED[/green]  (Include)    {s1['passed']:4d} papers  ({passed_pct:5.1f}%)
  [red]✗ FAILED[/red]  (Exclude)    {s1['failed']:4d} papers  ({failed_pct:5.1f}%)
  ────────────────────
  Total:              {total:4d} papers

[bold]Timeline:[/bold]
  Started:  {self.format_time_ago(s1['earliest']) if s1['earliest'] else 'Never'}
  Latest:   {self.format_time_ago(s1['latest']) if s1['latest'] else 'Never'}
"""
        
        console.print(Panel(summary.strip(), expand=False, border_style="yellow", title="Stage 1"))

    def display_stage2(self, stats: Dict) -> None:
        """Display Stage 2 results."""
        s2 = stats['stage2']
        dist = stats['similarity_dist']
        total = s2['processed']
        
        if total == 0:
            console.print("[yellow]⚠️  Stage 2 not yet executed[/yellow]\n")
            return
        
        included_pct = 100 * s2['included'] / total
        review_pct = 100 * s2['review'] / total
        excluded_pct = 100 * s2['excluded'] / total
        
        # Create summary text
        summary = f"""
[bold cyan]✓ Stage 2: Semantic Filter (Embedding-Based)[/bold cyan]
[dim]Goal: Find semantically similar papers (Precision ~85%, Recall ~90%)[/dim]

[bold]Classification Results:[/bold]
  [bold green]✓ INCLUDE[/bold green]         (≥ 0.65)      {s2['included']:4d} papers  ({included_pct:5.1f}%)
  [bold yellow]⚠ MANUAL REVIEW[/bold yellow]  (0.55-0.65)  {s2['review']:4d} papers  ({review_pct:5.1f}%)
  [bold red]✗ EXCLUDE[/bold red]        (< 0.55)      {s2['excluded']:4d} papers  ({excluded_pct:5.1f}%)
  ────────────────────
  Total:                   {total:4d} papers

[bold]Similarity Statistics:[/bold]
  Average:  {s2['avg_similarity']:.4f}
  Range:    {s2['min_similarity']:.4f} → {s2['max_similarity']:.4f}
  
[bold]Similarity Distribution:[/bold]
  ≥ 0.65:   {dist['high']:4d} papers  [green]{'█' * max(1, int(dist['high'] * 50 / max(total, 1))):<50}[/green]
  0.55-0.65: {dist['medium']:4d} papers  [yellow]{'█' * max(1, int(dist['medium'] * 50 / max(total, 1))):<50}[/yellow]
  0.45-0.55: {dist['low']:4d} papers  [dim]{'█' * max(1, int(dist['low'] * 50 / max(total, 1))):<50}[/dim]
  < 0.45:   {dist['very_low']:4d} papers  [dim]{'█' * max(1, int(dist['very_low'] * 50 / max(total, 1))):<50}[/dim]

[bold]Timeline:[/bold]
  Started:  {self.format_time_ago(s2['earliest']) if s2['earliest'] else 'Never'}
  Latest:   {self.format_time_ago(s2['latest']) if s2['latest'] else 'Never'}
"""
        
        console.print(Panel(summary.strip(), expand=False, border_style="cyan", title="Stage 2"))

    def display_detailed_table(self, stats: Dict) -> None:
        """Display detailed statistics table."""
        s1 = stats['stage1']
        s2 = stats['stage2']
        
        table = Table(title="📋 Detailed Screening Statistics", show_header=True, header_style="bold")
        table.add_column("Stage", style="cyan")
        table.add_column("Processed", justify="right", style="green")
        table.add_column("Passed/Included", justify="right", style="green")
        table.add_column("Failed/Excluded", justify="right", style="red")
        table.add_column("Pending Review", justify="right", style="yellow")
        table.add_column("Status", style="white")
        
        s1_status = "✓ Complete" if s1['processed'] > 0 else "⏳ Pending"
        s1_style = "green" if s1['processed'] > 0 else "yellow"
        table.add_row(
            "Stage 1",
            str(s1['processed']),
            str(s1['passed']),
            str(s1['failed']),
            "-",
            f"[{s1_style}]{s1_status}[/{s1_style}]"
        )
        
        s2_status = "✓ Complete" if s2['processed'] > 0 else "⏳ Pending"
        s2_style = "green" if s2['processed'] > 0 else "yellow"
        table.add_row(
            "Stage 2",
            str(s2['processed']),
            str(s2['included']),
            str(s2['excluded']),
            str(s2['review']),
            f"[{s2_style}]{s2_status}[/{s2_style}]"
        )
        
        console.print(table)
        console.print()

    def display_recommendations(self, stats: Dict) -> None:
        """Display recommendations based on current state."""
        s1 = stats['stage1']
        s2 = stats['stage2']
        total = stats['total_papers']
        
        console.print()
        
        recommendations = []
        
        if total == 0:
            recommendations.append("[yellow]Load papers from BibTeX file[/yellow]")
        elif s1['processed'] == 0:
            recommendations.append("[yellow]Run Stage 1 (keyword screening)[/yellow]")
        elif s2['processed'] == 0:
            recommendations.append("[yellow]Run Stage 2 (semantic filtering)[/yellow]")
        else:
            if s2['review'] > 0:
                recommendations.append(f"[yellow]Review {s2['review']} borderline papers (0.55-0.65 similarity)[/yellow]")
            recommendations.append("[green]Both stages complete![/green]")
            if s2['review'] > 0:
                recommendations.append("[cyan]Next: Run Stage 3 (LLM classification for borderline papers)[/cyan]")
        
        recommendation_text = "\n".join(recommendations)
        console.print(Panel(recommendation_text, expand=False, border_style="blue", title="💡 Recommendations"))

    def display_key_metrics(self, stats: Dict) -> None:
        """Display key performance metrics."""
        s1 = stats['stage1']
        s2 = stats['stage2']
        
        if s1['processed'] == 0 and s2['processed'] == 0:
            return
        
        console.print()
        
        # Create metrics table
        metrics_table = Table(show_header=True, header_style="bold magenta", title="📈 Key Metrics")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", justify="right", style="yellow")
        
        # Stage 1 pass rate
        if s1['processed'] > 0:
            s1_pass_rate = 100 * s1['passed'] / s1['processed']
            metrics_table.add_row("Stage 1 Pass Rate", f"{s1_pass_rate:.1f}%")
        
        # Stage 2 inclusion rate
        if s2['processed'] > 0:
            s2_include_rate = 100 * s2['included'] / s2['processed']
            metrics_table.add_row("Stage 2 Inclusion Rate", f"{s2_include_rate:.1f}%")
            
            # Manual review rate
            s2_review_rate = 100 * s2['review'] / s2['processed']
            metrics_table.add_row("Manual Review Rate", f"{s2_review_rate:.1f}%")
            
            # Average similarity
            metrics_table.add_row("Average Similarity", f"{s2['avg_similarity']:.4f}")
        
        # Overall inclusion (if all stages done)
        if s1['processed'] > 0 and s2['processed'] > 0:
            # Papers that passed both stages
            total_passed = s2['included']  # Those that passed Stage 2 as "pass"
            overall_rate = 100 * total_passed / s1['processed']
            metrics_table.add_row("Overall Inclusion", f"{overall_rate:.1f}%")
        
        console.print(metrics_table)

    def run(self) -> None:
        """Run the dashboard."""
        if not self.connect():
            return
        
        try:
            # Header
            console.print()
            console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
            console.print("[bold cyan]🔬 PAPER SCREENING DASHBOARD[/bold cyan]")
            console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
            
            # Fetch stats with progress indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                progress.add_task("Fetching statistics...", total=None)
                stats = self.get_stats()
            
            # Display sections
            self.display_overview(stats)
            self.display_stage1(stats)
            self.display_stage2(stats)
            self.display_detailed_table(stats)
            self.display_key_metrics(stats)
            self.display_recommendations(stats)
            
            # Footer
            console.print("[bold cyan]" + "="*80 + "[/bold cyan]")
            console.print(f"[dim]Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
            console.print()
            
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Screening Pipeline Dashboard")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfuser@localhost/pdfdb"),
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=0,
        help="Auto-refresh every N seconds (0 = no refresh)"
    )
    
    args = parser.parse_args()
    
    load_dotenv()
    
    dashboard = ScreeningDashboard(args.db_url)
    
    try:
        if args.refresh > 0:
            import time
            while True:
                dashboard.run()
                console.print(f"\n[dim]Refreshing in {args.refresh} seconds... (Ctrl+C to stop)[/dim]")
                time.sleep(args.refresh)
        else:
            dashboard.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard closed[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
