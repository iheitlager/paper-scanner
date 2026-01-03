# Spike 018: Structured Paper Embeddings

## Objective

Implement a sophisticated embedding system that respects paper document structure (title, abstract, keywords, sections) and enables semantic search, clustering, and paper similarity matching. Store embeddings in-memory initially, with SQL persistence as a second phase.

## Hypothesis

**Core Premise**: By embedding papers at multiple structural levels (title, abstract, keywords, full-text, individual sections) rather than as monolithic documents, we can:
1. Achieve more nuanced semantic search capabilities (find papers discussing specific topics in methodology vs. results)
2. Enable better clustering and similarity matching based on actual paper structure
3. Support hierarchical retrieval (search across full papers → narrow to sections → extract relevant content)
4. Build a foundation for section-level citation tracking and reference linking

## Goals

- [x] Design structured embedding strategy respecting paper components (title, abstract, keywords, sections)
- [x] Implement in-memory embedding storage with efficient lookup structures (`Embedding` class in `src/paper_scanner/core/models.py`)
- [x] Research and select best embedding models for scientific papers (started with `all-mpnet-base-v2`)
- [x] Create embedding pipeline that processes papers and their sections (`test_01_embedding_pipeline.py`)
- [x] Develop semantic search across embeddings (query-based search implemented)
- [x] Implement paper similarity and clustering using embedded vectors (cosine similarity matching)
- [x] Create production step and documentation (`GenerateEmbeddingsStep` with full unit tests)
- [x] Design schema for SQL persistence (pgvector extension) - `EmbeddingToRowConverter` + `insert_embeddings()` implemented
- [ ] Evaluate quality metrics (semantic relevance, clustering coherence)

## Key Research Questions

1. **Model Selection**: Which embedding model is best for scientific papers?
   - General: `all-mpnet-base-v2` (768 dims, good performance)
   - Domain-specific: `allenai/specter` (768 dims, trained on citations)
   - Hybrid: Combine multiple models for different paper aspects
   
2. **Embedding Granularity**: What level should we embed?
   - Full paper (title + abstract + keywords concatenated)
   - Per-section (methodology, results, discussion separately)
   - Both (hierarchical approach)
   
3. **In-Memory Storage**: How to efficiently store and query vectors?
   - NumPy arrays with metadata indices
   - FAISS (Facebook AI Similarity Search) for approximate nearest neighbor
   - Simple dict-based index for MVP

4. **Section Detection**: How to identify sections from PDF text?
   - Rule-based pattern matching (common headings: Introduction, Methods, Results, etc.)
   - LLM-based section detection (using Claude)
   - Structural cues from document layout

## Implementation Phases

### Phase 1: MVP (In-Memory)
1. Load papers from database with title, abstract, keywords
2. Generate embeddings using selected model
3. Store in-memory with simple dict/list structure
4. Implement basic semantic search (k-nearest neighbors)
5. Test with existing paper collections

### Phase 2: Enhanced Metadata
1. Extract section boundaries from full text
2. Generate embeddings for each section + paper-level
3. Build hierarchical index (paper → sections → chunks)
4. Implement section-aware search

### Phase 3: SQL Persistence
1. Create PostgreSQL schema with pgvector extension
2. Persist embeddings to database
3. Benchmark query performance
4. Build caching layer for frequent searches

### Phase 4: Integration
1. Add embedding generation to bibtex_import and PDF processing steps
2. Integrate semantic search into Web UI
3. Add paper similarity/clustering features
4. Build visualization of embedding space

## Technical Approach

### Data Structure (In-Memory)
```python
{
    'paper_id': {
        'title': 'Paper Title',
        'title_embedding': [...768 dims...],
        'abstract': 'Abstract text...',
        'abstract_embedding': [...768 dims...],
        'keywords': ['kw1', 'kw2'],
        'keywords_embedding': [...768 dims...],
        'sections': {
            'introduction': {
                'text': '...',
                'embedding': [...768 dims...]
            },
            'methodology': {...},
            ...
        }
    }
}
```

### Similarity Search
- L2 distance or cosine similarity for comparison
- k-nearest neighbor lookup
- Threshold-based filtering (e.g., similarity > 0.7)

### Integration Points
- New step `generate_embeddings` in pipeline
- Backend: embeddings stored in Paper model
- Web UI: semantic search widget, similarity sidebar

## Success Criteria

1. ✓ Embeddings generated for 100+ papers without errors
2. ✓ Semantic search returns relevant papers (manual evaluation)
3. ✓ Similar papers identified via cosine similarity (verify clustering)
4. ✓ In-memory lookup < 100ms for 1000 papers
5. ✓ Embeddings can be persisted to SQL and restored
6. ✓ Web UI displays similarity matches and allows semantic search

## References

- Spike 004: `tests/spikes/004_embedding/` (previous embedding work)
- Paper model: `src/paper_scanner/core/models.py` (Embedding class)
- Sentence Transformers: https://www.sbert.net/
- AllenAI SPECTER: https://github.com/allenai/specter
- FAISS: https://github.com/facebookresearch/faiss

## Notes

- Start with all-mpnet-base-v2 (proven, fast, 768-dim)
- Consider compute constraints (GPU optional but helpful)
- Plan for batch embedding (process 100s at a time)
- Embedding model ~400MB, need to handle download/caching
- Test with provided paper collections (papers1.jsonl, papers2.jsonl, etc.)