#!/usr/bin/env python3
"""
Cluster papers and store in database
"""

import json

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector  # Add this import
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def cluster_papers(conn, n_clusters=5):
    """
    Cluster papers using K-means
    """

    cursor = conn.cursor()

    # IMPORTANT: Register pgvector type converter
    register_vector(conn)

    # Step 1: Load all paper embeddings
    cursor.execute("""
        SELECT p.id, p.citekey, p.title, p.year, pe.embedding
        FROM papers p
        JOIN paper_embeddings pe ON p.id = pe.paper_id
        WHERE pe.embedding_method = 'aggregate_chunks'
    """)

    results = cursor.fetchall()
    paper_ids = [r[0] for r in results]
    citekeys = [r[1] for r in results]
    titles = [r[2] for r in results]
    years = [r[3] for r in results]

    # Convert embeddings to numpy array
    # After register_vector, embeddings come back as numpy arrays
    embeddings = np.array([np.array(r[4]) for r in results])

    print(f"Loaded {len(paper_ids)} papers")
    print(f"Embedding shape: {embeddings.shape}")

    # Check if we have enough papers for clustering
    if len(paper_ids) < n_clusters:
        print(f"Warning: Only {len(paper_ids)} papers, reducing clusters to {len(paper_ids)}")
        n_clusters = max(2, len(paper_ids))  # At least 2 clusters

    # Step 2: Run clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    centroids = kmeans.cluster_centers_

    # Calculate quality score
    if len(paper_ids) >= n_clusters:
        silhouette = silhouette_score(embeddings, labels)
        print(f"Silhouette score: {silhouette:.3f}")
    else:
        silhouette = None

    # Step 3: Analyze clusters
    for cluster_id in range(n_clusters):
        cluster_papers = [
            (pid, ck, t, y)
            for pid, ck, t, y, label in zip(paper_ids, citekeys, titles, years, labels)
            if label == cluster_id
        ]

        cluster_years = [y for _, _, _, y in cluster_papers if y]
        avg_year = np.mean(cluster_years) if cluster_years else None

        # Generate cluster name (using most common words in titles)
        cluster_titles = [t for _, _, t, _ in cluster_papers]
        cluster_name = f"Cluster {cluster_id + 1}"  # Could use LLM here

        print(f"\n{cluster_name}: {len(cluster_papers)} papers")
        if avg_year:
            print(f"  Avg year: {avg_year:.1f}")
        print(f"  Papers: {', '.join(ck for _, ck, _, _ in cluster_papers)}")

        # Step 4: Insert cluster into database
        centroid_str = "[" + ",".join(map(str, centroids[cluster_id])) + "]"

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
                json.dumps({"n_clusters": n_clusters, "silhouette_score": silhouette if silhouette else None}),
                len(cluster_papers),
                float(avg_year) if avg_year else None,
                centroid_str,
            ),
        )

        db_cluster_id = cursor.fetchone()[0]

        # Step 5: Assign papers to cluster
        for paper_id, _, _, _ in cluster_papers:
            # Calculate distance to centroid
            paper_idx = paper_ids.index(paper_id)
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
                (paper_id, db_cluster_id, float(distance), float(confidence)),
            )

    conn.commit()
    cursor.close()

    print(f"\n✓ Clustering complete. Created {n_clusters} clusters.")


if __name__ == "__main__":
    # Connect to database
    conn = psycopg2.connect("postgresql://pdfuser:pdfpass@localhost:5432/pdfdb")

    # Run clustering (use smaller number for 7 papers)
    cluster_papers(conn, n_clusters=3)  # 3 clusters for 7 papers

    conn.close()
