"""Tool: Database interface for retrieval operations."""
import json
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from sentence_transformers import SentenceTransformer

from .common import RetrievalResult


class Tool:
    """Database interface for retrieving paper data."""

    def __init__(self, db_conn, encoder: SentenceTransformer):
        """
        Initialize Tool with database connection and encoder.
        
        Args:
            db_conn: PostgreSQL connection
            encoder: SentenceTransformer encoder for embeddings
        """
        self.db_conn = db_conn
        self.encoder = encoder
        self.k = 5  # Top-k chunks to retrieve

    def vector_search(self, query: str) -> RetrievalResult:
        """
        Search using vector embeddings via pgvector.
        
        Args:
            query: Search query string
            
        Returns:
            RetrievalResult with retrieved chunks
        """
        # Embed the query
        query_embedding = self.encoder.encode(query, show_progress_bar=False)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)  # Normalize
        
        # Search pgvector
        cur = self.db_conn.cursor()
        cur.execute("""
            SELECT 
                ce.id, pc.text as content, ce.embedding, pc.paper_id,
                pc.section, p.title, p.cite_key, p.year,
                (1 - (ce.embedding <=> %s)) as similarity
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_id = pc.id
            JOIN papers p ON pc.paper_id = p.db_id
            ORDER BY similarity DESC
            LIMIT %s
        """, (json.dumps(query_embedding.tolist()), self.k))
        
        rows = cur.fetchall()
        cur.close()
        
        chunks = []
        paper_ids = set()
        total_similarity = 0
        
        for row in rows:
            chunk_id, content, embedding_json, paper_id, section, title, cite_key, year, similarity = row
            paper_ids.add(paper_id)
            total_similarity += similarity
            
            chunks.append({
                'content': content,
                'paper_id': paper_id,
                'title': title,
                'cite_key': cite_key,
                'year': year,
                'section': section,
                'similarity': similarity
            })
        
        return RetrievalResult(
            chunks=chunks,
            paper_count=len(paper_ids),
            total_similarity=total_similarity,
            search_method='vector_search'
        )

    def search_methodology(self, keywords: str) -> RetrievalResult:
        """
        Search structured methodology data from deep_analysis.
        
        Args:
            keywords: Search keywords
            
        Returns:
            RetrievalResult with chunks containing methodology info
        """
        cur = self.db_conn.cursor()
        cur.execute("""
            SELECT 
                ce.id, pc.text as content, pc.paper_id,
                pc.section, p.title, p.cite_key, p.year,
                0.8 as similarity
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_id = pc.id
            JOIN papers p ON pc.paper_id = p.db_id
            WHERE pc.section ILIKE %s OR pc.text ILIKE %s
            LIMIT %s
        """, (f'%{keywords}%', f'%{keywords}%', self.k))
        
        rows = cur.fetchall()
        cur.close()
        
        chunks = []
        paper_ids = set()
        
        for row in rows:
            chunk_id, content, paper_id, section, title, cite_key, year, similarity = row
            paper_ids.add(paper_id)
            
            chunks.append({
                'content': content,
                'paper_id': paper_id,
                'title': title,
                'cite_key': cite_key,
                'year': year,
                'section': section,
                'similarity': similarity
            })
        
        return RetrievalResult(
            chunks=chunks,
            paper_count=len(paper_ids),
            total_similarity=len(chunks) * 0.8,
            search_method='search_methodology'
        )

    def search_findings(self, keywords: str) -> RetrievalResult:
        """
        Search structured findings data.
        
        Args:
            keywords: Search keywords
            
        Returns:
            RetrievalResult with findings-related chunks
        """
        # Similar to methodology search but filtering for "findings" sections
        cur = self.db_conn.cursor()
        cur.execute("""
            SELECT 
                ce.id, pc.text as content, pc.paper_id,
                pc.section, p.title, p.cite_key, p.year,
                0.75 as similarity
            FROM chunk_embeddings ce
            JOIN paper_chunks pc ON ce.chunk_id = pc.id
            JOIN papers p ON pc.paper_id = p.db_id
            WHERE (pc.section ILIKE 'findings%' OR pc.section ILIKE 'results%')
                AND (pc.text ILIKE %s OR pc.text ILIKE %s)
            LIMIT %s
        """, (f'%{keywords}%', f'%{keywords}%', self.k))
        
        rows = cur.fetchall()
        cur.close()
        
        chunks = []
        paper_ids = set()
        
        for row in rows:
            chunk_id, content, paper_id, section, title, cite_key, year, similarity = row
            paper_ids.add(paper_id)
            
            chunks.append({
                'content': content,
                'paper_id': paper_id,
                'title': title,
                'cite_key': cite_key,
                'year': year,
                'section': section,
                'similarity': similarity
            })
        
        return RetrievalResult(
            chunks=chunks,
            paper_count=len(paper_ids),
            total_similarity=len(chunks) * 0.75,
            search_method='search_findings'
        )

    def deduplicate_results(self, result_list: List[RetrievalResult]) -> RetrievalResult:
        """
        Deduplicate and merge results from multiple searches.
        
        Args:
            result_list: List of RetrievalResult objects
            
        Returns:
            Merged RetrievalResult with deduplication
        """
        seen_chunks = {}  # Content -> best chunk
        paper_ids = set()
        
        for result in result_list:
            for chunk in result.chunks:
                content_key = chunk['content'][:50]  # Use first 50 chars as key
                
                if content_key not in seen_chunks:
                    seen_chunks[content_key] = chunk
                else:
                    # Keep chunk with higher similarity
                    if chunk['similarity'] > seen_chunks[content_key]['similarity']:
                        seen_chunks[content_key] = chunk
                
                paper_ids.add(chunk['paper_id'])
        
        merged_chunks = list(seen_chunks.values())
        total_similarity = sum(c['similarity'] for c in merged_chunks)
        
        return RetrievalResult(
            chunks=merged_chunks,
            paper_count=len(paper_ids),
            total_similarity=total_similarity,
            search_method='merged'
        )

    def filter_papers(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filter papers by criteria (year, keywords, etc).
        
        Args:
            criteria: Filter criteria dict
            
        Returns:
            List of matching papers
        """
        cur = self.db_conn.cursor()
        
        # Build WHERE clause based on criteria
        where_clauses = []
        params = []
        
        if 'year_min' in criteria:
            where_clauses.append('year >= %s')
            params.append(criteria['year_min'])
        
        if 'year_max' in criteria:
            where_clauses.append('year <= %s')
            params.append(criteria['year_max'])
        
        if 'keywords' in criteria:
            where_clauses.append('(title ILIKE %s OR abstract ILIKE %s)')
            params.extend([f"%{criteria['keywords']}%", f"%{criteria['keywords']}%"])
        
        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        
        cur.execute(f"""
            SELECT db_id, title, cite_key, year, abstract
            FROM papers
            WHERE {where_sql}
            ORDER BY year DESC
        """, params)
        
        papers = []
        for row in cur.fetchall():
            papers.append({
                'id': row[0],
                'title': row[1],
                'cite_key': row[2],
                'year': row[3],
                'abstract': row[4]
            })
        
        cur.close()
        return papers
