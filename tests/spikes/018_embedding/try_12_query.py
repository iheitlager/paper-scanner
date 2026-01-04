#!/usr/bin/env python
"""
Interactive Query Tool: "Who Says What?"

Uses Claude API to help interrogate the paper database about research findings,
methodologies, and claims. Combines LLM reasoning with vector similarity search
to find relevant papers and sections.

Usage:
    python try_12_query.py

Examples of questions:
    - "What do papers say about digital transformation?"
    - "Who discusses platform ecosystems?"
    - "What methodologies are used in digital business research?"
    - "Who found that digitalization creates new business models?"
    - "Compare how different papers view digital platforms"
"""

import os
import sys
from dotenv import load_dotenv

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
import anthropic
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Initialize rich console for colored output
console = Console()

# Load environment
load_dotenv()


def get_db_url():
    """Build database URL from env"""
    db_user = os.getenv("DB_USER", "pdfuser")
    db_password = os.getenv("DB_PASSWORD", "pdfpass")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "paper_scanner")
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class PaperQueryEngine:
    """Interactive query engine for "who says what" questions"""

    def __init__(self):
        self.conn = psycopg2.connect(get_db_url())
        register_vector(self.conn)
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-3-5-sonnet-20241022"
        self.load_papers()

    def load_papers(self):
        """Load papers and their info into memory"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT db_id, cite_key, title, year, journal, authors
            FROM papers
            ORDER BY year DESC, cite_key
        """
        )
        self.papers = {}
        for row in cursor.fetchall():
            db_id, cite_key, title, year, journal, authors = row
            self.papers[db_id] = {
                "cite_key": cite_key,
                "title": title,
                "year": year,
                "journal": journal,
                "authors": authors,
            }
        cursor.close()
        console.print(f"\n[green]✓[/green] Loaded [bold cyan]{len(self.papers)}[/bold cyan] papers from database")

    def search_similar_chunks(self, query_text: str, limit: int = 5) -> list:
        """Find similar chunks using vector search"""
        from sentence_transformers import SentenceTransformer

        # Generate embedding for query
        model = SentenceTransformer("all-mpnet-base-v2")
        query_embedding = model.encode(query_text)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                ce.id,
                p.db_id,
                p.cite_key,
                p.title,
                p.year,
                pc.section,
                pc.text,
                ce.embedding <=> %s::vector as distance
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_id = pc.db_id
            JOIN papers p ON pc.paper_db_id = p.db_id
            ORDER BY ce.embedding <=> %s::vector
            LIMIT %s
        """,
            (query_embedding, query_embedding, limit),
        )

        results = cursor.fetchall()
        cursor.close()

        return [
            {
                "chunk_id": r[0],
                "paper_db_id": r[1],
                "cite_key": r[2],
                "paper_title": r[3],
                "year": r[4],
                "section": r[5],
                "text": r[6][:500] + ("..." if len(r[6]) > 500 else ""),
                "distance": r[7],
            }
            for r in results
        ]

    def format_search_results(self, results: list) -> str:
        """Format search results for display"""
        if not results:
            return "[yellow]No relevant papers found.[/yellow]"

        output = []
        output.append("\n[bold magenta]📄 RELEVANT PAPERS & SECTIONS:[/bold magenta]")
        output.append("[dim]" + "=" * 80 + "[/dim]")

        for i, result in enumerate(results, 1):
            similarity_pct = (1 - result['distance']) * 100
            color = "green" if similarity_pct > 80 else "yellow" if similarity_pct > 60 else "white"
            output.append(f"\n[bold cyan]{i}.[/bold cyan] [bold]{result['cite_key']}[/bold] [dim]({result['year']})[/dim]")
            output.append(f"   [blue]Title:[/blue] {result['paper_title']}")
            output.append(f"   [blue]Section:[/blue] {result['section']}")
            output.append(f"   [blue]Similarity:[/blue] [{color}]{similarity_pct:.1f}%[/{color}]")
            output.append(f"   [blue]Content:[/blue] {result['text']}")
            output.append("[dim]" + "-" * 80 + "[/dim]")

        return "\n".join(output)

    def ask_claude_about_results(
        self, user_question: str, search_results: list, search_text: str
    ) -> str:
        """Ask Claude to synthesize findings from search results"""
        
        # Format papers info for context
        papers_context = "\n\n".join(
            [
                f"- {p['cite_key']} ({p['year']}): {p['title']}"
                for p in self.papers.values()
            ]
        )

        # Format search results for Claude
        results_context = "\n\n".join(
            [
                f"From {r['cite_key']} ({r['year']}):\n"
                f"Section: {r['section']}\n"
                f"Quote: {r['text']}"
                for r in search_results
            ]
        )

        prompt = f"""You are an academic research assistant helping with a literature review.
A user asked: "{user_question}"

We searched the database with: "{search_text}"

Available papers in database:
{papers_context}

Most relevant findings:
{results_context}

