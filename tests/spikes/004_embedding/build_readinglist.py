#!/usr/bin/env python3
"""
Build a reading list starting from a seed paper

Usage:
    python build_reading_list.py CiarliEtAl2021 10
"""

import sys

import psycopg2
from pgvector.psycopg2 import register_vector


def build_reading_list(seed_citekey, total_papers=10):
    """Build reading list by iteratively finding similar papers"""

    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    reading_list = []
    visited = set()
    queue = [(seed_citekey, 0)]  # (citekey, depth)

    print(f"Building reading list starting from: {seed_citekey}")
    print(f"Target: {total_papers} papers")
    print()

    while queue and len(reading_list) < total_papers:
        current, depth = queue.pop(0)

        if current in visited:
            continue

        visited.add(current)

        # Get paper details
        cursor.execute(
            """
            SELECT id, citekey, title, year, journal
            FROM papers
            WHERE citekey = %s
        """,
            (current,),
        )

        result = cursor.fetchone()
        if not result:
            continue

        paper_id, citekey, title, year, journal = result
        reading_list.append({"citekey": citekey, "title": title, "year": year, "journal": journal, "depth": depth})

        # Find similar papers to add to queue
        cursor.execute(
            """
            SELECT
                p2.citekey,
                pe1.embedding <=> pe2.embedding as distance
            FROM papers p1
            JOIN paper_embeddings pe1 ON p1.id = pe1.paper_id
            JOIN paper_embeddings pe2 ON pe2.paper_id != p1.id
            JOIN papers p2 ON pe2.paper_id = p2.id
            WHERE p1.citekey = %s
              AND pe1.embedding_method = 'aggregate_chunks'
              AND pe2.embedding_method = 'aggregate_chunks'
            ORDER BY distance
            LIMIT 3
        """,
            (current,),
        )

        for similar_citekey, _ in cursor.fetchall():
            if similar_citekey not in visited and similar_citekey not in [q[0] for q in queue]:
                queue.append((similar_citekey, depth + 1))

    cursor.close()
    conn.close()

    # Print reading list
    print("📚 Your Reading List:")
    print("=" * 80)

    for i, paper in enumerate(reading_list, 1):
        indent = "  " * paper["depth"]
        print(f"\n{i}. {indent}{paper['citekey']} ({paper['year']})")
        print(f"   {indent}{paper['title']}")
        if paper["journal"]:
            print(f"   {indent}📚 {paper['journal']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_reading_list.py <seed_citekey> [total_papers]")
        print("Example: python build_reading_list.py CiarliEtAl2021 10")
        sys.exit(1)

    seed = sys.argv[1]
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    build_reading_list(seed, total)
