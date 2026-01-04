#!/usr/bin/env python
"""
Cluster papers using K-means on paper embeddings.

Loads embeddings from paper_embeddings table, runs K-means clustering,
and stores results in paper_clusters and paper_cluster_assignments tables.

Usage:
    python try_11_cluster_papers.py [n_clusters]

Examples:
    python try_11_cluster_papers.py           # Default 3 clusters
    python try_11_cluster_papers.py 4         # 4 clusters
"""

import sys
import json
import os
from dotenv import load_dotenv

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

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


def cluster_papers(n_clusters=3):
    """
    Cluster papers using K-means
    """

    conn = psycopg2.connect(get_db_url())
    register_vector(conn)
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("PAPER CLUSTERING")
    print("="*80)

    # Step 1: Load all paper embeddings
    print("\n[Step 1/4] Loading paper embeddings...")
    cursor.execute("""
        SELECT p.db_id, p.cite_key, p.title, p.year, p.journal, pe.embedding
        FROM papers p
        JOIN paper_embeddings pe ON p.db_id = pe.paper_id
        ORDER BY p.cite_key
    """)

    results = cursor.fetchall()
    paper_db_ids = [r[0] for r in results]
    citekeys = [r[1] for r in results]
    titles = [r[2] for r in results]
    years = [r[3] if r[3] else 0 for r in results]
    journals = [r[4] if r[4] else "Unknown" for r in results]

    # Convert embeddings to numpy array
    # After register_vector, embeddings come back as numpy arrays
    embeddings = np.array([np.array(r[5]) for r in results])

    print(f"  ✓ Loaded {len(paper_db_ids)} papers")
    print(f"  ✓ Embedding shape: {embeddings.shape}")
    print(f"  Papers: {', '.join(citekeys)}")

    # Check if we have enough papers for clustering
    if len(paper_db_ids) < n_clusters:
        print(f"\n  ⚠ Warning: Only {len(paper_db_ids)} papers, reducing clusters to {len(paper_db_ids)}")
        n_clusters = max(2, len(paper_db_ids))  # At least 2 clusters

    # Step 2: Run K-means clustering
    print(f"\n[Step 2/4] Running K-means clustering (n_clusters={n_clusters})...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    centroids = kmeans.cluster_centers_

    # Calculate quality score
    if len(paper_db_ids) >= n_clusters:
        silhouette = silhouette_score(embeddings, labels)
        print(f"  ✓ Silhouette score: {silhouette:.3f}")
    else:
        silhouette = None

    # Step 3: Analyze and insert clusters
    print(f"\n[Step 3/4] Analyzing clusters and inserting into database...")

    cluster_db_ids = {}  # Map cluster_idx -> db_id

    for cluster_id in range(n_clusters):
        cluster_papers_list = [
            (pid, ck, t, y, j)
            for pid, ck, t, y, j, label in zip(
                paper_db_ids, citekeys, titles, years, journals, labels
            )
            if label == cluster_id
        ]

        cluster_years = [y for _, _, _, y, _ in cluster_papers_list if y > 0]
        avg_year = np.mean(cluster_years) if cluster_years else None

        # Generate cluster name
        cluster_name = f"Cluster {cluster_id + 1}"

        print(f"\n  Cluster {cluster_id + 1}: {len(cluster_papers_list)} papers")
        if avg_year:
            print(f"    Avg year: {avg_year:.1f}")

        cluster_citekeys = [ck for _, ck, _, _, _ in cluster_papers_list]
        print(f"    Papers: {', '.join(cluster_citekeys)}")

        # Insert cluster into database
        centroid_list = centroids[cluster_id].tolist()

        cursor.execute(
            """
            INSERT INTO paper_clusters (
                cluster_name,
                clustering_method,
                clustering_parameters,
                paper_count,
                avg_year,
                centroid_embedding
            ) VALUES (%s, %s, %s, %s, %s, %s::vector)
            RETURNING id
        """,
            (
                cluster_name,
                "kmeans",
                json.dumps({
                    "n_clusters": n_clusters,
                    "silhouette_score": float(silhouette) if silhouette else None,
                    "random_state": 42,
                }),
                len(cluster_papers_list),
                float(avg_year) if avg_year else None,
                centroid_list,
            ),
        )

        db_cluster_id = cursor.fetchone()[0]
        cluster_db_ids[cluster_id] = db_cluster_id
        print(f"    ✓ Inserted cluster with id={db_cluster_id}")

        # Assign papers to cluster
        for paper_db_id, _, _, _, _ in cluster_papers_list:
            # Calculate distance to centroid
            paper_idx = paper_db_ids.index(paper_db_id)
            distance = np.linalg.norm(embeddings[paper_idx] - centroids[cluster_id])
            confidence = 1 / (1 + distance)  # Simple confidence metric

            cursor.execute(
                """
                INSERT INTO paper_cluster_assignments (
                    paper_id,
                    cluster_id,
                    distance_to_centroid,
                    assignment_confidence
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (paper_id, cluster_id) DO UPDATE SET
                    distance_to_centroid = EXCLUDED.distance_to_centroid,
                    assignment_confidence = EXCLUDED.assignment_confidence
            """,
                (paper_db_id, db_cluster_id, float(distance), float(confidence)),
            )

    conn.commit()

    # Step 4: Display summary
    print(f"\n[Step 4/4] Clustering complete!")
    print(f"\n  Summary:")
    print(f"    - Papers clustered: {len(paper_db_ids)}")
    print(f"    - Number of clusters: {n_clusters}")
    silhouette_str = f"{silhouette:.3f}" if silhouette else "N/A"
    print(f"    - Silhouette score: {silhouette_str}")
    print(f"    - Embedding dimension: {embeddings.shape[1]}")

    cursor.close()
    conn.close()

    print("\n" + "="*80)
    print("✓ Clustering successfully stored in database!")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Parse arguments
    n_clusters = 3
    if len(sys.argv) > 1:
        try:
            n_clusters = int(sys.argv[1])
        except ValueError:
            print(f"Invalid n_clusters: {sys.argv[1]}")
            sys.exit(1)

    cluster_papers(n_clusters=n_clusters)
