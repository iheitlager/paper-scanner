# GenerateEmbeddingsStep

Generate semantic embeddings for paper text fields using transformer models.

## Overview

The `GenerateEmbeddingsStep` creates vector embeddings for papers' titles, abstracts, and keywords using the Sentence Transformers library. These embeddings enable:

- **Semantic search**: Find papers based on meaning rather than keywords
- **Similarity matching**: Identify related papers using vector similarity
- **Clustering**: Group papers by semantic similarity
- **SQL persistence**: Store embeddings in PostgreSQL with pgvector extension (future)

## Configuration

### Basic Configuration

```yaml
- step: generate_embeddings
  config:
    model: "all-mpnet-base-v2"    # Default: proven, fast, 768-dimensional
    device: "cpu"                  # Device: "cpu" or "cuda"
    batch_size: 32                 # Processing batch size
```

### Full Configuration

```yaml
- step: generate_embeddings
  config:
    # Model selection
    model: "all-mpnet-base-v2"                    # Embedding model name
    device: "cpu"                                  # "cpu" or "cuda"
    batch_size: 32                                 # Batch size for encoding
    
    # Fields to embed
    fields:                                        # Which fields to embed
      - title
      - abstract
      - keywords
    
    # Processing options
    skip_existing: true                           # Skip if already embedded
    
    # Filtering
    filter:
      included_only: true                         # Only embed included papers
      min_year: 2020                              # Optional year threshold
```

## Configuration Options

### `model`
- **Type**: string
- **Default**: `"all-mpnet-base-v2"`
- **Description**: Hugging Face model identifier for embeddings
- **Examples**:
  - `"all-mpnet-base-v2"` - General purpose (768 dims, ~430MB)
  - `"allenai/specter"` - Citation-based scientific papers (768 dims)
  - `"sentence-transformers/all-minilm-l6-v2"` - Lightweight (384 dims)

### `device`
- **Type**: string (`"cpu"` or `"cuda"`)
- **Default**: `"cpu"`
- **Description**: Device for model inference
- **Note**: `"cuda"` requires NVIDIA GPU and PyTorch CUDA support

### `batch_size`
- **Type**: integer
- **Default**: `32`
- **Description**: Number of texts to encode simultaneously
- **Note**: Larger batches are faster but use more memory

### `fields`
- **Type**: list of strings
- **Default**: `["title", "abstract", "keywords"]`
- **Valid values**: `"title"`, `"abstract"`, `"keywords"`, `"combined"`
- **Description**: Which paper fields to embed

### `skip_existing`
- **Type**: boolean
- **Default**: `true`
- **Description**: Skip papers that already have embeddings

### `filter`
- **Type**: dictionary
- **Nested options**:
  - `included_only` (bool): Only process papers with final_decision = INCLUDED
  - `min_year` (int): Only process papers from year onwards

## Output

The step returns a `StepResult` with:

- **status**: `SUCCESS`, `WARNING`, or `ERROR`
- **message**: Summary of embedding generation
- **stats**: Dictionary with:
  - `papers_count`: Total papers in database
  - `papers_processed`: Papers matching filters
  - `embeddings_generated`: Total embeddings created
  - `embeddings_skipped`: Papers already embedded
  - `errors`: Processing errors
- **details**: Formatted summary for reporting

## Example Output

```
Generated 125 embeddings for 125 papers (skipped 8), 1 errors

## Embedding Generation Summary

- **Model**: all-mpnet-base-v2
- **Device**: cpu
- **Fields embedded**: title, abstract, keywords
- **Papers processed**: 125
- **Embeddings generated**: 375 (title, abstract, keywords × 125 papers)
- **Embeddings skipped**: 8
- **Errors**: 1
- **Vector dimension**: 768
```

## Embedding Storage

Embeddings are stored in the `Paper` model:

- **title_abstract_embedding**: Main embedding (title or combined text)
- Custom properties (for future enhancement):
  - `_abstract_embedding`: Abstract-specific embedding
  - `_keywords_embedding`: Keywords-specific embedding

Each `Embedding` object contains:
- `vector`: List of 768 floats
- `model`: Model name used
- `text_source`: What was embedded ("title", "abstract", "keywords")
- `created_at`: Generation timestamp

## Integration with Pipeline

### Typical workflow:

```yaml
workflow:
  steps:
    - step: bibtex_import
      config:
        source: "papers.bib"
    
    - step: deduplication
    
    - step: metadata_screening
    
    - step: keyword_screening
    
    - step: semantic_screening
    
    - step: generate_embeddings          # After screening complete
      config:
        model: "all-mpnet-base-v2"
        fields: [title, abstract]
        filter:
          included_only: true            # Only included papers
    
    - step: export
      config:
        format: "jsonl"
        output: "results.jsonl"
```

## Performance

Typical performance metrics (on CPU, all-mpnet-base-v2):

- **Model loading**: ~2-3 seconds
- **Per-paper embedding**: ~0.1-0.2 seconds
- **100 papers**: ~10-20 seconds
- **1000 papers**: ~100-200 seconds

GPU acceleration (CUDA):
- **Model loading**: ~2-3 seconds
- **Per-paper embedding**: ~0.01-0.02 seconds
- **100 papers**: ~1-2 seconds
- **1000 papers**: ~10-20 seconds

### Optimization Tips

1. **Use GPU for large datasets** (`device: "cuda"`)
2. **Increase batch_size** with GPU (default 32, can go up to 128+)
3. **Embed only included papers** (`filter: {included_only: true}`)
4. **Skip existing embeddings** (`skip_existing: true`) for incremental runs

## Model Comparison

| Model | Dims | Size | Speed | Domain | Notes |
|-------|------|------|-------|--------|-------|
| all-mpnet-base-v2 | 768 | ~430MB | Fast | General | Best for speed/quality tradeoff |
| allenai/specter | 768 | ~400MB | Fast | Scientific | Trained on citations, better for papers |
| all-minilm-l6-v2 | 384 | ~80MB | Very Fast | General | Lightweight alternative |
| all-roberta-large-v1 | 1024 | ~740MB | Medium | General | Larger vectors, higher quality |

## Error Handling

The step handles common errors gracefully:

- **Model not found**: Returns ERROR status with message
- **Out of memory**: Reduce batch_size or use device="cpu"
- **Invalid text**: Skips that field, continues processing
- **Database connection**: Returns ERROR with descriptive message

## Future Enhancements

- [x] **Phase 1**: Basic title/abstract/keywords embedding
- [ ] **Phase 2**: Section-level embeddings for full-text papers
- [ ] **Phase 3**: SQL persistence with pgvector
- [ ] **Phase 4**: Web UI integration for semantic search
- [ ] **Phase 5**: Hybrid embeddings (multiple models combined)

## Related Steps

- [BibtexImportStep](./bibtex_import.md) - Load papers from BibTeX
- [ExportStep](./export.md) - Export papers with embeddings
- Future: SemanticSearchStep, PaperSimilarityStep

## References

- [Sentence Transformers](https://www.sbert.net/)
- [All-MiniLM-L6-v2 Model](https://huggingface.co/sentence-transformers/all-mpnet-base-v2)
- [AllenAI SPECTER](https://github.com/allenai/specter)
- [Spike 018: Structured Paper Embeddings](../../tests/spikes/018_embedding/README.md)
