# Rocchio Classifier Step

## Overview

The Rocchio Classifier uses **research dimensions as separate centroids** in embedding space to classify papers. Each dimension becomes its own semantic reference point, enabling multi-dimensional classification with explicit dominant dimension identification.

Unlike simpler binary classifiers, this approach:
- Treats each research dimension as a semantic centroid
- Computes paper similarity to **each dimension independently**
- Identifies which dimensions are relevant to a paper
- Determines if one dimension dominates clearly
- Classifies as: **EXCLUDED** (no dimensions), **INCLUDED** (one clear dimension), or **UNCERTAIN** (multiple dimensions)

## Classification Logic

```
Paper Embedding → Similarity to Each Dimension Centroid
     ↓
    [similarity_to_dim1, similarity_to_dim2, similarity_to_dim3, ...]
     ↓
  Compare to threshold → Identify applicable dimensions
     ↓
  Count applicable dimensions:
    0 dims  → EXCLUDED
    1 dim   → INCLUDED (clear dominant)
    2+ dims → MANUAL_REVIEW (uncertain which dominates)
```

## Use Cases

- **Multi-dimensional screening**: Papers may be relevant to one or multiple research dimensions
- **Uncertainty handling**: Explicitly surfaces papers relevant to multiple dimensions
- **Semantic classification**: Uses learned embeddings for nuanced similarity matching
- **Dimension importance**: Tracks which dimensions apply to each paper

## Configuration

```yaml
- step: "Rocchio Classification"
  builtin.rocchio_classifier:
    model: "all-mpnet-base-v2"           # Embedding model (optional, default shown)
    dimension_threshold: 0.5              # Similarity threshold (optional, default shown)
    initialize_from_research_question: true  # Use RQ for init (optional, default shown)
```

### Configuration Options

#### `model` (string, optional, default: `"all-mpnet-base-v2"`)

Sentence transformer model for embedding papers and dimensions.

**Recommended models:**

| Model | Dimension | Best For | Speed |
|-------|-----------|----------|-------|
| `all-mpnet-base-v2` | 768 | General academic papers, multilingual | Medium |
| `specter2` | 768 | Academic papers (domain-specialized) | Slow |
| `all-MiniLM-L6-v2` | 384 | Large datasets, resource-constrained | Fast |
| `sciBERT` | 768 | Scientific domain knowledge | Medium |

**Recommendation**: Use `all-mpnet-base-v2` for most cases (good balance of quality and speed). Use `specter2` for domain-specific academic papers if processing time permits.

#### `dimension_threshold` (float, optional, default: `0.5`)

Cosine similarity threshold for considering a dimension applicable to a paper.

- Range: `[0.0, 1.0]`
- Higher values (0.7+): More restrictive, only highly relevant dimensions apply
- Lower values (0.3-0.4): More inclusive, papers match multiple dimensions more often
- Recommended: `0.5` for balanced classification

#### `initialize_from_research_question` (boolean, optional, default: `true`)

If `true`, initialize dimension centroids from the research question combined with each dimension name. This provides initial semantic context when no training data is available.

If `false`, centroids start uninitialized (zero vectors) and must be trained separately.

## Output Fields

The classifier updates `paper.screening.semantic_screening` with:

### SemanticScreening Fields

| Field | Type | Meaning |
|-------|------|---------|
| `passed` | bool | `true` if INCLUDED, `false` if EXCLUDED or MANUAL_REVIEW |
| `decision` | ScreeningDecision | INCLUDED, EXCLUDED, or MANUAL_REVIEW |
| `classification` | string | "included", "excluded", or "uncertain" |
| `classification_vector` | List[float] | Similarity scores for each dimension (order matches `research_dimensions`) |
| `classification_labels` | List[str] | Names of applicable dimensions |
| `confidence` | float | Normalized confidence [0-1], higher = more confident |
| `similarity_score` | float | Highest dimension similarity |
| `reason` | string | Human-readable explanation (e.g., "Rocchio: innovation_process (sim=0.742)") |
| `metadata` | ProcessingMetadata | Model name, duration, success status |

### Example Output

```python
paper.screening.semantic_screening = SemanticScreening(
    passed=True,
    decision=ScreeningDecision.INCLUDED,
    classification="included",
    classification_vector=[0.74, 0.32, 0.19],  # Similarity to [dim1, dim2, dim3]
    classification_labels=["supplier_involvement"],  # Only one applies
    confidence=0.74,
    similarity_score=0.74,
    reason="Rocchio: supplier_involvement (sim=0.740)",
)
```

## Classification Decisions

### EXCLUDED
- **Condition**: All dimensions below `dimension_threshold`
- **Meaning**: Paper not relevant to any dimension
- **Action**: `final_decision` set to EXCLUDED (if not already decided)

