#!/usr/bin/env python
"""
Compare two papers with their chunk embeddings.

Usage:
    python try_08_compare_papers.py TestPaper2024 CitedPaper2023

Shows:
- Paper metadata
- Similarity metrics (cosine, euclidean)
- Papers similar to both
"""

import os
import sys

import numpy as np
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


def compare_papers(citekey1, citekey2):
    """Detailed comparison of two papers"""

    conn = psycopg2.connect(get_db_url())
    register_vector(conn)
    cursor = conn.cursor()

    # Get both papers with their embeddings
    papers = {}
    for citekey in (citekey1, citekey2):
        cursor.execute(
            """
            SELECT
                p.cite_key, p.title, p.year, p.journal,
                pe.embedding, pe.embedding_method, pe.created_at
            FROM papers p
            LEFT JOIN paper_embeddings pe ON p.db_id = pe.paper_id
            WHERE p.cite_key = %s
            LIMIT 1
        """,
            (citekey,),
        )

        result = cursor.fetchone()
        if not result:
            print(f"❌ Paper not found: {citekey}")
            cursor.close()
            conn.close()
            return False

        cite_key, title, year, journal, embedding, method, created = result

        if embedding is None:
            print(f"⚠️  Paper {citekey} has no embedding yet")
            cursor.close()
            conn.close()
            return False

        papers[citekey] = {
            "cite_key": cite_key,
            "title": title,
            "year": year,
            "journal": journal,
            "embedding": np.array(embedding),
            "embedding_method": method,
            "created_at": created,
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
        print(f"\n📄 Paper {i}:")
        print(f"   Citekey: {p['cite_key']}")
        print(f"   Title: {p['title']}")
        if p["year"]:
            print(f"   Year: {p['year']}")
        if p["journal"]:
            print(f"   Journal: {p['journal']}")
        print(f"   Embedding: {p['embedding_method']} ({len(p['embedding'])}d)")
        print(f"   Created: {p['created_at']}")

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

    cursor.close()
    conn.close()
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python try_08_compare_papers.py <citekey1> <citekey2>")
        print("Example: python try_08_compare_papers.py TestPaper2024 CitedPaper2023")
        sys.exit(1)

    citekey1 = sys.argv[1]
    citekey2 = sys.argv[2]

    success = compare_papers(citekey1, citekey2)
    sys.exit(0 if success else 1)
