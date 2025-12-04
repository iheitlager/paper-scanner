#!/usr/bin/env python3
"""
Interactive Paper Explorer with Claude Sonnet

Rich console interface for exploring your paper collection using:
- Semantic search with embeddings
- Claude Sonnet for intelligent analysis
- Citation network navigation
- Cluster exploration

Usage:
    python paper_explorer.py
"""

import os
import sys

# Disable tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json

import numpy as np
import psycopg2
from anthropic import Anthropic
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from sentence_transformers import SentenceTransformer

# Load environment variables
load_dotenv()

# Initialize
console = Console()
anthropic = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
embedding_model = None  # Lazy load


class PaperExplorer:
    """Interactive paper exploration system"""

    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        register_vector(self.conn)
        self.current_paper = None
        self.conversation_history = []

        console.print(
            Panel.fit(
                "[bold cyan]🔬 Paper Explorer with Claude Sonnet[/bold cyan]\n"
                "Intelligent exploration of your research collection",
                border_style="cyan",
            )
        )

    def load_embedding_model(self):
        """Lazy load embedding model"""
        global embedding_model
        if embedding_model is None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task("Loading embedding model...", total=None)
                embedding_model = SentenceTransformer("all-mpnet-base-v2")
        return embedding_model

    def select_citekey_interactive(self) -> Optional[str]:
        """Interactive citekey selector with fuzzy search"""

        # Get all citekeys
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT citekey, title, year
            FROM papers
            ORDER BY citekey
        """)
        papers = cursor.fetchall()
        cursor.close()

        if not papers:
            console.print("[yellow]No papers available[/yellow]")
            return None

        # Start with all papers
        available = list(papers)

        console.print("\n[cyan]Interactive citekey selector[/cyan]")
        console.print("[dim]Type to filter, press Enter to select, Ctrl+C to cancel[/dim]\n")

        while True:
            # Display current options
            if len(available) > 10:
                console.print(f"[dim]Showing 1-10 of {len(available)} papers[/dim]")
                display_list = available[:10]
            else:
                display_list = available

            table = Table(box=box.ROUNDED, show_header=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Citekey", style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("Year", justify="center", width=6)

            for i, (citekey, title, year) in enumerate(display_list, 1):
                table.add_row(
                    str(i), citekey, title[:50] + "..." if len(title) > 50 else title, str(year) if year else "N/A"
                )

            console.print(table)
            console.print()

            # Get user input
            try:
                user_input = Prompt.ask("[cyan]Search or select (1-{})".format(len(display_list)), default="").strip()

                if not user_input:
                    console.print("[yellow]Cancelled[/yellow]")
                    return None

                # Check if it's a number (selection)
                try:
                    idx = int(user_input) - 1
                    if 0 <= idx < len(display_list):
                        selected_citekey = str(display_list[idx][0])
                        console.print(f"\n[green]✓ Selected: {selected_citekey}[/green]")
                        return selected_citekey
                    else:
                        console.print("[red]Invalid selection[/red]")
                        continue
                except ValueError:
                    # It's a search query - filter papers
                    search = user_input.lower()
                    available = [
                        p
                        for p in papers
                        if search in p[0].lower() or search in p[1].lower() or search in str(p[2]).lower()
                    ]

                    if not available:
                        console.print(f"[yellow]No papers matching '{search}'[/yellow]")
                        available = list(papers)

                    console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled[/yellow]")
                return None

    def get_paper_by_citekey(self, citekey: str) -> dict:
        """Load complete paper information"""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT 
                p.id, p.citekey, p.title, p.year, p.journal, p.authors,
                p.abstract, p.doi, p.keywords,
                pe.embedding
            FROM papers p
            LEFT JOIN paper_embeddings pe ON p.id = pe.paper_id 
                AND pe.embedding_method = 'aggregate_chunks'
            WHERE p.citekey = %s
        """,
            (citekey,),
        )

        result = cursor.fetchone()
        if not result:
            return None

        paper = {
            "id": result[0],
            "citekey": result[1],
            "title": result[2],
            "year": result[3],
            "journal": result[4],
            "authors": result[5],
            "abstract": result[6],
            "doi": result[7],
            "keywords": result[8],
            "embedding": np.array(result[9]) if result[9] is not None else None,
        }

        # Get reference count
        cursor.execute(
            """
            SELECT COUNT(*) FROM "references" WHERE source_paper_id = %s
        """,
            (paper["id"],),
        )
        paper["reference_count"] = cursor.fetchone()[0]

        # Get citation count
        cursor.execute(
            """
            SELECT COUNT(*) FROM citation_edges WHERE cited_paper_id = %s
        """,
            (paper["id"],),
        )
        paper["citation_count"] = cursor.fetchone()[0]

        # Get cluster
        cursor.execute(
            """
            SELECT c.cluster_name, pca.assignment_confidence
            FROM paper_cluster_assignments pca
            JOIN paper_clusters c ON pca.cluster_id = c.id
            WHERE pca.paper_id = %s
        """,
            (paper["id"],),
        )
        cluster_result = cursor.fetchone()
        if cluster_result:
            paper["cluster"] = cluster_result[0]
            paper["cluster_confidence"] = cluster_result[1]

        # Get chunks count
        cursor.execute(
            """
            SELECT COUNT(*) FROM paper_chunks WHERE paper_id = %s
        """,
            (paper["id"],),
        )
        paper["chunk_count"] = cursor.fetchone()[0]

        cursor.close()
        return paper

    def display_paper(self, paper: dict):
        """Display paper details in a rich format"""

        # Header
        console.print()
        console.print(Panel(f"[bold cyan]{paper['citekey']}[/bold cyan]", border_style="cyan"))

        # Title and basic info
        console.print(f"[bold]{paper['title']}[/bold]")
        console.print()

        # Authors
        if paper["authors"]:
            authors = paper["authors"]
            if isinstance(authors, list):
                author_names = [a.get("name", str(a)) for a in authors]
                console.print(f"👥 Authors: {', '.join(author_names)}")
            else:
                console.print(f"👥 Authors: {authors}")

        # Publication details
        info_parts = []
        if paper["year"]:
            info_parts.append(f"📅 {paper['year']}")
        if paper["journal"]:
            info_parts.append(f"📚 {paper['journal']}")
        if info_parts:
            console.print(" | ".join(info_parts))

        if paper["doi"]:
            console.print(f"🔗 DOI: {paper['doi']}")

        console.print()

        # Stats table
        stats_table = Table(show_header=False, box=box.SIMPLE)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        stats_table.add_row("References", str(paper["reference_count"]))
        stats_table.add_row("Citations (in collection)", str(paper["citation_count"]))
        stats_table.add_row("Chunks", str(paper["chunk_count"]))

        if "cluster" in paper:
            stats_table.add_row("Cluster", f"{paper['cluster']} ({paper.get('cluster_confidence', 0):.1%} confidence)")

        console.print(stats_table)
        console.print()

        # Abstract
        if paper["abstract"]:
            console.print(Panel(paper["abstract"], title="[bold]Abstract[/bold]", border_style="dim"))

    def search_papers(self, query: str, limit: int = 5) -> list:
        """Semantic search for papers"""

        model = self.load_embedding_model()

        with console.status("[cyan]Searching papers...[/cyan]"):
            query_embedding = model.encode(query)
            vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT 
                    p.citekey,
                    p.title,
                    p.year,
                    p.journal,
                    1 - (pe.embedding <=> %s::vector) as similarity
                FROM papers p
                JOIN paper_embeddings pe ON p.id = pe.paper_id
                WHERE pe.embedding_method = 'aggregate_chunks'
                ORDER BY pe.embedding <=> %s::vector
                LIMIT %s
            """,
                (vector_str, vector_str, limit),
            )

            results = cursor.fetchall()
            cursor.close()

        return results

    def find_similar_papers(self, paper_id: int, limit: int = 5) -> list:
        """Find papers similar to given paper"""

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                p2.citekey,
                p2.title,
                p2.year,
                1 - (pe1.embedding <=> pe2.embedding) as similarity
            FROM paper_embeddings pe1
            JOIN paper_embeddings pe2 ON pe2.paper_id != pe1.paper_id
            JOIN papers p2 ON pe2.paper_id = p2.id
            WHERE pe1.paper_id = %s
              AND pe1.embedding_method = 'aggregate_chunks'
              AND pe2.embedding_method = 'aggregate_chunks'
            ORDER BY pe1.embedding <=> pe2.embedding
            LIMIT %s
        """,
            (paper_id, limit),
        )

        results = cursor.fetchall()
        cursor.close()
        return results

    def get_paper_context(self, paper: dict) -> str:
        """Build context about a paper for Claude"""

        context_parts = [
            f"Paper: {paper['citekey']}",
            f"Title: {paper['title']}",
        ]

        if paper["year"]:
            context_parts.append(f"Year: {paper['year']}")

        if paper["journal"]:
            context_parts.append(f"Journal: {paper['journal']}")

        if paper["authors"]:
            authors = paper["authors"]
            if isinstance(authors, list):
                author_names = [a.get("name", str(a)) for a in authors]
                context_parts.append(f"Authors: {', '.join(author_names)}")

        if paper["abstract"]:
            context_parts.append(f"\nAbstract:\n{paper['abstract']}")

        if "cluster" in paper:
            context_parts.append(f"\nCluster: {paper['cluster']}")

        context_parts.append(f"\nReferences: {paper['reference_count']}")
        context_parts.append(f"Citations in collection: {paper['citation_count']}")

        return "\n".join(context_parts)

    def get_collection_context(self) -> str:
        """Get overview of entire collection"""

        cursor = self.conn.cursor()

        # Total papers
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_papers = cursor.fetchone()[0]

        # Year range
        cursor.execute("SELECT MIN(year), MAX(year) FROM papers WHERE year IS NOT NULL")
        min_year, max_year = cursor.fetchone()

        # Clusters
        cursor.execute("""
            SELECT cluster_name, paper_count 
            FROM paper_clusters 
            ORDER BY paper_count DESC
        """)
        clusters = cursor.fetchall()

        # Top journals
        cursor.execute("""
            SELECT journal, COUNT(*) as cnt
            FROM papers
            WHERE journal IS NOT NULL
            GROUP BY journal
            ORDER BY cnt DESC
            LIMIT 5
        """)
        journals = cursor.fetchall()

        cursor.close()

        context = [
            "Collection Overview:",
            f"- Total papers: {total_papers}",
            f"- Year range: {min_year} - {max_year}",
        ]

        if clusters:
            context.append("\nClusters:")
            for name, count in clusters:
                context.append(f"  - {name}: {count} papers")

        if journals:
            context.append("\nTop Journals:")
            for journal, count in journals:
                context.append(f"  - {journal}: {count} papers")

        return "\n".join(context)

    def ask_claude(self, question: str, context: str = None) -> str:
        """Ask Claude a question with context"""

        system_prompt = """You are a research assistant helping explore an academic paper collection. 
You have access to papers, their embeddings, citations, and clusters.

Be concise but informative. Use markdown formatting for readability.
When discussing papers, always mention their citekey.
Focus on insights and connections between papers."""

        messages = self.conversation_history.copy()

        user_message = question
        if context:
            user_message = f"{context}\n\n---\n\n{question}"

        messages.append({"role": "user", "content": user_message})

        with console.status("[cyan]Claude is thinking...[/cyan]"):
            response = anthropic.messages.create(
                model="claude-sonnet-4-20250514", max_tokens=2000, system=system_prompt, messages=messages
            )

        assistant_message = response.content[0].text

        # Update conversation history
        self.conversation_history.append(
            {
                "role": "user",
                "content": question,  # Store without context
            }
        )
        self.conversation_history.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def show_menu(self):
        """Display main menu"""

        console.print()
        console.print(
            Panel(
                "[bold]Commands:[/bold]\n"
                "  [cyan]search[/cyan]         - Search papers by topic\n"
                "  [cyan]search-detail[/cyan]  - Search with section-level matches\n"  # ADD THIS
                "  [cyan]view[/cyan]           - View paper details\n"
                "  [cyan]similar[/cyan]        - Find similar papers\n"
                "  [cyan]ask[/cyan]            - Ask Claude about current paper\n"
                "  [cyan]compare[/cyan]        - Compare two papers\n"
                "  [cyan]overview[/cyan]       - Collection overview\n"
                "  [cyan]clusters[/cyan]       - Browse clusters\n"
                "  [cyan]network[/cyan]        - Citation network analysis\n"
                "  [cyan]list[/cyan]           - List all papers (APA format)\n"
                "  [cyan]help[/cyan]           - Show this menu\n"
                "  [cyan]quit[/cyan]           - Exit",
                title="📚 Menu",
                border_style="blue",
            )
        )

    def cmd_search(self):
        """Search command with better filtering and display"""
        query = Prompt.ask("[cyan]Search query[/cyan]")

        # Get more results to show range
        results = self.search_papers(query, limit=20)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        # Calculate similarity statistics
        similarities = [r[4] for r in results]
        max_sim = max(similarities)
        min_sim = min(similarities)
        avg_sim = sum(similarities) / len(similarities)

        # Show similarity distribution
        console.print()
        console.print(f"[dim]Found {len(results)} papers[/dim]")
        console.print(f"[dim]Similarity range: {min_sim:.1%} - {max_sim:.1%} (avg: {avg_sim:.1%})[/dim]")

        # Filter by relevance threshold
        # Dynamic threshold: show papers above average, or at least top 5
        threshold = max(0.5, avg_sim)  # At least 50% or average
        filtered_results = [r for r in results if r[4] >= threshold]

        # But always show at least top 5
        if len(filtered_results) < 5:
            filtered_results = results[:5]

        console.print(f"[dim]Showing {len(filtered_results)} most relevant papers[/dim]")
        console.print()

        # Display results with color-coded similarity
        table = Table(title=f"Search Results for '{query}'", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Citekey", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Year", justify="center", width=6)
        table.add_column("Similarity", justify="right")

        for i, (citekey, title, year, journal, similarity) in enumerate(filtered_results, 1):
            # Color-code similarity
            if similarity >= 0.7:
                sim_style = "bold green"
                sim_icon = "🟢"
            elif similarity >= 0.55:
                sim_style = "yellow"
                sim_icon = "🟡"
            elif similarity >= 0.4:
                sim_style = "orange3"
                sim_icon = "🟠"
            else:
                sim_style = "red"
                sim_icon = "🔴"

            table.add_row(
                str(i),
                citekey,
                title[:60] + "..." if len(title) > 60 else title,
                str(year) if year else "N/A",
                f"{sim_icon} [{sim_style}]{similarity:.1%}[/{sim_style}]",
            )

        console.print(table)

        # Show interpretation guide
        console.print()
        console.print(
            Panel(
                "🟢 [bold green]>70%[/bold green] - Highly relevant\n"
                "🟡 [yellow]55-70%[/yellow] - Related\n"
                "🟠 [orange3]40-55%[/orange3] - Somewhat related\n"
                "🔴 [red]<40%[/red] - Less relevant",
                title="[bold]Relevance Guide[/bold]",
                border_style="dim",
                expand=False,
            )
        )

        # Warn if collection is too focused
        if min_sim > 0.4:
            console.print()
            console.print(
                Panel(
                    "[yellow]Note:[/yellow] Your collection is focused on similar topics.\n"
                    "All papers show moderate-to-high similarity to most queries.\n"
                    "This is normal for specialized research collections.",
                    border_style="yellow",
                    expand=False,
                )
            )

        # Option to view a result
        console.print()
        if Confirm.ask("[cyan]View a paper?[/cyan]", default=False):
            choice = Prompt.ask("Enter number", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(filtered_results):
                    citekey = filtered_results[idx][0]
                    self.current_paper = self.get_paper_by_citekey(citekey)
                    if self.current_paper:
                        self.display_paper(self.current_paper)
            except ValueError:
                console.print("[red]Invalid choice[/red]")

    def search_papers_detailed(self, query: str, limit: int = 10) -> list:
        """Search with chunk-level detail for better relevance"""

        model = self.load_embedding_model()

        with console.status("[cyan]Searching paper sections...[/cyan]"):
            query_embedding = model.encode(query)
            vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

            cursor = self.conn.cursor()

            # Search chunks and aggregate by paper
            cursor.execute(
                """
                WITH chunk_matches AS (
                    SELECT 
                        pc.paper_id,
                        pc.section_title,
                        pc.content,
                        ce.embedding <=> %s::vector as distance,
                        1 - (ce.embedding <=> %s::vector) as similarity,
                        ROW_NUMBER() OVER (PARTITION BY pc.paper_id ORDER BY ce.embedding <=> %s::vector) as rn
                    FROM paper_chunks pc
                    JOIN chunk_embeddings ce ON pc.id = ce.chunk_id
                    WHERE ce.model_name = 'all-mpnet-base-v2'
                )
                SELECT 
                    p.citekey,
                    p.title,
                    p.year,
                    p.journal,
                    cm.similarity as best_similarity,
                    cm.section_title,
                    cm.content
                FROM chunk_matches cm
                JOIN papers p ON cm.paper_id = p.id
                WHERE cm.rn = 1  -- Best matching chunk per paper
                ORDER BY cm.distance
                LIMIT %s
            """,
                (vector_str, vector_str, vector_str, limit),
            )

            results = cursor.fetchall()
            cursor.close()

        return results

    def cmd_search_detailed(self):
        """Detailed search showing matching sections"""
        query = Prompt.ask("[cyan]Search query[/cyan]")

        results = self.search_papers_detailed(query, limit=10)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print()

        # Display with matching sections
        for i, (citekey, title, year, journal, similarity, section, content) in enumerate(results, 1):
            # Color-code similarity
            if similarity >= 0.7:
                style = "bold green"
                icon = "🟢"
            elif similarity >= 0.55:
                style = "yellow"
                icon = "🟡"
            elif similarity >= 0.4:
                style = "orange3"
                icon = "🟠"
            else:
                style = "red"
                icon = "🔴"

            console.print(f"{i}. [{style}]{icon} {similarity:.1%}[/{style}] - [cyan]{citekey}[/cyan] ({year})")
            console.print(f"   [bold]{title[:70]}...[/bold]")

            if section:
                console.print(f"   📍 Best match in: [yellow]{section}[/yellow]")

            # Show snippet
            snippet = content[:150] + "..." if len(content) > 150 else content
            console.print(f"   [dim]↳ {snippet}[/dim]")
            console.print()

        # Option to view
        if Confirm.ask("[cyan]View a paper?[/cyan]", default=False):
            choice = Prompt.ask("Enter number", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(results):
                    citekey = results[idx][0]
                    self.current_paper = self.get_paper_by_citekey(citekey)
                    if self.current_paper:
                        self.display_paper(self.current_paper)
            except ValueError:
                console.print("[red]Invalid choice[/red]")

    def cmd_view(self):
        """View paper command"""
        citekey = self.select_citekey_interactive()

        if not citekey:
            return

        paper = self.get_paper_by_citekey(citekey)
        if paper is not None:
            self.current_paper = paper
            self.display_paper(paper)
        else:
            console.print(f"[red]Paper not found: {citekey}[/red]")

    def cmd_similar(self):
        """Find similar papers command"""
        if self.current_paper is None:
            console.print("[yellow]No paper selected. Use 'view' or 'search' first.[/yellow]")
            return

        results = self.find_similar_papers(self.current_paper["id"], limit=5)

        if not results:
            console.print("[yellow]No similar papers found[/yellow]")
            return

        table = Table(title=f"Papers Similar to {self.current_paper['citekey']}", box=box.ROUNDED)
        table.add_column("Citekey", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Year", justify="center", width=6)
        table.add_column("Similarity", justify="right", style="green")

        for citekey, title, year, similarity in results:
            table.add_row(
                citekey,
                title[:60] + "..." if len(title) > 60 else title,
                str(year) if year else "N/A",
                f"{similarity:.1%}",
            )

        console.print(table)

    def cmd_ask(self):
        """Ask Claude about current paper"""
        if self.current_paper is None:
            console.print("[yellow]No paper selected. Use 'view' or 'search' first.[/yellow]")
            return

        question = Prompt.ask("[cyan]Ask about this paper[/cyan]")

        context = self.get_paper_context(self.current_paper)

        # Also get similar papers for context
        similar = self.find_similar_papers(self.current_paper["id"], limit=3)
        if similar:
            context += "\n\nSimilar papers in collection:\n"
            for citekey, title, year, similarity in similar:
                context += f"- {citekey} ({year}): {title}\n"

        response = self.ask_claude(question, context)

        console.print()
        console.print(Panel(Markdown(response), title="[bold cyan]Claude's Response[/bold cyan]", border_style="cyan"))

    def cmd_compare(self):
        """Compare two papers"""
        console.print("\n[bold cyan]Select first paper:[/bold cyan]")
        citekey1 = self.select_citekey_interactive()
        if not citekey1:
            return

        console.print("\n[bold cyan]Select second paper:[/bold cyan]")
        citekey2 = self.select_citekey_interactive()
        if not citekey2:
            return

        paper1 = self.get_paper_by_citekey(citekey1)
        paper2 = self.get_paper_by_citekey(citekey2)

        if paper1 is None:
            console.print(f"[red]Paper not found: {citekey1}[/red]")
            return
        if paper2 is None:
            console.print(f"[red]Paper not found: {citekey2}[/red]")
            return

        # Calculate similarity
        if paper1["embedding"] is not None and paper2["embedding"] is not None:
            similarity = np.dot(paper1["embedding"], paper2["embedding"]) / (
                np.linalg.norm(paper1["embedding"]) * np.linalg.norm(paper2["embedding"])
            )
        else:
            similarity = None

        # Build context for Claude
        context = f"Paper 1:\n{self.get_paper_context(paper1)}\n\n"
        context += f"Paper 2:\n{self.get_paper_context(paper2)}\n\n"

        if similarity:
            context += f"Embedding Similarity: {similarity:.1%}\n\n"

        question = (
            "Compare these two papers. What are the similarities and differences? How do they relate to each other?"
        )

        response = self.ask_claude(question, context)

        console.print()
        console.print(
            Panel(
                Markdown(response),
                title=f"[bold cyan]Comparison: {citekey1} vs {citekey2}[/bold cyan]",
                border_style="cyan",
            )
        )

    def cmd_overview(self):
        """Collection overview"""
        context = self.get_collection_context()

        question = "Provide an overview of this research collection. What are the main themes? Any interesting patterns or gaps?"

        response = self.ask_claude(question, context)

        console.print()
        console.print(
            Panel(Markdown(response), title="[bold cyan]Collection Overview[/bold cyan]", border_style="cyan")
        )

    def cmd_clusters(self):
        """Browse clusters"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT 
                c.id,
                c.cluster_name,
                c.paper_count,
                c.avg_year
            FROM paper_clusters c
            ORDER BY c.paper_count DESC
        """)

        clusters = cursor.fetchall()

        if not clusters:
            console.print("[yellow]No clusters found. Run clustering first.[/yellow]")
            return

        # Display clusters
        table = Table(title="Research Clusters", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Cluster", style="cyan")
        table.add_column("Papers", justify="right", style="green")
        table.add_column("Avg Year", justify="center")

        for i, (cid, name, count, avg_year) in enumerate(clusters, 1):
            table.add_row(str(i), name, str(count), f"{avg_year:.0f}" if avg_year else "N/A")

        console.print(table)

        # Option to explore a cluster
        if Confirm.ask("[cyan]Explore a cluster?[/cyan]", default=False):
            choice = Prompt.ask("Enter number", default="1")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(clusters):
                    cluster_id = clusters[idx][0]
                    cluster_name = clusters[idx][1]

                    # Get papers in cluster
                    cursor.execute(
                        """
                        SELECT p.citekey, p.title, p.year
                        FROM paper_cluster_assignments pca
                        JOIN papers p ON pca.paper_id = p.id
                        WHERE pca.cluster_id = %s
                        ORDER BY p.year DESC
                    """,
                        (cluster_id,),
                    )

                    papers_in_cluster = cursor.fetchall()

                    # Display papers
                    table = Table(title=f"Papers in '{cluster_name}'", box=box.ROUNDED)
                    table.add_column("Citekey", style="cyan")
                    table.add_column("Title", style="bold")
                    table.add_column("Year", justify="center")

                    for citekey, title, year in papers_in_cluster:
                        table.add_row(
                            citekey, title[:60] + "..." if len(title) > 60 else title, str(year) if year else "N/A"
                        )

                    console.print(table)

                    # Ask Claude about cluster
                    if Confirm.ask("[cyan]Ask Claude about this cluster?[/cyan]", default=False):
                        paper_list = "\n".join([f"- {ck} ({year}): {title}" for ck, title, year in papers_in_cluster])

                        context = f"Cluster: {cluster_name}\n\nPapers:\n{paper_list}"
                        question = "Analyze this cluster. What unifies these papers? What are the key themes?"

                        response = self.ask_claude(question, context)

                        console.print()
                        console.print(
                            Panel(
                                Markdown(response),
                                title=f"[bold cyan]Cluster Analysis: {cluster_name}[/bold cyan]",
                                border_style="cyan",
                            )
                        )

            except ValueError:
                console.print("[red]Invalid choice[/red]")

        cursor.close()

    def cmd_network(self):
        """Citation network analysis"""
        cursor = self.conn.cursor()

        # Most cited papers
        cursor.execute("""
            SELECT 
                p.citekey,
                p.title,
                p.year,
                COUNT(ce.id) as citation_count
            FROM papers p
            JOIN citation_edges ce ON p.id = ce.cited_paper_id
            GROUP BY p.id, p.citekey, p.title, p.year
            ORDER BY citation_count DESC
            LIMIT 5
        """)

        most_cited = cursor.fetchall()

        if most_cited:
            table = Table(title="Most Cited Papers (in collection)", box=box.ROUNDED)
            table.add_column("Citekey", style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("Year", justify="center")
            table.add_column("Citations", justify="right", style="green")

            for citekey, title, year, count in most_cited:
                table.add_row(
                    citekey, title[:50] + "..." if len(title) > 50 else title, str(year) if year else "N/A", str(count)
                )

            console.print(table)

        # Papers with most references
        cursor.execute("""
            SELECT 
                p.citekey,
                p.title,
                p.year,
                COUNT(r.id) as ref_count
            FROM papers p
            JOIN "references" r ON p.id = r.source_paper_id
            GROUP BY p.id, p.citekey, p.title, p.year
            ORDER BY ref_count DESC
            LIMIT 5
        """)

        most_refs = cursor.fetchall()

        if most_refs:
            console.print()
            table = Table(title="Papers with Most References", box=box.ROUNDED)
            table.add_column("Citekey", style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("Year", justify="center")
            table.add_column("References", justify="right", style="green")

            for citekey, title, year, count in most_refs:
                table.add_row(
                    citekey, title[:50] + "..." if len(title) > 50 else title, str(year) if year else "N/A", str(count)
                )

            console.print(table)

        cursor.close()

        # Ask Claude for network insights
        if Confirm.ask("[cyan]Ask Claude for network insights?[/cyan]", default=False):
            context = "Citation Network Analysis:\n\n"

            if most_cited:
                context += "Most Cited Papers:\n"
                for citekey, title, year, count in most_cited:
                    context += f"- {citekey} ({year}): {count} citations - {title}\n"

            if most_refs:
                context += "\nPapers with Most References:\n"
                for citekey, title, year, count in most_refs:
                    context += f"- {citekey} ({year}): {count} references - {title}\n"

            question = (
                "Analyze this citation network. What does it tell us about the collection? Which papers are central?"
            )

            response = self.ask_claude(question, context)

            console.print()
            console.print(
                Panel(Markdown(response), title="[bold cyan]Citation Network Insights[/bold cyan]", border_style="cyan")
            )

    def format_apa(self, citekey, authors, year, title, journal, volume, issue, pages, doi):
        """Format paper as APA citation"""

        # Format authors
        if authors:
            try:
                if isinstance(authors, str):
                    authors_list = json.loads(authors)
                else:
                    authors_list = authors

                # Extract names from structured format
                author_names = []
                for author in authors_list:
                    if isinstance(author, dict):
                        name = author.get("name", "")
                    else:
                        name = str(author)
                    author_names.append(name)

                if len(author_names) > 3:
                    authors_str = f"{author_names[0]} et al."
                else:
                    authors_str = " & ".join(author_names)
            except:
                authors_str = "Unknown Authors"
        else:
            authors_str = "Unknown Authors"

        # Build APA citation
        citation = f"{authors_str} ({year}). {title}."

        if journal:
            citation += f" [bold]{journal}[/bold]"
            if volume:
                citation += f", {volume}"
                if issue:
                    citation += f"({issue})"
            if pages:
                citation += f", {pages}"

        citation += "."

        if doi:
            citation += f" https://doi.org/{doi}"

        return citation

    def cmd_list(self):
        """List all papers in APA format with filtering and sorting"""

        # Get filter key
        filter_key = (
            Prompt.ask(
                "[cyan]Filter by keyword (author, title, year, journal) or leave blank for all[/cyan]", default=""
            )
            .strip()
            .lower()
        )

        # Get sort option
        console.print("\n[cyan]Sort by:[/cyan]")
        console.print("  1. Author (default)")
        console.print("  2. Year")
        console.print("  3. Title")
        sort_choice = Prompt.ask("[cyan]Choose[/cyan]", default="1").strip()

        sort_map = {
            "1": "authors",
            "2": "year",
            "3": "title",
        }
        sort_by = sort_map.get(sort_choice, "authors")

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                SELECT 
                    citekey, authors, year, title, journal, volume, issue, pages, doi
                FROM papers
                ORDER BY 
                    CASE 
                        WHEN %s = 'year' THEN year::text
                        WHEN %s = 'title' THEN title
                        ELSE CAST(authors AS text)
                    END DESC,
                    year DESC
                """,
                (sort_by, sort_by),
            )

            papers = cursor.fetchall()

            if not papers:
                console.print("[yellow]No papers found[/yellow]")
                return

            # Filter if needed
            filtered_papers = []
            if filter_key:
                for paper in papers:
                    citekey, authors, year, title, journal, volume, issue, pages, doi = paper

                    # Check if filter matches any field
                    searchable = f"{citekey} {authors} {year} {title} {journal}".lower()
                    if filter_key in searchable:
                        filtered_papers.append(paper)
            else:
                filtered_papers = papers

            if not filtered_papers:
                console.print(f"[yellow]No papers matching '{filter_key}'[/yellow]")
                return

            # Display results
            console.print()
            console.print(f"[bold cyan]📚 Papers ({len(filtered_papers)})[/bold cyan]")
            console.print()

            for i, paper in enumerate(filtered_papers, 1):
                citekey, authors, year, title, journal, volume, issue, pages, doi = paper
                apa = self.format_apa(citekey, authors, year, title, journal, volume, issue, pages, doi)

                console.print(f"[bold]{i}.[/bold] [{citekey}] {apa}")
                console.print()

            # Option to export
            if Confirm.ask("\n[cyan]Export to file?[/cyan]", default=False):
                filename = Prompt.ask("[cyan]Filename[/cyan]", default="papers.txt").strip()

                with open(filename, "w") as f:
                    f.write(f"Reading List ({len(filtered_papers)} papers)\n")
                    f.write("=" * 80 + "\n\n")

                    for i, paper in enumerate(filtered_papers, 1):
                        citekey, authors, year, title, journal, volume, issue, pages, doi = paper
                        apa = self.format_apa(citekey, authors, year, title, journal, volume, issue, pages, doi)
                        f.write(f"{i}. [{citekey}] {apa}\n\n")

                console.print(f"[green]✓ Exported to {filename}[/green]")

        finally:
            cursor.close()

    def run(self):
        """Main interactive loop"""

        self.show_menu()

        commands = {
            "search": self.cmd_search,
            "s": self.cmd_search,
            "search-detail": self.cmd_search_detailed,
            "sd": self.cmd_search_detailed,
            "view": self.cmd_view,
            "v": self.cmd_view,
            "similar": self.cmd_similar,
            "sim": self.cmd_similar,
            "ask": self.cmd_ask,
            "a": self.cmd_ask,
            "compare": self.cmd_compare,
            "comp": self.cmd_compare,
            "overview": self.cmd_overview,
            "o": self.cmd_overview,
            "clusters": self.cmd_clusters,
            "c": self.cmd_clusters,
            "network": self.cmd_network,
            "net": self.cmd_network,
            "list": self.cmd_list,
            "l": self.cmd_list,
            "help": self.show_menu,
            "h": self.show_menu,
        }

        while True:
            try:
                console.print()
                cmd = Prompt.ask("[bold cyan]paper-explorer>[/bold cyan]", default="help").strip().lower()

                if cmd in ["quit", "q", "exit"]:
                    console.print("[yellow]Goodbye! 👋[/yellow]")
                    break

                if cmd in commands:
                    commands[cmd]()
                else:
                    console.print(f"[red]Unknown command: {cmd}[/red]")
                    console.print("Type 'help' for commands")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback

                traceback.print_exc()


def main():
    """Entry point"""

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        console.print("Set it with: export ANTHROPIC_API_KEY=your-key")
        sys.exit(1)

    # Connection string from environment or use default
    connection_string = os.environ.get("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")

    try:
        explorer = PaperExplorer(connection_string)
        explorer.run()
    except psycopg2.OperationalError as e:
        console.print(f"[red]Database connection error: {e}[/red]")
        console.print("Make sure PostgreSQL is running:")
        console.print("  docker-compose up -d pdf-browser-db")
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
