#!/usr/bin/env python3
"""
Find papers similar to a given paper

Usage:
    python find_similar.py CiarliEtAl2021

Finding papers similar to:
  CiarliEtAl2021: Digital technologies, innovation, and skills...

Most similar papers:
--------------------------------------------------------------------------------
1. MancusoEtAl2024 (2024)
   Leadership in the metaverse: Building and integrating digital capabilities
   Journal: Business Horizons
   Similarity: 87.3% (distance: 0.1271)

2. CorreaniEtAl2020 (2020)
   Implementing a Digital Strategy: Learning from the experience...
   Journal: California Management Review
   Similarity: 84.2% (distance: 0.1582)
"""

import sys

import psycopg2
from pgvector.psycopg2 import register_vector


def find_similar_papers(citekey, limit=5):
    """Find papers similar to the given citekey"""

    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    # Get the target paper's embedding
    cursor.execute(
        """
        SELECT p.id, p.citekey, p.title
        FROM papers p
        WHERE p.citekey = %s
    """,
        (citekey,),
    )

    result = cursor.fetchone()
    if not result:
        print(f"Paper not found: {citekey}")
        return

    paper_id, paper_citekey, paper_title = result

    print("Finding papers similar to:")
    print(f"  {paper_citekey}: {paper_title}")
    print()

    # Find similar papers using vector similarity
    cursor.execute(
        """
        SELECT 
            p2.citekey,
            p2.title,
            p2.year,
            p2.journal,
            pe1.embedding <=> pe2.embedding as distance,
            1 - (pe1.embedding <=> pe2.embedding) as similarity
        FROM papers p1
        JOIN paper_embeddings pe1 ON p1.id = pe1.paper_id
        JOIN paper_embeddings pe2 ON pe2.paper_id != p1.id
        JOIN papers p2 ON pe2.paper_id = p2.id
        WHERE p1.citekey = %s
          AND pe1.embedding_method = 'aggregate_chunks'
          AND pe2.embedding_method = 'aggregate_chunks'
        ORDER BY pe1.embedding <=> pe2.embedding
        LIMIT %s
    """,
        (citekey, limit),
    )

    print("Most similar papers:")
    print("-" * 80)

    for i, (ck, title, year, journal, distance, similarity) in enumerate(cursor.fetchall(), 1):
        print(f"{i}. {ck} ({year})")
        print(f"   {title}")
        if journal:
            print(f"   Journal: {journal}")
        print(f"   Similarity: {similarity:.1%} (distance: {distance:.4f})")
        print()

    cursor.close()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_similar.py <citekey> [limit]")
        print("Example: python find_similar.py CiarliEtAl2021 5")
        sys.exit(1)

    citekey = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    find_similar_papers(citekey, limit)
