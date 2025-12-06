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

        # Stage 0 stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN stage0_exclusion_reason IS NOT NULL THEN 1 END) as failed,
            COUNT(CASE WHEN stage0_exclusion_reason LIKE 'rejected_paper_type%' THEN 1 END) as rejected_type,
            COUNT(CASE WHEN stage0_exclusion_reason = 'duplicate' THEN 1 END) as rejected_dup,
            COUNT(CASE WHEN stage0_exclusion_reason = 'review_paper' THEN 1 END) as rejected_review,
            COUNT(CASE WHEN stage0_exclusion_reason = 'conceptual_paper' THEN 1 END) as rejected_conceptual,
            MIN(stage0_processed_at) as earliest,
            MAX(stage0_processed_at) as latest
        FROM paper_screening
        WHERE stage0_processed_at IS NOT NULL;
        """)
        s0 = cursor.fetchone()
        total_s0 = s0['total'] or 0
        failed_s0 = s0['failed'] or 0
        stats['stage0'] = {
            'processed': total_s0,
            'passed': total_s0 - failed_s0,
            'failed': failed_s0,
            'rejected_type': s0['rejected_type'] or 0,
            'rejected_dup': s0['rejected_dup'] or 0,
            'rejected_review': s0['rejected_review'] or 0,
            'rejected_conceptual': s0['rejected_conceptual'] or 0,
            'earliest': s0['earliest'],
            'latest': s0['latest']
        }

        # Stage 1 stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN stage1_exclusion_reason IS NOT NULL THEN 1 END) as failed,
            MIN(stage1_processed_at) as earliest,
            MAX(stage1_processed_at) as latest
        FROM paper_screening
        WHERE stage1_processed_at IS NOT NULL;
        """)
        s1 = cursor.fetchone()
        total_s1 = s1['total'] or 0
        failed_s1 = s1['failed'] or 0
        stats['stage1'] = {
            'processed': total_s1,
            'passed': total_s1 - failed_s1,
            'failed': failed_s1,
            'earliest': s1['earliest'],
            'latest': s1['latest']
        }

        # Stage 2 stats
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN stage2_exclusion_reason IS NULL AND stage2_processed_at IS NOT NULL THEN 1 END) as included,
            COUNT(CASE WHEN screening_stage = 'stage2_review' THEN 1 END) as review,
            COUNT(CASE WHEN stage2_exclusion_reason IS NOT NULL THEN 1 END) as excluded,
            ROUND(AVG(semantic_similarity)::numeric, 4) as avg_similarity,
            MIN(semantic_similarity) as min_similarity,
            MAX(semantic_similarity) as max_similarity,
            MIN(stage2_processed_at) as earliest,
            MAX(stage2_processed_at) as latest,
            COUNT(CASE WHEN needs_manual_review = true THEN 1 END) as manual_review_count
        FROM paper_screening
        WHERE stage2_processed_at IS NOT NULL
          AND stage1_exclusion_reason IS NULL;
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

        # Paper type analysis (2D: paper_type vs acceptance/pending/rejection)
        cursor.execute("""
        SELECT 
            COALESCE(p.paper_type, 'Unknown') as paper_type,
            COUNT(*) as total,
            COUNT(CASE WHEN ps.stage2_exclusion_reason IS NULL AND ps.stage2_processed_at IS NOT NULL THEN 1 END) as included,
            COUNT(CASE WHEN ps.screening_stage = 'stage2_review' THEN 1 END) as pending,
            COUNT(CASE WHEN ps.stage2_exclusion_reason IS NOT NULL THEN 1 END) as excluded,
            COUNT(CASE WHEN ps.stage0_exclusion_reason IS NOT NULL THEN 1 END) as stage0_rejected,
            COUNT(CASE WHEN ps.stage1_exclusion_reason IS NOT NULL THEN 1 END) as stage1_rejected,
            COUNT(CASE WHEN ps.stage2_exclusion_reason IS NOT NULL THEN 1 END) as stage2_rejected
        FROM papers p
        LEFT JOIN paper_screening ps ON p.id = ps.paper_id
        GROUP BY p.paper_type
        ORDER BY total DESC
        """)
        paper_type_analysis = cursor.fetchall()
        stats['paper_type_analysis'] = [dict(row) for row in paper_type_analysis]

        # Papers per year (total and final pass/review)
        cursor.execute("""
        SELECT 
            p.year,
            COUNT(*) as total_count,
            COUNT(CASE WHEN ps.screening_stage IN ('stage2_pass', 'stage2_review') THEN 1 END) as final_count
        FROM papers p
        LEFT JOIN paper_screening ps ON p.id = ps.paper_id
        WHERE p.year IS NOT NULL
        GROUP BY p.year
        ORDER BY p.year ASC;
        """)
        papers_by_year = cursor.fetchall()
        stats['papers_by_year'] = [dict(row) for row in papers_by_year]

        cursor.close()
        return stats

    def create_year_histogram(self, stats: Dict) -> None:
        """Display ASCII histogram of papers per year with total and final pass/review counts merged."""
        papers_by_year = stats.get('papers_by_year', [])
        
        if not papers_by_year:
            return
        
        console.print()
        console.print("[bold cyan]📈 Papers per Year (Total vs Final Pass/Review)[/bold cyan]")
        
        # Get max counts for scaling and alignment
        max_total = max(row['total_count'] for row in papers_by_year) if papers_by_year else 1
        max_total_width = len(str(max_total))
        
        # Create histogram with fixed width for bars
        bar_width = 40
        
        # Calculate total line width
        total_width = 4 + 3 + bar_width + 3 + (max_total_width * 2 + 3)
        
        # Header
        numbers_header = f"{'Total':>{max_total_width}} / {'Pass':>{max_total_width}}"
        console.print(f"{'Year':>4} │ {'Merged View':<{bar_width}} │ {numbers_header}")
        console.print("─" * total_width)
        
        for row in papers_by_year:
            year = row['year']
            total_count = row['total_count']
            final_count = row['final_count'] or 0
            
            # Calculate bar lengths (proportional to max total)
            if max_total > 0:
                total_bar_length = int((total_count / max_total) * bar_width)
                final_bar_length = int((final_count / max_total) * bar_width)
            else:
                total_bar_length = 0
                final_bar_length = 0
            
            # Build the bar character by character without color codes first
            bar_chars = []
            
            # Add green bars for pass/review
            for i in range(final_bar_length):
                bar_chars.append("[green]█[/green]")
            
            # Add cyan bars for others
            for i in range(total_bar_length - final_bar_length):
                bar_chars.append("[cyan]█[/cyan]")
            
            # Add spaces to pad to bar_width
            remaining = bar_width - total_bar_length
            bar_chars.extend([" "] * remaining)
            
            # Join the bar
            bar_display = "".join(bar_chars)
            
            # Format numbers
            numbers_display = f"{total_count:>{max_total_width}} / {final_count:>{max_total_width}}"
            
            # Format the line
            line = f"{year:4d} │ {bar_display} │ {numbers_display}"
            console.print(line)
        
        # Print scale reference at bottom
        console.print("─" * total_width)
        
        # Legend
        console.print("[green]█[/green] = Pass/Review | [cyan]█[/cyan] = Other papers")

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
        s0_processed = stats['stage0']['processed']
        s1_processed = stats['stage1']['processed']
        s2_processed = stats['stage2']['processed']
        
        s0_pct = f"{100*s0_processed/total:.1f}%" if total > 0 else "0%"
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

