#!/usr/bin/env python3
"""
Compare two papers in detail

Usage:
    python compare_papers.py CiarliEtAl2021 MancusoEtAl2024
"""

import sys

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector


def compare_papers(citekey1, citekey2):
    """Detailed comparison of two papers"""

    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    # Get both papers
    papers = {}
    for citekey in (citekey1, citekey2):
        cursor.execute(
            """
            SELECT 
                p.citekey, p.title, p.year, p.journal, p.authors,
                pe.embedding
            FROM papers p
            JOIN paper_embeddings pe ON p.id = pe.paper_id
            WHERE p.citekey = %s
              AND pe.embedding_method = 'aggregate_chunks'
        """,
            (citekey,),
        )

        result = cursor.fetchone()
        if not result:
            print(f"Paper not found: {citekey}")
            return

        papers[citekey] = {
            "citekey": result[0],
            "title": result[1],
            "year": result[2],
            "journal": result[3],
            "authors": result[4],
            "embedding": np.array(result[5]),
        }

    # Calculate similarity
    emb1 = papers[citekey1]["embedding"]
    emb2 = papers[citekey2]["embedding"]

    # Cosine similarity
    cosine_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

    # Euclidean distance
    euclidean_dist = np.linalg.norm(emb1 - emb2)

    # Print comparison
    print("=" * 80)
    print("PAPER COMPARISON")
    print("=" * 80)

    for i, ck in enumerate([citekey1, citekey2], 1):
        p = papers[ck]
        print(f"\nPaper {i}:")
        print(f"  Citekey: {p['citekey']}")
        print(f"  Title: {p['title']}")
        print(f"  Year: {p['year']}")
        if p["journal"]:
            print(f"  Journal: {p['journal']}")

    print(f"\n{'=' * 80}")
    print("SIMILARITY METRICS")
    print("=" * 80)
    print(f"Cosine Similarity: {cosine_sim:.1%}")
    print(f"Euclidean Distance: {euclidean_dist:.4f}")

    if cosine_sim > 0.85:
        print("\n🟢 Very similar papers - likely the same research area")
    elif cosine_sim > 0.70:
        print("\n🟡 Related papers - overlapping concepts")
    elif cosine_sim > 0.50:
        print("\n🟠 Somewhat related - some common themes")
    else:
        print("\n🔴 Different topics - distinct research areas")

    # Find papers similar to both
    print(f"\n{'=' * 80}")
    print("PAPERS SIMILAR TO BOTH")
    print("=" * 80)

    cursor.execute(
        """
        WITH paper1 AS (
            SELECT embedding FROM paper_embeddings pe
            JOIN papers p ON pe.paper_id = p.id
            WHERE p.citekey = %s AND pe.embedding_method = 'aggregate_chunks'
        ),
        paper2 AS (
            SELECT embedding FROM paper_embeddings pe
            JOIN papers p ON pe.paper_id = p.id
            WHERE p.citekey = %s AND pe.embedding_method = 'aggregate_chunks'
        )
        SELECT 
            p.citekey,
            p.title,
            (pe.embedding <=> (SELECT embedding FROM paper1)) as dist1,
            (pe.embedding <=> (SELECT embedding FROM paper2)) as dist2,
            ((pe.embedding <=> (SELECT embedding FROM paper1)) + 
             (pe.embedding <=> (SELECT embedding FROM paper2))) / 2 as avg_dist
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE p.citekey NOT IN (%s, %s)
          AND pe.embedding_method = 'aggregate_chunks'
        ORDER BY avg_dist
        LIMIT 3
    """,
        (citekey1, citekey2, citekey1, citekey2),
    )

    for ck, title, dist1, dist2, avg_dist in cursor.fetchall():
        sim1 = 1 - dist1
        sim2 = 1 - dist2
        print(f"\n📄 {ck}")
        print(f"   {title}")
        print(f"   Similarity to {citekey1}: {sim1:.1%}")
        print(f"   Similarity to {citekey2}: {sim2:.1%}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compare_papers.py <citekey1> <citekey2>")
        print("Example: python compare_papers.py CiarliEtAl2021 MancusoEtAl2024")
        sys.exit(1)

    compare_papers(sys.argv[1], sys.argv[2])