Based on these findings, provide a synthesis answer to the user's question about "who says what".
Format your response as:
1. Direct answer to the question (what the papers say)
2. Key findings from each paper (who says what)
3. Any patterns or contradictions you notice
4. Suggested follow-up questions for deeper exploration

Be specific about which papers make which claims."""

        # Use spinner while calling Claude
        spinner = Spinner("dots", text="[cyan]Claude is analyzing...[/cyan]")
        with Live(spinner, console=console, refresh_per_second=12.5):
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

        return message.content[0].text

    def interactive_session(self):
        """Run interactive query session"""
        help_panel = Panel(
            "[bold]📚 PAPER QUERY ENGINE: 'Who Says What?'[/bold]\n\n"
            "Use natural language to ask questions about what papers say.\n\n"
            "[cyan]Examples:[/cyan]\n"
            "  • 'What do papers say about digital transformation?'\n"
            "  • 'Who discusses platform ecosystems?'\n"
            "  • 'What methodologies are used?'\n"
            "  • 'Compare how papers view digitalization'\n\n"
            "[cyan]Commands:[/cyan]\n"
            "  [bold]exit[/bold] or [bold]quit[/bold] - Exit the program\n"
            "  [bold]papers[/bold] - List all loaded papers\n"
            "  [bold]help[/bold] - Show this help message",
            title="[bold magenta]Welcome[/bold magenta]",
            border_style="magenta"
        )
        console.print(help_panel)

        while True:
            try:
                console.print("[cyan]🔍 Your question:[/cyan]", end=" ", soft_wrap=True)
                sys.stdout.flush()
                line = sys.stdin.readline()
                if not line:
                    console.print("\n[yellow]👋 End of input. Goodbye![/yellow]")
                    break
                user_input = line.strip()
                
                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\n[yellow]👋 Goodbye![/yellow]")
                    break

                if user_input.lower() == "papers":
                    table = Table(title="📖 PAPERS IN DATABASE", show_header=True, header_style="bold magenta")
                    table.add_column("Cite Key", style="cyan")
                    table.add_column("Year", style="green")
                    table.add_column("Title", style="white")
                    for db_id, info in sorted(
                        self.papers.items(), key=lambda x: x[1]["year"], reverse=True
                    ):
                        table.add_row(
                            info['cite_key'],
                            str(info['year']),
                            info['title'][:60] + "..."
                        )
                    console.print(table)
                    continue

                if user_input.lower() == "help":
                    help_text = Panel(
                        "[bold cyan]COMMANDS:[/bold cyan]\n"
                        "  [bold]papers[/bold]    - List all loaded papers\n"
                        "  [bold]exit[/bold]      - Exit the program\n"
                        "  [bold]help[/bold]      - Show this help message\n\n"
                        "[bold cyan]QUESTION TYPES:[/bold cyan]\n"
                        "  • 'What do papers say about X?' → Finds papers discussing X\n"
                        "  • 'Who discusses X?' → Finds papers by topic\n"
                        "  • 'Compare X and Y' → Finds papers on both topics\n"
                        "  • 'What methodologies...' → Finds methodology sections",
                        title="[bold magenta]Help[/bold magenta]",
                        border_style="cyan"
                    )
                    console.print(help_text)
                    continue

                # Process question
                console.print("\n[bold blue]⏳ Searching papers and analyzing...[/bold blue]")

                # Step 1: Search for relevant chunks
                search_results = self.search_similar_chunks(user_input, limit=5)

                if not search_results:
                    console.print("[bold red]❌ No relevant papers found.[/bold red] Try a different question.")
                    continue

                # Display search results
                console.print(self.format_search_results(search_results))

                # Step 2: Ask Claude to synthesize
                synthesis = self.ask_claude_about_results(
                    user_input, search_results, user_input
                )

                synthesis_panel = Panel(
                    synthesis,
                    title="[bold magenta]📝 SYNTHESIS[/bold magenta]",
                    border_style="magenta"
                )
                console.print(synthesis_panel)

                # Suggested follow-up
                console.print("\n[cyan]💡 Tip: You can ask follow-up questions for deeper exploration![/cyan]")

            except KeyboardInterrupt:
                console.print("\n[yellow]👋 Interrupted. Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
                console.print("[dim]Please try another question.[/dim]")

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main entry point"""
    banner = Panel(
        "[bold cyan]🚀 INITIALIZING PAPER QUERY ENGINE[/bold cyan]",
        border_style="cyan"
    )
    console.print(banner)

    try:
        engine = PaperQueryEngine()
        console.print("\n[bold green]✅ Engine ready! Starting interactive session...[/bold green]")
        engine.interactive_session()

    except Exception as e:
        console.print(f"\n[bold red]❌ Error initializing engine:[/bold red] {e}")
        sys.exit(1)
    finally:
        try:
            engine.close()
        except:
            pass


if __name__ == "__main__":
    main()