Stage 0 (Type/Duplicate Filter):   [bold magenta]{s0_processed:,}[/bold magenta] processed ({s0_pct})
Stage 1 (Keyword Filtering):       [bold yellow]{s1_processed:,}[/bold yellow] processed ({s1_pct})
Stage 2 (Semantic Filtering):      [bold cyan]{s2_processed:,}[/bold cyan] processed ({s2_pct})
"""
        
        console.print(Panel(overview_text.strip(), expand=False, border_style="cyan"))

    def display_stage0(self, stats: Dict) -> None:
        """Display Stage 0 results."""
        s0 = stats['stage0']
        total = s0['processed']
        
        if total == 0:
            console.print("[yellow]⚠️  Stage 0 not yet executed[/yellow]\n")
            return
        
        passed_pct = 100 * s0['passed'] / total
        failed_pct = 100 * s0['failed'] / total
        
        # Build rejection breakdown
        rejection_text = ""
        if s0['rejected_type'] > 0:
            pct = 100 * s0['rejected_type'] / total
            rejection_text += f"\n    • Wrong citation type:    {s0['rejected_type']:4d} ({pct:5.1f}%)"
        if s0['rejected_dup'] > 0:
            pct = 100 * s0['rejected_dup'] / total
            rejection_text += f"\n    • Duplicates:             {s0['rejected_dup']:4d} ({pct:5.1f}%)"
        if s0['rejected_review'] > 0:
            pct = 100 * s0['rejected_review'] / total
            rejection_text += f"\n    • Literature reviews:     {s0['rejected_review']:4d} ({pct:5.1f}%)"
        if s0['rejected_conceptual'] > 0:
            pct = 100 * s0['rejected_conceptual'] / total
            rejection_text += f"\n    • Conceptual/theoretical: {s0['rejected_conceptual']:4d} ({pct:5.1f}%)"
        
        # Create summary text
        summary = f"""
