"""Memory: Caching and history management."""
import json
import time
import tempfile
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

from .common import PipelineMetrics


class Memory:
    """Manages query caching and interaction history."""

    def __init__(self, encoder: SentenceTransformer, history_db: Optional[str] = None):
        """
        Initialize Memory with encoder and history storage.
        
        Args:
            encoder: SentenceTransformer for query similarity
            history_db: Path to SQLite history database (defaults to temp directory)
        """
        self.encoder = encoder
        
        # Use temp directory if no path provided
        if history_db is None:
            temp_dir = tempfile.gettempdir()
            history_db = os.path.join(temp_dir, ".rag_history.db")
        
        self.history_db = history_db
        self.query_cache = {}  # In-memory cache: question_hash -> results
        self.similarity_threshold = 0.85  # For cache hit detection
        
        self._init_history_db()

    def _init_history_db(self):
        """Initialize SQLite database for history."""
        conn = sqlite3.connect(self.history_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                question TEXT,
                answer TEXT,
                chunks_count INTEGER,
                papers_count INTEGER,
                coverage REAL,
                relevance REAL,
                freshness REAL,
                plan_type TEXT,
                total_tokens INTEGER,
                total_time_ms REAL
            )
        """)
        conn.commit()
        conn.close()

    def find_similar_query(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Find previously cached result for similar question.
        
        Args:
            question: Current question
            
        Returns:
            Cached result if found, None otherwise
        """
        question_embedding = self.encoder.encode(question)
        question_embedding = question_embedding / np.linalg.norm(question_embedding)
        
        best_match = None
        best_similarity = 0
        
        for cached_question, cached_result in self.query_cache.items():
            cached_embedding = self.encoder.encode(cached_question)
            cached_embedding = cached_embedding / np.linalg.norm(cached_embedding)
            
            # Cosine similarity
            similarity = np.dot(question_embedding, cached_embedding)
            
            if similarity > best_similarity and similarity > self.similarity_threshold:
                best_match = cached_result
                best_similarity = similarity
        
        return best_match

    def store_interaction(self,
                         question: str,
                         answer: str,
                         chunks_count: int,
                         papers_count: int,
                         quality_score: Optional[Any],
                         plan_type: str,
                         metrics: PipelineMetrics):
        """
        Store interaction in cache and history database.
        
        Args:
            question: User question
            answer: Generated answer
            chunks_count: Number of chunks retrieved
            papers_count: Number of unique papers
            quality_score: QualityScore object from Evaluator
            plan_type: Type of plan used
            metrics: PipelineMetrics from execution
        """
        # Cache in-memory
        cache_result = {
            'question': question,
            'answer': answer,
            'chunks_count': chunks_count,
            'papers_count': papers_count,
            'timestamp': datetime.now().isoformat()
        }
        self.query_cache[question] = cache_result
        
        # Store in database
        conn = sqlite3.connect(self.history_db)
        conn.execute("""
            INSERT INTO interactions 
            (timestamp, question, answer, chunks_count, papers_count, 
             coverage, relevance, freshness, plan_type, total_tokens, total_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            question,
            answer,
            chunks_count,
            papers_count,
            quality_score.coverage if quality_score else 0,
            quality_score.relevance if quality_score else 0,
            quality_score.freshness if quality_score else 0,
            plan_type,
            metrics.total_tokens,
            metrics.total_time_ms
        ))
        conn.commit()
        conn.close()

    def get_conversation_context(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get last N interactions for conversation context.
        
        Args:
            n: Number of interactions to retrieve
            
        Returns:
            List of recent interactions
        """
        conn = sqlite3.connect(self.history_db)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT question, answer, timestamp
            FROM interactions
            ORDER BY timestamp DESC
            LIMIT ?
        """, (n,))
        
        interactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return list(reversed(interactions))  # Chronological order

    def invalidate_cache(self):
        """Clear cache when corpus changes."""
        self.query_cache.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache and history statistics."""
        conn = sqlite3.connect(self.history_db)
        
        cursor = conn.execute("SELECT COUNT(*) FROM interactions")
        total_interactions = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT AVG(coverage), AVG(relevance), AVG(total_tokens) FROM interactions")
        avg_coverage, avg_relevance, avg_tokens = cursor.fetchone()
        
        conn.close()
        
        return {
            'cache_size': len(self.query_cache),
            'total_interactions': total_interactions,
            'avg_coverage': avg_coverage or 0,
            'avg_relevance': avg_relevance or 0,
            'avg_tokens': avg_tokens or 0
        }
