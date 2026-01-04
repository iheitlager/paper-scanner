#!/usr/bin/env python
"""
Find papers similar to a given paper using vector similarity.

Usage:
    python try_09_find_similar.py TestPaper2024

Shows:
- Target paper info
- Top N most similar papers ranked by cosine similarity
- Distance and similarity metrics
"""

import sys
import os
from dotenv import load_dotenv

import numpy as np
import psycopg2
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


def find_similar_papers(citekey, limit=5):
    """Find papers similar to the given citekey"""

    conn = psycopg2.connect(get_db_url())
    register_vector(conn)
    cursor = conn.cursor()

    # Get the target paper
    cursor.execute(
        """
        SELECT p.db_id, p.cite_key, p.title, p.year, p.journal
        FROM papers p
        WHERE p.cite_key = %s
    """,
        (citekey,),
    )

    result = cursor.fetchone()
    if not result:
        print(f"❌ Paper not found: {citekey}")
        cursor.close()
        conn.close()
        return False

    paper_db_id, paper_cite_key, paper_title, paper_year, paper_journal = result

    print("=" * 80)
    print("FIND SIMILAR PAPERS")
    print("=" * 80)
    print(f"\n🎯 Target Paper:")
    print(f"   {paper_cite_key} ({paper_year})")
    print(f"   {paper_title}")
    if paper_journal:
        print(f"   Journal: {paper_journal}")
    print()

    # Find similar papers using pgvector distance operator (<=>)
    # The <=> operator returns distance, so smaller = more similar
    cursor.execute(
        """
        SELECT 
            p2.cite_key,
            p2.title,
            p2.year,
            p2.journal,
            pe1.embedding <=> pe2.embedding as distance
        FROM paper_embeddings pe1
        JOIN paper_embeddings pe2 ON pe2.paper_id != pe1.paper_id
        JOIN papers p2 ON pe2.paper_id = p2.db_id
        WHERE pe1.paper_id = %s
        ORDER BY pe1.embedding <=> pe2.embedding
        LIMIT %s
    """,
        (paper_db_id, limit),
    )

    results = cursor.fetchall()
    
    if not results:
        print("⚠️  No other papers found in database")
        cursor.close()
        conn.close()
        return True

    print(f"🔍 Most similar papers (top {limit}):")
    print("-" * 80)

    for i, (ck, title, year, journal, distance) in enumerate(results, 1):
        # Distance 0 = identical, convert to similarity percentage
        # pgvector distance ranges from 0 to 2 for normalized vectors
        similarity = max(0, 1.0 - distance)  # Approximate conversion
        
        print(f"\n{i}. {ck} ({year})")
        print(f"   {title}")
        if journal:
            print(f"   Journal: {journal}")
        print(f"   Distance: {distance:.4f} | Similarity: {similarity:.1%}")

    cursor.close()
    conn.close()
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python try_09_find_similar.py <citekey> [limit]")
        print("Example: python try_09_find_similar.py TestPaper2024 5")
        sys.exit(1)

    citekey = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    success = find_similar_papers(citekey, limit)
    sys.exit(0 if success else 1)