[bold magenta]✓ Stage 0: Quality Filter (Type/Duplicate/Method)[/bold magenta]
[dim]Goal: Remove non-empirical papers, duplicates, and non-peer-reviewed works[/dim]

[bold]Results:[/bold]
  [green]✓ PASSED[/green]  (Empirical peer-reviewed) {s0['passed']:4d} papers  ({passed_pct:5.1f}%)
  [red]✗ FAILED[/red]  (Excluded)                {s0['failed']:4d} papers  ({failed_pct:5.1f}%)
  ────────────────────
  Total:                              {total:4d} papers

[bold]Rejection Breakdown:[/bold]{rejection_text}

[bold]Timeline:[/bold]
  Started:  {self.format_time_ago(s0['earliest']) if s0['earliest'] else 'Never'}
  Latest:   {self.format_time_ago(s0['latest']) if s0['latest'] else 'Never'}
"""
        
        console.print(Panel(summary.strip(), expand=False, border_style="magenta", title="Stage 0"))

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
        s0 = stats['stage0']
        s1 = stats['stage1']
        s2 = stats['stage2']
        
        table = Table(title="📋 Detailed Screening Statistics", show_header=True, header_style="bold")
        table.add_column("Stage", style="cyan")
        table.add_column("Processed", justify="right", style="green")
        table.add_column("Passed/Included", justify="right", style="green")
        table.add_column("Failed/Excluded", justify="right", style="red")
        table.add_column("Pending Review", justify="right", style="yellow")
        table.add_column("Status", style="white")
        
        s0_status = "✓ Complete" if s0['processed'] > 0 else "⏳ Pending"
        s0_style = "green" if s0['processed'] > 0 else "yellow"
        table.add_row(
            "Stage 0",
            str(s0['processed']),
            str(s0['passed']),
            str(s0['failed']),
            "-",
            f"[{s0_style}]{s0_status}[/{s0_style}]"
        )
        
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
        
        # Explain the filtering funnel
        s0 = stats['stage0']
        s1 = stats['stage1']
        s2 = stats['stage2']
        
        funnel_explanation = f"""
[dim]📊 Filtering Funnel Explanation:[/dim]
  Start:           {s0['processed']:4d} papers (all papers processed at Stage 0)
  → Stage 0 Pass:  {s0['passed']:4d} papers (removed {s0['failed']:4d} non-empirical/duplicates)
  → Stage 1 Pass:  {s1['passed']:4d} papers (removed {s1['failed']:4d} keyword-irrelevant)
  → Stage 2 In:    {s2['processed']:4d} papers (note: may differ from Stage 1 pass if some papers skipped Stage 2)
     ├─ Included:  {s2['included']:4d} papers
     ├─ Pending:   {s2['review']:4d} papers (manual review needed)
     └─ Excluded:  {s2['excluded']:4d} papers
