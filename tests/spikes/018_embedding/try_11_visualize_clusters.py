#!/usr/bin/env python
"""
Visualize paper clusters in 2D and 3D space.

Uses t-SNE or PCA to reduce 768-dim embeddings to 2D/3D for visualization.
Shows cluster assignments, centroids, and paper relationships.

Usage:
    python try_11_visualize_clusters.py [method] [dim]

Examples:
    python try_11_visualize_clusters.py tsne 2     # t-SNE 2D (default)
    python try_11_visualize_clusters.py pca 2      # PCA 2D
    python try_11_visualize_clusters.py tsne 3     # t-SNE 3D
"""

import sys
import os
from dotenv import load_dotenv

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns
import psycopg2
from pgvector.psycopg2 import register_vector
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

# Load environment
load_dotenv()

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 10)
plt.rcParams["font.size"] = 10


def get_db_url():
    """Build database URL from env"""
    db_user = os.getenv("DB_USER", "pdfuser")
    db_password = os.getenv("DB_PASSWORD", "pdfpass")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "paper_scanner")
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class ClusterVisualizer:
    """Visualize paper clusters"""

    def __init__(self):
        self.conn = psycopg2.connect(get_db_url())
        register_vector(self.conn)
        self.load_data()

    def load_data(self):
        """Load papers, embeddings, and cluster assignments"""
        cursor = self.conn.cursor()

        # Load papers with embeddings and cluster assignments
        cursor.execute("""
            SELECT 
                p.db_id,
                p.cite_key,
                p.title,
                p.year,
                pe.embedding,
                COALESCE(pca.cluster_id, -1) as cluster_id,
                COALESCE(pc.cluster_name, 'Unclustered') as cluster_name,
                COALESCE(pca.distance_to_centroid, 0) as distance_to_centroid,
                COALESCE(pca.assignment_confidence, 0) as assignment_confidence
            FROM papers p
            JOIN paper_embeddings pe ON p.db_id = pe.paper_id
            LEFT JOIN paper_cluster_assignments pca ON p.db_id = pca.paper_id
            LEFT JOIN paper_clusters pc ON pca.cluster_id = pc.id
            ORDER BY p.cite_key
        """)

        results = cursor.fetchall()

        self.paper_ids = [r[0] for r in results]
        self.citekeys = [r[1] for r in results]
        self.titles = [r[2] for r in results]
        self.years = [r[3] if r[3] else 0 for r in results]
        self.embeddings = np.array([np.array(r[4]) for r in results])
        self.cluster_ids = [r[5] for r in results]
        self.cluster_names = [r[6] for r in results]
        self.distances = [r[7] for r in results]
        self.confidences = [r[8] for r in results]

        # Load cluster statistics and centroids
        cursor.execute("""
            SELECT 
                id,
                cluster_name,
                paper_count,
                avg_year,
                centroid_embedding
            FROM paper_clusters
            ORDER BY id
        """)

        cluster_results = cursor.fetchall()
        self.cluster_stats = cluster_results
        self.cluster_centroids = np.array(
            [np.array(r[4]) for r in cluster_results]
        ) if cluster_results else np.array([])

        cursor.close()

        print(f"\n{'='*80}")
        print("CLUSTER VISUALIZATION")
        print(f"{'='*80}")
        print(f"Loaded {len(self.paper_ids)} papers")
        print(f"Embedding dimension: {self.embeddings.shape[1]}")
        print(f"Number of clusters: {len(self.cluster_stats)}")
        print(f"Papers: {', '.join(self.citekeys)}")

    def reduce_dimensions(self, method="tsne", n_components=2):
        """Reduce embedding dimensions for visualization"""

        print(f"\nReducing dimensions using {method.upper()} to {n_components}D...")

        if method == "tsne":
            # Pre-process with PCA if high-dimensional
            n_samples = len(self.paper_ids)
            n_features = self.embeddings.shape[1]
            max_pca_components = min(50, n_samples - 1, n_features)

            pca = None
            if n_features > max_pca_components and max_pca_components > n_components:
                print(f"  Pre-processing with PCA: {n_features}D → {max_pca_components}D")
                pca = PCA(n_components=max_pca_components, random_state=42)
                embeddings_pca = pca.fit_transform(self.embeddings)
                print(f"  Explained variance: {pca.explained_variance_ratio_.sum():.2%}")
            else:
                embeddings_pca = self.embeddings
                pca = None

            # Adjust perplexity for small datasets
            perplexity = min(30, max(2, n_samples - 1))

            print(f"  Running t-SNE (perplexity={perplexity})...")
            tsne = TSNE(
                n_components=n_components,
                random_state=42,
                perplexity=perplexity,
                max_iter=1000,
                init="pca",
            )
            reduced = tsne.fit_transform(embeddings_pca)

            # Reduce centroids if we have them
            if len(self.cluster_centroids) > 0:
                if pca is not None:
                    centroids_pca = pca.transform(self.cluster_centroids)
                else:
                    centroids_pca = self.cluster_centroids
                # Project centroids using fitted TSNE (approximate)
                # Create a simple projection by finding nearest neighbors
                centroids_reduced = []
                for centroid_pca in centroids_pca:
                    # For each centroid, find its approximate 2D position
                    # by computing distance to each point and using weighted average
                    distances = np.linalg.norm(embeddings_pca - centroid_pca, axis=1)
                    weights = np.exp(-distances)
                    weights /= weights.sum()
                    centroid_2d = np.average(reduced, axis=0, weights=weights)
                    centroids_reduced.append(centroid_2d)
                centroids_reduced = np.array(centroids_reduced)
            else:
                centroids_reduced = None

        elif method == "pca":
            # Adjust n_components for small datasets
            max_components = min(n_components, len(self.paper_ids) - 1, self.embeddings.shape[1])
            print(f"  Using PCA with {max_components} components")
            pca = PCA(n_components=max_components, random_state=42)
            reduced = pca.fit_transform(self.embeddings)
            print(f"  Explained variance: {pca.explained_variance_ratio_.sum():.2%}")

            # Reduce centroids if we have them
            if len(self.cluster_centroids) > 0:
                centroids_reduced = pca.transform(self.cluster_centroids)
            else:
                centroids_reduced = None

        else:
            raise ValueError(f"Unknown method: {method}")

        return reduced, centroids_reduced

    def plot_clusters_2d(self, reduced, centroids_reduced):
        """Plot clusters in 2D"""

        fig, ax = plt.subplots(figsize=(14, 10))

        # Get unique clusters
        unique_clusters = sorted(set(c for c in self.cluster_ids if c > 0))
        colors = sns.color_palette("husl", len(unique_clusters) + 1)

        # Plot unclustered papers
        unclustered_mask = [c <= 0 for c in self.cluster_ids]
        if any(unclustered_mask):
            unclustered_idx = [i for i, m in enumerate(unclustered_mask) if m]
            ax.scatter(
                reduced[unclustered_idx, 0],
                reduced[unclustered_idx, 1],
                c="gray",
                marker="x",
                s=200,
                alpha=0.5,
                label="Unclustered",
                linewidths=2,
            )

        # Plot each cluster
        for cluster_id, color in zip(unique_clusters, colors):
            cluster_mask = [c == cluster_id for c in self.cluster_ids]
            cluster_idx = [i for i, m in enumerate(cluster_mask) if m]

            ax.scatter(
                reduced[cluster_idx, 0],
                reduced[cluster_idx, 1],
                c=[color],
                s=300,
                alpha=0.7,
                label=f"Cluster {cluster_id}",
                edgecolors="black",
                linewidths=1.5,
            )

        # Plot centroids
        if centroids_reduced is not None and len(centroids_reduced) > 0:
            ax.scatter(
                centroids_reduced[:, 0],
                centroids_reduced[:, 1],
                c="red",
                marker="*",
                s=800,
                edgecolors="black",
                linewidths=2,
                label="Centroids",
                zorder=5,
            )

        # Add labels
        for i, citekey in enumerate(self.citekeys):
            ax.annotate(
                citekey,
                xy=(reduced[i, 0], reduced[i, 1]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=9,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.3),
            )

        ax.set_xlabel("Dimension 1")
        ax.set_ylabel("Dimension 2")
        ax.set_title("Paper Clusters (2D Projection)")
        ax.legend(loc="best", fontsize=10)
        ax.grid(True, alpha=0.3)

        return fig

    def plot_clusters_3d(self, reduced, centroids_reduced):
        """Plot clusters in 3D"""

        fig = plt.figure(figsize=(16, 12))
        ax = fig.add_subplot(111, projection="3d")

        # Get unique clusters
        unique_clusters = sorted(set(c for c in self.cluster_ids if c > 0))
        colors = sns.color_palette("husl", len(unique_clusters) + 1)

        # Plot unclustered papers
        unclustered_mask = [c <= 0 for c in self.cluster_ids]
        if any(unclustered_mask):
            unclustered_idx = [i for i, m in enumerate(unclustered_mask) if m]
            ax.scatter(
                reduced[unclustered_idx, 0],
                reduced[unclustered_idx, 1],
                reduced[unclustered_idx, 2],
                c="gray",
                marker="x",
                s=200,
                alpha=0.5,
                label="Unclustered",
                linewidths=2,
            )

        # Plot each cluster
        for cluster_id, color in zip(unique_clusters, colors):
            cluster_mask = [c == cluster_id for c in self.cluster_ids]
            cluster_idx = [i for i, m in enumerate(cluster_mask) if m]

            ax.scatter(
                reduced[cluster_idx, 0],
                reduced[cluster_idx, 1],
                reduced[cluster_idx, 2],
                c=[color],
                s=300,
                alpha=0.7,
                label=f"Cluster {cluster_id}",
                edgecolors="black",
                linewidths=1.5,
            )

        # Plot centroids
        if centroids_reduced is not None and len(centroids_reduced) > 0:
            ax.scatter(
                centroids_reduced[:, 0],
                centroids_reduced[:, 1],
                centroids_reduced[:, 2],
                c="red",
                marker="*",
                s=800,
                edgecolors="black",
                linewidths=2,
                label="Centroids",
                zorder=5,
            )

        # Add labels
        for i, citekey in enumerate(self.citekeys):
            ax.text(
                reduced[i, 0],
                reduced[i, 1],
                reduced[i, 2],
                citekey,
                fontsize=9,
                fontweight="bold",
            )

        ax.set_xlabel("Dimension 1")
        ax.set_ylabel("Dimension 2")
        ax.set_zlabel("Dimension 3")
        ax.set_title("Paper Clusters (3D Projection)")
        ax.legend(loc="best", fontsize=10)

        return fig

    def print_statistics(self):
        """Print cluster statistics"""

        print(f"\n{'='*80}")
        print("CLUSTER STATISTICS")
        print(f"{'='*80}")

        for cluster_info in self.cluster_stats:
            cluster_id, cluster_name, paper_count, avg_year, _ = cluster_info

            # Get papers in this cluster
            cluster_papers = [
                (ck, y) for ck, y, c in zip(self.citekeys, self.years, self.cluster_ids)
                if c == cluster_id
            ]

            print(f"\n{cluster_name} (ID: {cluster_id})")
            print(f"  Papers: {paper_count}")
            print(f"  Avg year: {avg_year if avg_year else 'N/A'}")
            print(f"  Members: {', '.join([ck for ck, _ in cluster_papers])}")

        print(f"\n{'='*80}\n")

    def visualize(self, method="tsne", dim=2):
        """Generate visualizations"""

        reduced, centroids_reduced = self.reduce_dimensions(method=method, n_components=dim)

        self.print_statistics()

        if dim == 2:
            fig = self.plot_clusters_2d(reduced, centroids_reduced)
        elif dim == 3:
            fig = self.plot_clusters_3d(reduced, centroids_reduced)
        else:
            raise ValueError(f"Unsupported dimension: {dim}")

        plt.tight_layout()

        # Save figure
        output_file = f"clusters_{method}_{dim}d.png"
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        print(f"✓ Saved visualization to {output_file}")

        plt.show()

        self.conn.close()


if __name__ == "__main__":
    # Parse arguments
    method = "tsne"
    dim = 2

    if len(sys.argv) > 1:
        method = sys.argv[1].lower()
    if len(sys.argv) > 2:
        try:
            dim = int(sys.argv[2])
        except ValueError:
            print(f"Invalid dimension: {sys.argv[2]}")
            sys.exit(1)

    if method not in ["tsne", "pca"]:
        print(f"Invalid method: {method}. Use 'tsne' or 'pca'")
        sys.exit(1)

    if dim not in [2, 3]:
        print(f"Invalid dimension: {dim}. Use 2 or 3")
        sys.exit(1)

    visualizer = ClusterVisualizer()
    visualizer.visualize(method=method, dim=dim)
