#!/usr/bin/env python3
"""Test semantic logging with Router."""
import os
import sys
from pathlib import Path
from io import StringIO

# Disable tokenizers parallelism
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import psycopg2
from dotenv import load_dotenv
from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
from rich.console import Console

from paper_scanner.core.models import Paper

# Add components to path
sys.path.insert(0, str(Path(__file__).parent))
from components import (
    SimplifyingPlanner, Tool, Evaluator, Synthesizer, Memory, Router,
    DefaultLogger, SilentLogger
)

load_dotenv()


def connect_db():
    """Connect to PostgreSQL."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "paper_scanner_dev"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432")
    )
    return conn


def load_papers(db_conn, limit: int = 50):
    """Load papers from database."""
    cur = db_conn.cursor()
    cur.execute("""
        SELECT db_id, id, cite_key, doi, title, year, journal, volume, issue, abstract, authors
        FROM papers
        ORDER BY year DESC, cite_key
        LIMIT %s
    """, (limit,))
    
    papers = {}
    for row in cur.fetchall():
        db_id, id_val, cite_key, doi, title, year, journal, volume, issue, abstract, authors = row
        paper = Paper(
            db_id=db_id, id=id_val, cite_key=cite_key, doi=doi, title=title, year=year,
            journal=journal, volume=volume, issue=issue, abstract=abstract, authors=authors or []
        )
        papers[db_id] = paper
    
    cur.close()
    return papers


def main():
    """Test semantic logging."""
    console = Console()
    
    try:
        console.print("[bold cyan]Initializing components...[/bold cyan]")
        
        db_conn = connect_db()
        encoder = SentenceTransformer('all-mpnet-base-v2')
        llm_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        papers = load_papers(db_conn)
        console.print(f"[green]Loaded {len(papers)} papers[/green]\n")
        
        # Initialize components
        planner = SimplifyingPlanner(llm_client)
        tool = Tool(db_conn, encoder)
        evaluator = Evaluator()
        synthesizer = Synthesizer(llm_client)
        memory = Memory(encoder)
        
        # Create logger
        logger = DefaultLogger(console)
        
        # Create Router with logger
        router = Router(
            planner=planner,
            tool=tool,
            evaluator=evaluator,
            synthesizer=synthesizer,
            memory=memory,
            verbose=True,
            logger=logger
        )
        
        console.print("[bold cyan]Router initialized with semantic logging[/bold cyan]\n")
        
        # Test query
        question = "What are the main findings about machine learning in software development?"
        console.print(f"[bold cyan]Processing query:[/bold cyan] {question}\n")
        
        results = router.route_query(question)
        
        if 'error' not in results:
            console.print(f"\n[bold green]✓ Query processed successfully[/bold green]")
            console.print(f"Source: {results.get('source')}")
            console.print(f"Citations: {len(results.get('citations', []))} found")
        else:
            console.print(f"\n[bold red]✗ Query failed: {results['error']}[/bold red]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        if 'db_conn' in locals():
            db_conn.close()


if __name__ == "__main__":
    main()