"""
        console.print(funnel_explanation)

    def display_recommendations(self, stats: Dict) -> None:
        """Display recommendations based on current state."""
        s0 = stats['stage0']
        s1 = stats['stage1']
        s2 = stats['stage2']
        total = stats['total_papers']
        
        console.print()
        
        recommendations = []
        
        if total == 0:
            recommendations.append("[yellow]Load papers from BibTeX file[/yellow]")
        elif s0['processed'] == 0:
            recommendations.append("[yellow]Run Stage 0 (quality filter: type/duplicates/empirical)[/yellow]")
        elif s1['processed'] == 0:
            recommendations.append("[yellow]Run Stage 1 (keyword screening)[/yellow]")
        elif s2['processed'] == 0:
            recommendations.append("[yellow]Run Stage 2 (semantic filtering)[/yellow]")
        else:
            if s2['review'] > 0:
                recommendations.append(f"[yellow]Review {s2['review']} borderline papers (0.55-0.65 similarity)[/yellow]")
            recommendations.append("[green]All screening stages complete![/green]")
            if s2['review'] > 0:
                recommendations.append("[cyan]Next: Run Stage 3 (LLM classification for borderline papers)[/cyan]")
        
        recommendation_text = "\n".join(recommendations)
        console.print(Panel(recommendation_text, expand=False, border_style="blue", title="💡 Recommendations"))

    def display_key_metrics(self, stats: Dict) -> None:
        """Display key performance metrics."""
        s0 = stats['stage0']
        s1 = stats['stage1']
        s2 = stats['stage2']
        
        if s0['processed'] == 0 and s1['processed'] == 0 and s2['processed'] == 0:
            return
        
        console.print()
        
        # Create metrics table
        metrics_table = Table(show_header=True, header_style="bold magenta", title="📈 Key Metrics")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", justify="right", style="yellow")
        
        # Stage 0 pass rate
        if s0['processed'] > 0:
            s0_pass_rate = 100 * s0['passed'] / s0['processed']
            metrics_table.add_row("Stage 0 Pass Rate", f"{s0_pass_rate:.1f}%")
        
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
        if s0['processed'] > 0 and s1['processed'] > 0 and s2['processed'] > 0:
            # Papers that passed all stages
            total_passed = s2['included']  # Those that passed Stage 2 as "pass"
            overall_rate = 100 * total_passed / s0['processed']
            metrics_table.add_row("Overall Inclusion (all stages)", f"{overall_rate:.1f}%")
        
        console.print(metrics_table)

    def display_paper_type_analysis(self, stats: Dict) -> None:
        """Display 2D analysis of paper_type vs acceptance/rejection rates."""
        paper_type_data = stats.get('paper_type_analysis', [])
        
        if not paper_type_data:
            return
        
        console.print()
        
        # Create table
        table = Table(
            title="📊 Paper Type Analysis (Current Screening Status)",
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Paper Type", style="cyan", width=25)
        table.add_column("Total", justify="right", style="white")
        table.add_column("Advancing", justify="right", style="green")
        table.add_column("% Adv.", justify="right", style="green")
        table.add_column("Pending", justify="right", style="yellow")
        table.add_column("% Pend.", justify="right", style="yellow")
        table.add_column("Rejected", justify="right", style="red")
        table.add_column("% Rej.", justify="right", style="red")
        table.add_column("S0 Rej", justify="right", style="dim")
        
        for row in paper_type_data:
            paper_type = row['paper_type'] or 'Unknown'
            total = row['total']
            included = row['included'] or 0
            excluded = row['excluded'] or 0
            pending = row['pending'] or 0
            stage0_rejected = row['stage0_rejected'] or 0
            
            # Calculate percentages
            pct_included = 100 * included / total if total > 0 else 0
            pct_pending = 100 * pending / total if total > 0 else 0
            pct_excluded = 100 * excluded / total if total > 0 else 0
            
            # Truncate paper type if too long
            paper_type_display = paper_type[:23] if len(paper_type) > 23 else paper_type
            
            table.add_row(
                paper_type_display,
                str(total),
                str(included),
                f"{pct_included:.1f}%",
                str(pending),
                f"{pct_pending:.1f}%",
                str(excluded),
                f"{pct_excluded:.1f}%",
                str(stage0_rejected)
            )
        
        console.print(table)

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
            self.display_stage0(stats)
            self.display_stage1(stats)
            self.display_stage2(stats)
            self.display_detailed_table(stats)
            self.display_key_metrics(stats)
            self.display_paper_type_analysis(stats)
            self.create_year_histogram(stats)
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
