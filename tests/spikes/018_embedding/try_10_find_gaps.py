#!/usr/bin/env python
"""
Find research gaps - papers with no similar papers.

Usage:
    python try_10_find_gaps.py [threshold]

Shows:
- Papers isolated from others (low similarity to all neighbors)
- Threshold: papers with similarity < threshold to nearest neighbor
- Potential research gaps or niche topics
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

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


def find_gaps(threshold=0.6):
    """Find papers that are isolated (low similarity to nearest neighbor)"""

    conn = psycopg2.connect(get_db_url())
    register_vector(conn)
    cursor = conn.cursor()

    # Count total papers
    cursor.execute("SELECT COUNT(*) FROM paper_embeddings")
    total_papers = cursor.fetchone()[0]

    print("=" * 80)
    print("FIND RESEARCH GAPS")
    print("=" * 80)
    print(f"\nAnalyzing {total_papers} papers for research gaps...")
    print(f"Threshold: Papers with nearest neighbor similarity < {threshold:.0%}")
    print()

    # Get all papers
    cursor.execute(
        """
        SELECT p.db_id, p.cite_key, p.title, p.year
        FROM papers p
        JOIN paper_embeddings pe ON p.db_id = pe.paper_id
        ORDER BY p.cite_key
    """
    )

    all_papers = cursor.fetchall()
    gaps = []

    for paper_db_id, citekey, title, year in all_papers:
        # Find nearest neighbor (excluding self)
        cursor.execute(
            """
            SELECT
                p2.cite_key,
                pe1.embedding <=> pe2.embedding as distance
            FROM paper_embeddings pe1
            JOIN paper_embeddings pe2 ON pe2.paper_id != pe1.paper_id
            JOIN papers p2 ON pe2.paper_id = p2.db_id
            WHERE pe1.paper_id = %s
            ORDER BY pe1.embedding <=> pe2.embedding
            LIMIT 1
        """,
            (paper_db_id,),
        )

        result = cursor.fetchone()
        if result:
            nearest_citekey, distance = result
            # Convert distance to similarity (approximate for normalized vectors)
            similarity = max(0, 1.0 - distance)

            if similarity < threshold:
                gaps.append({
                    "citekey": citekey,
                    "title": title,
                    "year": year,
                    "nearest": nearest_citekey,
                    "similarity": similarity,
                    "distance": distance,
                })

    cursor.close()
    conn.close()

    if gaps:
        print(f"🔍 Found {len(gaps)} potential research gaps:")
        print("=" * 80)

        for gap in sorted(gaps, key=lambda x: x["similarity"]):
            print(f"\n🎯 {gap['citekey']} ({gap['year']})")
            print(f"   {gap['title']}")
            print(f"   Nearest paper: {gap['nearest']}")
            print(f"   Similarity to nearest: {gap['similarity']:.1%} (distance: {gap['distance']:.4f})")

        print(f"\n{'=' * 80}")
        print("💡 Interpretation:")
        print("   These papers are isolated from other topics in your collection.")
        print("   They represent potential research gaps or niche areas.")
    else:
        print(f"✅ No research gaps found (all papers have similarity >= {threshold:.0%})")
        print("   Your collection is well-connected with similar papers.")

    return True


if __name__ == "__main__":
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6

    if not (0 <= threshold <= 1):
        print("❌ Threshold must be between 0 and 1")
        sys.exit(1)

    success = find_gaps(threshold)
    sys.exit(0 if success else 1)
