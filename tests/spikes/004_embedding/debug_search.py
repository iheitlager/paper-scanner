#!/usr/bin/env python3
"""
Debug semantic search

Test if embeddings are working correctly
"""

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer


def debug_search():
    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")
    register_vector(conn)
    cursor = conn.cursor()

    # Load model
    print("Loading embedding model...")
    model = SentenceTransformer("all-mpnet-base-v2")

    # Test query
    query = "digital transformation"
    print(f"\nQuery: '{query}'")

    # Generate query embedding
    query_embedding = model.encode(query)
    print(f"Query embedding shape: {query_embedding.shape}")
    print(f"Query embedding sample (first 5 values): {query_embedding[:5]}")

    # Check paper embeddings
    cursor.execute("""
        SELECT 
            p.citekey,
            p.title,
            pe.embedding,
            pe.model_name,
            pe.model_dimension
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
        LIMIT 1
    """)

    result = cursor.fetchone()
    if result:
        citekey, title, paper_emb, model_name, dimension = result
        paper_emb = np.array(paper_emb)

        print(f"\nFirst paper: {citekey}")
        print(f"Paper embedding shape: {paper_emb.shape}")
        print(f"Paper embedding sample (first 5 values): {paper_emb[:5]}")
        print(f"Model in DB: {model_name}")
        print(f"Dimension in DB: {dimension}")

    # Test similarity calculation manually
    print("\n" + "=" * 60)
    print("MANUAL SIMILARITY CALCULATION")
    print("=" * 60)

    cursor.execute("""
        SELECT p.citekey, p.title, pe.embedding
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
    """)

    all_papers = cursor.fetchall()

    for citekey, title, paper_emb in all_papers:
        paper_emb = np.array(paper_emb)

        # Cosine similarity
        cosine_sim = np.dot(query_embedding, paper_emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(paper_emb))

        # Cosine distance (what pgvector uses with <=>)
        cosine_dist = 1 - cosine_sim

        print(f"\n{citekey}")
        print(f"  Title: {title[:50]}...")
        print(f"  Cosine similarity: {cosine_sim:.4f} ({cosine_sim:.1%})")
        print(f"  Cosine distance: {cosine_dist:.4f}")

    # Now test with PostgreSQL
    print("\n" + "=" * 60)
    print("POSTGRESQL SEARCH RESULTS")
    print("=" * 60)

    vector_str = "[" + ",".join(map(str, query_embedding)) + "]"

    cursor.execute(
        """
        SELECT 
            p.citekey,
            p.title,
            pe.embedding <=> %s::vector as distance,
            1 - (pe.embedding <=> %s::vector) as similarity
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
        ORDER BY pe.embedding <=> %s::vector
    """,
        (vector_str, vector_str, vector_str),
    )

    for citekey, title, distance, similarity in cursor.fetchall():
        print(f"\n{citekey}")
        print(f"  Title: {title[:50]}...")
        print(f"  Distance: {distance:.4f}")
        print(f"  Similarity: {similarity:.1%}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    debug_search()