### INCLUDED
- **Condition**: Exactly one dimension above `dimension_threshold`
- **Meaning**: Paper clearly maps to a single dimension
- **Action**: `final_decision` set to INCLUDED with dominant dimension identified

### MANUAL_REVIEW (Uncertain)
- **Condition**: 2+ dimensions above `dimension_threshold`
- **Meaning**: Paper relevant to multiple dimensions; humans must decide dominance
- **Action**: `final_decision` remains UNCERTAIN for human review

## Step Result Stats

```python
{
    "step": "rocchio_classifier",
    "total_papers": 150,           # Total papers in database
    "classified": 145,              # Papers actually classified
    "included": 85,                 # Papers with clear dimension
    "excluded": 35,                 # Papers with no dimension
    "manual_review": 25,            # Papers with multiple dimensions
    "model": "all-mpnet-base-v2",
    "dimension_threshold": 0.5,
    "dimensions": 4,                # Number of research dimensions
}
```

## Examples

### Example 1: Simple Configuration

```yaml
steps:
  - step: "Import"
    builtin.bibtex_import:
      file_path: "papers.bib"
      source_type: "scopus"
  
  - step: "Rocchio Classification"
    builtin.rocchio_classifier:
      # Uses defaults: all-mpnet-base-v2, threshold=0.5, init from RQ
```

### Example 2: Strict Classification

```yaml
steps:
  - step: "Rocchio Classification"
    builtin.rocchio_classifier:
      model: "specter2"
      dimension_threshold: 0.7        # Only very relevant papers included
      initialize_from_research_question: true
```

### Example 3: Inclusive Classification

```yaml
steps:
  - step: "Rocchio Classification"
    builtin.rocchio_classifier:
      model: "all-mpnet-base-v2"
      dimension_threshold: 0.3        # More papers match multiple dimensions
      initialize_from_research_question: true
```

## Requirements

- `research_question`: Must be set in project configuration (used for context)
- `research_dimensions`: Must be a non-empty list in project configuration
  - Example: `["supplier_involvement", "digital_innovation", "incumbent_firms"]`

## Performance Considerations

### Speed

| Model | Typical Paper | Batch Speed |
|-------|---------------|-------------|
| `all-MiniLM-L6-v2` | ~5ms | ~200 papers/sec |
| `all-mpnet-base-v2` | ~10ms | ~100 papers/sec |
| `specter2` | ~50ms | ~20 papers/sec |

### Memory

- Single model instance shared across all papers
- ~500MB RAM for `all-mpnet-base-v2`
- ~1.5GB RAM for `specter2`

### Optimization Tips

- Use `all-MiniLM-L6-v2` for large datasets (1000+ papers)
- Use `all-mpnet-base-v2` for balanced quality/speed (default)
- Use `specter2` only if you need domain-specific academic understanding
- Adjust `dimension_threshold` to control classification strictness

## Implementation Notes

### Centroid Initialization

When `initialize_from_research_question=true`:

```
For each dimension:
    text = research_question + ". " + dimension + "."
    centroid = encode(text)
```

This provides semantic context without external training data.

### Similarity Computation

Uses **cosine similarity** on normalized embedding vectors:

```
similarity(paper, dimension) = (paper_embedding · dimension_embedding) / 
                               (||paper_embedding|| × ||dimension_embedding||)
```

### Decision Boundary Logic

```python
applicable_dimensions = [
    dim for dim, sim in similarities.items()
    if sim >= dimension_threshold
]

if len(applicable_dimensions) == 0:
    decision = EXCLUDED
elif len(applicable_dimensions) == 1:
    decision = INCLUDED
else:
    decision = MANUAL_REVIEW
```

## Debugging

### Check Classification Vector

The `classification_vector` shows similarity to each dimension:

```python
paper.screening.semantic_screening.classification_vector
# [0.74, 0.32, 0.19] for dimensions [dim1, dim2, dim3]
```

### Check Applicable Dimensions

```python
paper.screening.semantic_screening.classification_labels
# ["dim1"] if only one applies
# ["dim1", "dim2"] if multiple apply
```

### Check Reasoning

```python
paper.screening.semantic_screening.reason
# "Rocchio: dim1 (sim=0.740)"
```

### Examine Raw Similarities

Access step callbacks or logs to see detailed similarity scores for all dimensions.

## Related Steps

- **keyword_screening**: Rule-based screening on keywords
- **semantic_screening**: Rocchio-based screening on accept/reject centroids
- **llm_classification**: LLM-based multi-dimensional classification
- **metadata_screening**: Screening on publication metadata

## See Also

- [BaseStep Documentation](base_step.md)
- [SemanticScreening Model](../architecture/models.md#semanticscreening)
- [Rocchio Algorithm](https://nlp.stanford.edu/IR-book/html/htmledition/rocchio-classification-1.html)
