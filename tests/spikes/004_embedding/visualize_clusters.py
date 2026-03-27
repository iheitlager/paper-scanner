#!/usr/bin/env python3
"""
Paper Clustering Visualization

Creates visualizations:
1. 2D scatter plot of papers (t-SNE projection)
2. Cluster statistics bar chart
3. Timeline showing cluster evolution
4. Network graph of paper relationships

Usage:
    python visualize_clusters.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import psycopg2
import seaborn as sns
from pgvector.psycopg2 import register_vector
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (16, 12)
plt.rcParams["font.size"] = 10


class ClusterVisualizer:
    """
    Visualize paper clusters
    """

    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        register_vector(self.conn)
        self.load_data()

    def load_data(self):
        """Load papers, embeddings, and cluster assignments"""

        cursor = self.conn.cursor()

        # Load papers with embeddings and cluster assignments
        cursor.execute("""
            SELECT
                p.id,
                p.citekey,
                p.title,
                p.year,
                p.authors,
                pe.embedding,
                c.id as cluster_id,
                c.cluster_name,
                pca.distance_to_centroid,
                pca.assignment_confidence
            FROM papers p
            JOIN paper_embeddings pe ON p.id = pe.paper_id
            LEFT JOIN paper_cluster_assignments pca ON p.id = pca.paper_id
            LEFT JOIN paper_clusters c ON pca.cluster_id = c.id
            WHERE pe.embedding_method = 'aggregate_chunks'
            ORDER BY p.year, p.citekey
        """)

        results = cursor.fetchall()

        self.paper_ids = [r[0] for r in results]
        self.citekeys = [r[1] for r in results]
        self.titles = [r[2] for r in results]
        self.years = [r[3] if r[3] else 0 for r in results]
        self.authors = [r[4] for r in results]
        self.embeddings = np.array([np.array(r[5]) for r in results])
        self.cluster_ids = [r[6] if r[6] else -1 for r in results]
        self.cluster_names = [r[7] if r[7] else "Unclustered" for r in results]
        self.distances = [r[8] if r[8] else 0 for r in results]
        self.confidences = [r[9] if r[9] else 0 for r in results]

        # Load cluster statistics
        cursor.execute("""
            SELECT
                c.id,
                c.cluster_name,
                c.paper_count,
                c.avg_year,
                c.top_keywords
            FROM paper_clusters c
            ORDER BY c.id
        """)

        self.cluster_stats = cursor.fetchall()

        cursor.close()

        print(f"Loaded {len(self.paper_ids)} papers")
        print(f"Embedding dimension: {self.embeddings.shape[1]}")
        print(f"Number of clusters: {len(set(self.cluster_ids))}")

    def reduce_dimensions(self, method="tsne", n_components=2):
        """
        Reduce embedding dimensions for visualization

        Methods:
        - 'tsne': t-SNE (better for visualization, slower)
        - 'pca': PCA (faster, linear)
        """

        print(f"Reducing dimensions using {method.upper()}...")

        if method == "tsne":
            # Adjust PCA components based on number of samples
            n_samples = len(self.paper_ids)
            n_features = self.embeddings.shape[1]

            # PCA components must be min(n_samples, n_features, 50)
            max_pca_components = min(50, n_samples - 1, n_features)

            # Use PCA first to speed up t-SNE (only if we have enough samples)
            if n_features > max_pca_components and max_pca_components > n_components:
                print(f"  Pre-processing with PCA: {n_features}D → {max_pca_components}D")
                pca = PCA(n_components=max_pca_components, random_state=42)
                embeddings_pca = pca.fit_transform(self.embeddings)
                print(f"  Explained variance: {pca.explained_variance_ratio_.sum():.2%}")
            else:
                embeddings_pca = self.embeddings

            # Adjust perplexity for small datasets
            # Perplexity should be less than n_samples
            perplexity = min(30, max(2, n_samples - 1))

            print(f"  Running t-SNE (perplexity={perplexity})...")
            tsne = TSNE(
                n_components=n_components,
                random_state=42,
                perplexity=perplexity,
                max_iter=1000,
                init="pca",  # Better initialization
            )
            reduced = tsne.fit_transform(embeddings_pca)

        elif method == "pca":
            # Adjust n_components for small datasets
            max_components = min(n_components, len(self.paper_ids) - 1, self.embeddings.shape[1])

            pca = PCA(n_components=max_components, random_state=42)
            reduced = pca.fit_transform(self.embeddings)
            print(f"Explained variance: {pca.explained_variance_ratio_.sum():.2%}")

        else:
            raise ValueError(f"Unknown method: {method}")

        print(f"  Final shape: {reduced.shape}")
        return reduced

    def plot_cluster_scatter(self, reduced_embeddings, output_path="cluster_scatter.png"):
        """
        Plot 2D scatter of papers colored by cluster
        """

        fig, ax = plt.subplots(figsize=(14, 10))

        # Get unique clusters
        unique_clusters = sorted(set(self.cluster_ids))
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_clusters)))

        # Plot each cluster
        for cluster_id, color in zip(unique_clusters, colors):
            mask = [cid == cluster_id for cid in self.cluster_ids]
            cluster_name = next(
                (name for cid, name in zip(self.cluster_ids, self.cluster_names) if cid == cluster_id),
                f"Cluster {cluster_id}",
            )

            ax.scatter(
                reduced_embeddings[mask, 0],
                reduced_embeddings[mask, 1],
                c=[color],
                label=cluster_name,
                s=200,
                alpha=0.7,
                edgecolors="black",
                linewidth=1.5,
            )

            # Add labels for each paper
            for i, (x, y, citekey) in enumerate(
                zip(
                    reduced_embeddings[mask, 0],
                    reduced_embeddings[mask, 1],
                    [ck for ck, m in zip(self.citekeys, mask) if m],
                )
            ):
                ax.annotate(
                    citekey,
                    (x, y),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.3),
                    alpha=0.8,
                )

        ax.set_xlabel("Dimension 1", fontsize=12, fontweight="bold")
        ax.set_ylabel("Dimension 2", fontsize=12, fontweight="bold")
        ax.set_title("Paper Clusters (2D Projection)", fontsize=16, fontweight="bold", pad=20)

        ax.legend(title="Clusters", title_fontsize=12, fontsize=10, loc="best", framealpha=0.9)

        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✓ Saved: {output_path}")
        plt.close()

    def plot_cluster_stats(self, output_path="cluster_stats.png"):
        """
        Plot cluster statistics bar charts
        """

        if not self.cluster_stats:
            print("No cluster statistics available")
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        cluster_names = [c[1] for c in self.cluster_stats]
        paper_counts = [c[2] for c in self.cluster_stats]
        avg_years = [c[3] if c[3] else 0 for c in self.cluster_stats]

        colors = plt.cm.Set3(np.linspace(0, 1, len(cluster_names)))

        # 1. Paper count per cluster
        ax = axes[0, 0]
        bars = ax.barh(cluster_names, paper_counts, color=colors, edgecolor="black", linewidth=1.5)
        ax.set_xlabel("Number of Papers", fontsize=12, fontweight="bold")
        ax.set_title("Papers per Cluster", fontsize=14, fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + 0.1,
                bar.get_y() + bar.get_height() / 2,
                f"{int(width)}",
                ha="left",
                va="center",
                fontweight="bold",
            )

        # 2. Average year per cluster
        ax = axes[0, 1]
        bars = ax.barh(cluster_names, avg_years, color=colors, edgecolor="black", linewidth=1.5)
        ax.set_xlabel("Average Year", fontsize=12, fontweight="bold")
        ax.set_title("Average Publication Year", fontsize=14, fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

        # Add value labels
        for bar in bars:
            width = bar.get_width()
            if width > 0:
                ax.text(
                    width + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(width)}",
                    ha="left",
                    va="center",
                    fontweight="bold",
                )

        # 3. Cluster confidence distribution
        ax = axes[1, 0]
        unique_clusters = sorted(set(self.cluster_ids))

        confidence_data = []
        labels = []

        for cluster_id in unique_clusters:
            cluster_confidences = [
                float(conf) if conf else 0.0
                for cid, conf in zip(self.cluster_ids, self.confidences)
                if cid == cluster_id
            ]
            if cluster_confidences:
                confidence_data.append(cluster_confidences)
                cluster_name = next((c[1] for c in self.cluster_stats if c[0] == cluster_id), f"Cluster {cluster_id}")
                labels.append(cluster_name)

        if confidence_data:
            bp = ax.boxplot(confidence_data, tick_labels=labels, patch_artist=True, showmeans=True)

            # Color boxes
            for patch, color in zip(bp["boxes"], colors):
                patch.set_facecolor(color)
                patch.set_edgecolor("black")
                patch.set_linewidth(1.5)

            ax.set_ylabel("Assignment Confidence", fontsize=12, fontweight="bold")
            ax.set_title("Cluster Assignment Confidence", fontsize=14, fontweight="bold")
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ax.grid(axis="y", alpha=0.3)

        # 4. Papers by year and cluster
        ax = axes[1, 1]

        # Group papers by year and cluster
        year_cluster_counts = {}
        for year, cluster_id in zip(self.years, self.cluster_ids):
            if year > 0:
                if year not in year_cluster_counts:
                    year_cluster_counts[year] = {}
                year_cluster_counts[year][cluster_id] = year_cluster_counts[year].get(cluster_id, 0) + 1

        if year_cluster_counts:
            years_sorted = sorted(year_cluster_counts.keys())
            unique_clusters = sorted(set(cid for cid in self.cluster_ids if cid >= 0))

            # Prepare data for stacked bar chart
            cluster_data = {}
            for cluster_id in unique_clusters:
                cluster_data[cluster_id] = [year_cluster_counts[year].get(cluster_id, 0) for year in years_sorted]

            # Plot stacked bars
            bottom = np.zeros(len(years_sorted))
            for i, cluster_id in enumerate(unique_clusters):
                cluster_name = next((c[1] for c in self.cluster_stats if c[0] == cluster_id), f"Cluster {cluster_id}")
                ax.bar(
                    years_sorted,
                    cluster_data[cluster_id],
                    bottom=bottom,
                    label=cluster_name,
                    color=colors[i],
                    edgecolor="black",
                    linewidth=1,
                )
                bottom += cluster_data[cluster_id]

            ax.set_xlabel("Year", fontsize=12, fontweight="bold")
            ax.set_ylabel("Number of Papers", fontsize=12, fontweight="bold")
            ax.set_title("Papers by Year and Cluster", fontsize=14, fontweight="bold")
            ax.legend(fontsize=9, loc="upper left")
            ax.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✓ Saved: {output_path}")
        plt.close()

    def plot_cluster_heatmap(self, output_path="cluster_heatmap.png"):
        """
        Plot similarity heatmap between papers
        """

        from scipy.cluster.hierarchy import dendrogram, linkage
        from scipy.spatial.distance import pdist, squareform

        fig, ax = plt.subplots(figsize=(14, 12))

        # Calculate cosine similarity matrix
        similarity_matrix = 1 - squareform(pdist(self.embeddings, metric="cosine"))

        # Create hierarchical clustering
        linkage_matrix = linkage(self.embeddings, method="ward")

        # Reorder based on clustering
        dendro = dendrogram(linkage_matrix, no_plot=True)
        order = dendro["leaves"]

        similarity_matrix_ordered = similarity_matrix[order][:, order]
        citekeys_ordered = [self.citekeys[i] for i in order]

        # Plot heatmap
        im = ax.imshow(similarity_matrix_ordered, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

        # Set ticks
        ax.set_xticks(range(len(citekeys_ordered)))
        ax.set_yticks(range(len(citekeys_ordered)))
        ax.set_xticklabels(citekeys_ordered, rotation=90, fontsize=9)
        ax.set_yticklabels(citekeys_ordered, fontsize=9)

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Similarity", fontsize=12, fontweight="bold")

        ax.set_title("Paper Similarity Matrix", fontsize=16, fontweight="bold", pad=20)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✓ Saved: {output_path}")
        plt.close()

    def plot_dendrogram(self, output_path="cluster_dendrogram.png"):
        """
        Plot hierarchical clustering dendrogram
        """

        from scipy.cluster.hierarchy import dendrogram, linkage

        fig, ax = plt.subplots(figsize=(14, 8))

        # Perform hierarchical clustering
        linkage_matrix = linkage(self.embeddings, method="ward")

        # Plot dendrogram
        dendrogram(linkage_matrix, labels=self.citekeys, leaf_rotation=90, leaf_font_size=10, ax=ax)

        ax.set_xlabel("Papers", fontsize=12, fontweight="bold")
        ax.set_ylabel("Distance", fontsize=12, fontweight="bold")
        ax.set_title("Hierarchical Clustering Dendrogram", fontsize=16, fontweight="bold", pad=20)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✓ Saved: {output_path}")
        plt.close()

    def create_all_visualizations(self, output_dir="visualizations"):
        """
        Create all visualizations
        """

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print("Creating visualizations...")
        print("")

        # 1. Reduce dimensions
        reduced_tsne = self.reduce_dimensions("tsne")

        # 2. Scatter plot
        print("Creating cluster scatter plot...")
        self.plot_cluster_scatter(reduced_tsne, output_path / "cluster_scatter.png")

        # 3. Statistics
        print("Creating cluster statistics...")
        self.plot_cluster_stats(output_path / "cluster_stats.png")

        # 4. Heatmap
        print("Creating similarity heatmap...")
        self.plot_cluster_heatmap(output_path / "cluster_heatmap.png")

        # 5. Dendrogram
        print("Creating dendrogram...")
        self.plot_dendrogram(output_path / "cluster_dendrogram.png")

        print("")
        print("=" * 60)
        print("✓ All visualizations created!")
        print(f"  Output directory: {output_path.absolute()}")
        print("=" * 60)


def main():
    """Main entry point"""

    # Connection string
    connection_string = "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"

    try:
        # Create visualizer
        viz = ClusterVisualizer(connection_string)

        # Create all visualizations
        viz.create_all_visualizations("visualizations")

    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        print("")
        print("Make sure PostgreSQL is running:")
        print("  docker-compose up -d pdf-browser-db")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
