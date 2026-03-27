#!/usr/bin/env python3
"""
Search papers using natural language query

Usage:
    python search_papers.py "digital transformation strategy"

Example output:

Loading embedding model...
Searching for: 'digital transformation strategy'

Search results:
================================================================================

1. CorreaniEtAl2020 (2020) - Similarity: 89.2%
   Implementing a Digital Strategy: Learning from the experience...
   📚 California Management Review
   📄 This article examines three digital transformation projects...

2. PiccoliEtAl2024 (2024) - Similarity: 86.5%
   Digital transformation requires digital resource primacy...
   📚 Journal of Strategic Information Systems
"""

import sys

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer


def search_papers(query, limit=5):
    """Search papers using semantic similarity"""

    # Load embedding model (same as used for papers)
    print("Loading embedding model...")
    model = SentenceTransformer("all-mpnet-base-v2")

    # Embed the query
    print(f"Searching for: '{query}'")
    print()
    query_embedding = model.encode(query)

    # Search database
    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    # Convert to vector string
    vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

    # Find similar papers
    cursor.execute(
        """
        SELECT
            p.citekey,
            p.title,
            p.year,
            p.journal,
            p.abstract,
            pe.embedding <=> %s::vector as distance,
            1 - (pe.embedding <=> %s::vector) as similarity
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
        ORDER BY pe.embedding <=> %s::vector
        LIMIT %s
    """,
        (vector_str, vector_str, vector_str, limit),
    )

    print("Search results:")
    print("=" * 80)

    for i, (citekey, title, year, journal, abstract, distance, similarity) in enumerate(cursor.fetchall(), 1):
        print(f"\n{i}. {citekey} ({year}) - Similarity: {similarity:.1%}")
        print(f"   {title}")
        if journal:
            print(f"   📚 {journal}")
        if abstract:
            print(f"   📄 {abstract[:200]}...")
        print()

    cursor.close()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_papers.py '<query>' [limit]")
        print("Example: python search_papers.py 'innovation capabilities' 5")
        sys.exit(1)

    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    search_papers(query, limit)
