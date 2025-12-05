#!/usr/bin/env python3
"""
Semantic Screening Utilities

Shared utilities for embedding-based paper screening and similarity analysis.
Can be imported and used by other screening stages or analysis scripts.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.distance import cosine
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Manager for generating and comparing embeddings."""
    
    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        """Initialize embedding manager.
        
        Args:
            model_name: Sentence transformer model to use
                - 'all-mpnet-base-v2': 768 dims, best quality (default)
                - 'all-MiniLM-L6-v2': 384 dims, faster
        """
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.dimension: Optional[int] = None
    
    def load_model(self) -> SentenceTransformer:
        """Load embedding model (lazy loading)."""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Dimension: {self.dimension}")
        return self.model
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        model = self.load_model()
        return model.encode(text, convert_to_numpy=True)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embed multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            
        Returns:
            Array of embeddings (n_texts, dimension)
        """
        model = self.load_model()
        return model.encode(texts, batch_size=batch_size, 
                          show_progress_bar=False, convert_to_numpy=True)
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score (0-1, where 1 is identical)
        """
        # Flatten if needed
        emb1 = embedding1.flatten() if embedding1.ndim > 1 else embedding1
        emb2 = embedding2.flatten() if embedding2.ndim > 1 else embedding2
        
        # Cosine similarity = 1 - cosine_distance
        distance = cosine(emb1, emb2)
        similarity = 1 - distance
        
        # Clamp to [0, 1]
        return float(max(0, min(1, similarity)))
    
    def compute_similarities_batch(self, query_embedding: np.ndarray, 
                                  candidate_embeddings: np.ndarray) -> np.ndarray:
        """Compute similarities between query and multiple candidates.
        
        Args:
            query_embedding: Query embedding (dimension,)
            candidate_embeddings: Candidate embeddings (n_candidates, dimension)
            
        Returns:
            Array of similarity scores (n_candidates,)
        """
        query = query_embedding.flatten() if query_embedding.ndim > 1 else query_embedding
        
        similarities = []
        for candidate in candidate_embeddings:
            cand = candidate.flatten() if candidate.ndim > 1 else candidate
            sim = self.compute_similarity(query, cand)
            similarities.append(sim)
        
        return np.array(similarities)


class PaperEmbedder:
    """Utilities for embedding papers."""
    
    def __init__(self, embedding_manager: EmbeddingManager):
        """Initialize paper embedder.
        
        Args:
            embedding_manager: EmbeddingManager instance
        """
        self.embedding_manager = embedding_manager
    
    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Normalize text for embedding.
        
        Args:
            text: Text to normalize
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        return text.strip()
    
    def combine_paper_text(self, title: Optional[str] = None, 
                          abstract: Optional[str] = None,
                          keywords: Optional[List[str]] = None,
                          full_text: Optional[str] = None) -> str:
        """Combine paper components into single text for embedding.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            keywords: List of keywords
            full_text: Full paper text (optional, usually too long)
            
        Returns:
            Combined text for embedding
        """
        parts = []
        
        if title:
            parts.append(self.normalize_text(title))
        
        if abstract:
            parts.append(self.normalize_text(abstract))
        
        if keywords:
            keywords_str = ' '.join([self.normalize_text(kw) for kw in keywords if kw])
            if keywords_str:
                parts.append(keywords_str)
        
        # Full text is usually too long, use only if specified and others missing
        if full_text and not abstract:
            # Truncate to first 512 words
            words = full_text.split()[:512]
            parts.append(' '.join(words))
        
        combined = ' '.join(parts)
        return combined.strip() if combined else "No text available"
    
    def embed_paper(self, title: Optional[str] = None,
                   abstract: Optional[str] = None,
                   keywords: Optional[List[str]] = None) -> np.ndarray:
        """Embed paper based on title, abstract, and keywords.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            keywords: List of keywords
            
        Returns:
            Paper embedding vector
        """
        combined_text = self.combine_paper_text(title, abstract, keywords)
        return self.embedding_manager.embed_text(combined_text)
    
    def embed_papers_batch(self, papers: List[Dict]) -> List[np.ndarray]:
        """Embed multiple papers efficiently.
        
        Args:
            papers: List of paper dicts with 'title', 'abstract', 'keywords'
            
        Returns:
            List of embedding vectors
        """
        texts = []
        for paper in papers:
            text = self.combine_paper_text(
                paper.get('title'),
                paper.get('abstract'),
                paper.get('keywords')
            )
            texts.append(text)
        
        return [emb for emb in self.embedding_manager.embed_batch(texts)]


class SimilarityClassifier:
    """Classify papers based on similarity thresholds."""
    
    def __init__(self, threshold_include: float = 0.65,
                 threshold_manual_review: float = 0.55):
        """Initialize classifier.
        
        Args:
            threshold_include: Similarity threshold for inclusion
            threshold_manual_review: Similarity threshold for manual review
        """
        self.threshold_include = threshold_include
        self.threshold_manual_review = threshold_manual_review
    
    def classify(self, similarity: float) -> Tuple[str, str, Optional[str]]:
        """Classify paper based on similarity.
        
        Args:
            similarity: Similarity score (0-1)
            
        Returns:
            Tuple of (stage, decision, reason)
            - stage: 'pass', 'review', 'fail'
            - decision: 'include', 'manual_review', 'exclude'
            - reason: Reason if not included
        """
        if similarity >= self.threshold_include:
            return 'pass', 'include', None
        elif similarity >= self.threshold_manual_review:
            return 'review', 'manual_review', \
                   f'Borderline similarity ({similarity:.4f}): requires manual review'
        else:
            return 'fail', 'exclude', \
                   f'Low semantic similarity ({similarity:.4f})'
    
    def batch_classify(self, similarities: np.ndarray) -> List[Tuple[str, str, Optional[str]]]:
        """Classify multiple papers at once.
        
        Args:
            similarities: Array of similarity scores
            
        Returns:
            List of (stage, decision, reason) tuples
        """
        return [self.classify(float(sim)) for sim in similarities]


def create_research_question_embedding(research_question: str,
                                      model_name: str = "all-mpnet-base-v2") -> np.ndarray:
    """Create embedding for research question.
    
    Args:
        research_question: Research question text
        model_name: Model to use
        
    Returns:
        Research question embedding
    """
    manager = EmbeddingManager(model_name)
    return manager.embed_text(research_question)


def compare_paper_to_question(paper: Dict, research_question: str,
                             model_name: str = "all-mpnet-base-v2") -> float:
    """Compute similarity between paper and research question.
    
    Args:
        paper: Paper dict with 'title', 'abstract', 'keywords'
        research_question: Research question text
        model_name: Model to use
        
    Returns:
        Similarity score
    """
    manager = EmbeddingManager(model_name)
    
    # Embed question and paper
    question_emb = manager.embed_text(research_question)
    
    paper_embedder = PaperEmbedder(manager)
    paper_emb = paper_embedder.embed_paper(
        paper.get('title'),
        paper.get('abstract'),
        paper.get('keywords')
    )
    
    # Compute similarity
    return manager.compute_similarity(question_emb, paper_emb)
