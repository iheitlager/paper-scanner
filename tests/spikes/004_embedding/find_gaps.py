#!/usr/bin/env python3
"""
Find research gaps - topics that have no similar papers

Usage:
    python find_gaps.py
"""

import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np


def find_gaps(threshold=0.6):
    """Find papers that are isolated (no similar neighbors)"""

    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    # Get all papers with their embeddings
    cursor.execute("""
        SELECT p.id, p.citekey, p.title, p.year, pe.embedding
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
    """)

    papers = cursor.fetchall()

    print(f"Analyzing {len(papers)} papers for research gaps...")
    print(f"Threshold: Papers with similarity < {threshold:.0%} to all others")
    print()

    gaps = []

    for i, (pid, citekey, title, year, embedding) in enumerate(papers):
        # Find nearest neighbor
        cursor.execute(
            """
            SELECT 
                p2.citekey,
                pe1.embedding <=> pe2.embedding as distance,
                1 - (pe1.embedding <=> pe2.embedding) as similarity
            FROM paper_embeddings pe1
            JOIN paper_embeddings pe2 ON pe2.paper_id != pe1.paper_id
            JOIN papers p2 ON pe2.paper_id = p2.id
            WHERE pe1.paper_id = %s
              AND pe1.embedding_method = 'aggregate_chunks'
              AND pe2.embedding_method = 'aggregate_chunks'
            ORDER BY pe1.embedding <=> pe2.embedding
            LIMIT 1
        """,
            (pid,),
        )

        result = cursor.fetchone()
        if result:
            nearest_citekey, distance, similarity = result

            if similarity < threshold:
                gaps.append(
                    {
                        "citekey": citekey,
                        "title": title,
                        "year": year,
                        "nearest": nearest_citekey,
                        "similarity": similarity,
                    }
                )

    cursor.close()
    conn.close()

    if gaps:
        print(f"🔍 Found {len(gaps)} potential research gaps:")
        print("=" * 80)

        for gap in sorted(gaps, key=lambda x: x["similarity"]):
            print(f"\n📌 {gap['citekey']} ({gap['year']})")
            print(f"   {gap['title']}")
            print(f"   Nearest paper: {gap['nearest']} (similarity: {gap['similarity']:.1%})")
            print(f"   → This paper is relatively isolated - potential research gap!")
    else:
        print("✓ No significant gaps found. All papers have similar neighbors.")


if __name__ == "__main__":
    find_gaps(threshold=0.6)
