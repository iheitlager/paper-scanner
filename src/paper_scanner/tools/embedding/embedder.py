import sys
from typing import Dict, List

import numpy as np
# Embeddings
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    """
    Generate embeddings using sentence-transformers
    """

    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        """
        Initialize embedding model

        Options:
        - 'all-mpnet-base-v2': 768 dims, best quality
        - 'all-MiniLM-L6-v2': 384 dims, faster
        """
        print(f"Loading embedding model: {model_name}...", file=sys.stderr)
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Dimension: {self.dimension}", file=sys.stderr)

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple texts efficiently"""
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Embed all chunks and return with embeddings attached
        """

        # Extract texts
        chunk_texts = [c["content"] for c in chunks]

        # Generate embeddings
        embeddings = self.embed_batch(chunk_texts)

        # Attach embeddings to chunks
        enriched_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            enriched_chunk = chunk.copy()
            enriched_chunk["embedding"] = {
                "vector": embedding.tolist(),
                "model_name": self.model_name,
                "dimension": self.dimension,
            }
            enriched_chunks.append(enriched_chunk)

        return enriched_chunks

    def embed_paper(self, chunks: List[Dict], method: str = "aggregate_chunks") -> Dict[str]:
        """
        Generate paper-level embedding

        Methods:
        - 'aggregate_chunks': Average all chunk embeddings
        - 'first_chunk': Use first chunk (usually abstract/intro)
        """

        if method == "aggregate_chunks":
            # Average all chunk embeddings
            chunk_vectors = [c["embedding"]["vector"] for c in chunks]
            paper_vector = np.mean(chunk_vectors, axis=0)

        elif method == "first_chunk":
            # Use first chunk
            paper_vector = np.array(chunks[0]["embedding"]["vector"])

        else:
            raise ValueError(f"Unknown method: {method}")

        return {
            "vector": paper_vector.tolist(),
            "model_name": self.model_name,
            "dimension": self.dimension,
            "method": method,
        }
