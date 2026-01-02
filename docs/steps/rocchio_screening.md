# Rocchio Semantic Screening

### Title
**Rocchio Semantic Screening** - Adaptive semantic classification using centroid-based Rocchio algorithm with persistent decision boundaries across iterations

### Description

The Rocchio Semantic Screening step performs intelligent relevance filtering using an adaptive Rocchio algorithm. Unlike static embedding-based screening, this step maintains persistent centroid vectors for accepted and rejected papers that evolve across screening iterations, enabling adaptive decision boundaries that strengthen as more papers are labeled.

The step combines the research question embedding with learned centroids of relevant and irrelevant papers. Papers are classified as accepted, rejected, or uncertain based on weighted similarity scores computed via the Rocchio formula. Centroid vectors are stored in the executor state, allowing them to persist between pipeline runs and snowballing iterations without requiring external storage.

### Features

- ✅ **Adaptive decision boundaries**: Centroids evolve as papers are classified, improving decision quality over iterations
- ✅ **Persistent centroids**: State maintained across runs within a session via executor.step_state for continuous learning
- ✅ **Research question driven**: Initializes from research question embedding, refined with labeled papers
- ✅ **Bootstrap from keyword screening**: Optionally initializes centroids from prior keyword_screening results for faster convergence
- ✅ **Multiple embedding models**: Supports domain-specific (SPECTER2) and general-purpose models (all-mpnet-base-v2, all-MiniLM-L6-v2)
- ✅ **Configurable Rocchio weights**: Fine-tune influence of research question (α), accepted papers (β), and rejected papers (γ)
- ✅ **Three-tier classification**: Auto-accept, auto-reject, and uncertain papers with configurable thresholds
- ✅ **Efficient computation**: O(1) centroid updates; pure cosine similarity without LLM calls
- ✅ **Transparent scoring**: Detailed similarity scores and decision reasoning for each paper
- ✅ **No external LLM required**: Pure embedding-based vector operations with well-established IR theory

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | `string` | No | `sentence-transformers/allenai-specter` | Embedding model: `specter2` (academic), `all-mpnet-base-v2` (general), `all-MiniLM-L6-v2` (fast), or HuggingFace identifier |
| `rocchio_weights.alpha` | `number` | No | `1.0` | Weight for research question centroid (0.0-2.0) |
| `rocchio_weights.beta` | `number` | No | `0.75` | Weight for accepted papers centroid (0.0-2.0) |
| `rocchio_weights.gamma` | `number` | No | `0.15` | Weight for rejected papers centroid (0.0-2.0) |
| `thresholds.accept` | `number` | No | `0.7` | Similarity score for automatic acceptance (0-1) |
| `thresholds.reject` | `number` | No | `0.3` | Similarity score for automatic rejection (0-1) |
| `initialize_from_keyword_screening` | `boolean` | No | `true` | Bootstrap centroids from prior keyword_screening results |

#### YAML Definition

```yaml
- step: Rocchio semantic screening
  builtin.rocchio_screening:
    model: "sentence-transformers/allenai-specter"
    rocchio_weights:
      alpha: 1.0
      beta: 0.75
      gamma: 0.15
    thresholds:
      accept: 0.7
      reject: 0.3
    initialize_from_keyword_screening: true
```

### Input/Output

#### Input
- **Format**: Papers with metadata from prior steps
- **Source**: Database with papers (title, abstract, keywords)
- **Requirements**: 
  - Papers must have title or abstract (combines both for richer embedding)
  - Project config must include `research_question` field
  - Prior `keyword_screening` step recommended for bootstrapping (if `initialize_from_keyword_screening: true`)
- **State**: Loads/restores centroid vectors from `executor.step_state`

#### Output
- **Format**: Papers with Rocchio semantic screening classification
- **Database**: Updates `Paper` model with:
  - `screening.semantic_screening.passed` - boolean (True if INCLUDED or UNCERTAIN)
  - `screening.semantic_screening.decision` - INCLUDED/EXCLUDED/UNCERTAIN
  - `screening.semantic_screening.similarity_score` - float (0-1, Rocchio score)
  - `screening.semantic_screening.confidence` - float (0-1, decision confidence)
  - `screening.semantic_screening.reason` - text explanation with thresholds and scores
  - `screening.semantic_screening.metadata.timestamp` - ISO8601 timestamp
  - `screening.current_stage` - set to "rocchio_screening_complete"
  - `screening.final_decision` - updated if pending (INCLUDED/EXCLUDED)
- **State**: Saves updated centroid state to `executor.step_state[semantic_classification_rocchio_state]`
- **Metrics**: Papers classified (total, accepted, rejected, uncertain), centroid initialization status

### Validation

The step validates:
- `model`: Must be valid HuggingFace model identifier or known alias (specter2, all-mpnet-base-v2, all-MiniLM-L6-v2)
- `rocchio_weights`: If provided, must be dict with numeric non-negative values for alpha, beta, gamma
- `thresholds`: If provided, must be dict with numeric values between 0-1 for accept and reject
- `initialize_from_keyword_screening`: Must be boolean if provided
- Project configuration must include `research_question` field
- At least some papers must exist in database

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "research_question must be set" | Missing research_question in project config | Add research_question to project configuration |
| "Model download failed" | Cannot fetch embedding model from HuggingFace | Check internet, try alternative model like all-mpnet-base-v2 |
| "Invalid threshold values" | Thresholds outside 0-1 range | Use values between 0 (completely dissimilar) and 1 (perfect match) |
| "No papers to screen" | All papers already classified or excluded | Verify prior steps completed successfully |
| "Model name not found" | Invalid HuggingFace model identifier | Use valid identifier or known alias (specter2, all-mpnet-base-v2) |
| "Memory error" | Model too large for system | Try lightweight model like all-MiniLM-L6-v2 (384-dim) |

### Embedding Models

The model selection significantly impacts centroid quality and decision boundaries:

| Model | Type | Dimensions | Best For | Speed |
|-------|------|-----------|----------|-------|
| `allenai-specter` (default) | Domain-specialized | 768 | Academic papers, systematic reviews | Medium |
| `all-mpnet-base-v2` | General-purpose | 768 | Broad content, fast baseline | Medium |
| `all-MiniLM-L6-v2` | Lightweight | 384 | Resource-constrained, fast inference | Fast |
| `sentence-transformers/sciBERT` | Domain-aware | 768 | Scientific text, alternative to SPECTER | Medium |

**Recommendation for academic papers**: Use `allenai-specter` (domain-trained on citation graphs). Papers close in citation space are semantically similar, aligning perfectly with systematic review logic.

**Recommendation for speed**: Use `all-mpnet-base-v2` as balanced general-purpose model or `all-MiniLM-L6-v2` for fast inference with acceptable quality.

### Algorithm Details

The Rocchio algorithm computes a weighted similarity score combining three signals:

$$Q_{new} = \alpha \cdot Q_{original} + \beta \cdot \frac{1}{|D_r|}\sum_{d \in D_r} d - \gamma \cdot \frac{1}{|D_{nr}|}\sum_{d \in D_{nr}} d$$

Where:
- $Q_{original}$ = research question embedding (constant across runs)
- $D_r$ = set of accepted papers (centroid evolves)
- $D_{nr}$ = set of rejected papers (centroid evolves)
- $\alpha, \beta, \gamma$ = weights controlling influence of each signal

Papers with scores ≥ `thresholds.accept` are automatically included. Papers with scores ≤ `thresholds.reject` are automatically excluded. Papers between the thresholds are marked as UNCERTAIN for manual review.

### Examples

#### Basic Example - Standard Configuration
```yaml
project:
  research_question: "How do incumbent firms involve suppliers in digital innovation?"

pipeline:
  - step: Rocchio semantic screening
    builtin.rocchio_screening:
      model: "sentence-transformers/allenai-specter"
      thresholds:
        accept: 0.7
        reject: 0.3
```

#### Advanced Example - Fine-tuned Weights
```yaml
project:
  research_question: "What barriers exist to Industry 4.0 adoption in SMEs?"

pipeline:
  - step: Rocchio semantic screening with custom weights
    builtin.rocchio_screening:
      model: "sentence-transformers/allenai-specter"
      rocchio_weights:
        alpha: 1.0    # Research question influence
        beta: 0.8     # Higher weight for accepted papers
        gamma: 0.2    # Higher weight against rejected papers
      thresholds:
        accept: 0.72
        reject: 0.28
      initialize_from_keyword_screening: true
```

#### Fast Processing - Lightweight Model
```yaml
project:
  research_question: "What innovations in technology exist?"

pipeline:
  - step: Fast Rocchio screening
    builtin.rocchio_screening:
      model: "all-MiniLM-L6-v2"  # Lightweight 384-dim model
      thresholds:
        accept: 0.68
        reject: 0.32
```

#### Strict Screening - High Thresholds
```yaml
pipeline:
  - step: Strict Rocchio screening for small review
    builtin.rocchio_screening:
      model: "sentence-transformers/allenai-specter"
      thresholds:
        accept: 0.8   # Very high - only obvious matches
        reject: 0.2   # Very low - only obvious non-matches
```

### Workflow Across Snowballing Iterations

**Iteration 0 (Initial Screening):**
1. Embed research question to initialize query centroid
2. Optional: Bootstrap from `keyword_screening` results (accepted/rejected papers)
3. Classify remaining papers; route uncertain to manual review
4. Save centroids to executor state

**Iteration 1+ (Snowballing):**
1. Load persisted centroids from executor state
2. Process new papers from forward/backward citations
3. Same classification logic applies to new papers
4. Update centroids with manually labeled results
5. State persists automatically to executor.step_state

### Related Steps

- **Upstream**: `keyword_screening` (recommended for bootstrapping), `load_files`, `deduplication`, `categorization`
- **Downstream**: `checkpoint`, `summarize`, `export`
- **Alternative**: `semantic_screening` (static thresholds, no adaptive learning)
- **Complementary**: `keyword_screening` (keyword-based) + `rocchio_screening` (semantic adaptive)

### Notes

- **Centroid persistence**: Centroids persist in `executor.step_state` within a session. To reset state between runs, call `executor.step_state.clear()` or restart the pipeline
- **Bootstrapping improves convergence**: Running with `initialize_from_keyword_screening: true` typically converges faster; provide 20+ labeled papers for good initial centroids
- **Threshold tuning**: Inspect papers near threshold boundaries (0.65-0.75) to refine accept/reject thresholds
- **First model download**: Initial run may take 1-5 minutes downloading embedding model; subsequent runs use cached model
- **Research question quality**: Specific, well-written research questions produce better decision boundaries than generic questions
- **Rocchio weights interpretation**:
  - **α (alpha)**: Importance of research question. Higher = respect original query more
  - **β (beta)**: Importance of accepted papers. Higher = move boundary toward included papers
  - **γ (gamma)**: Importance of rejected papers. Higher = move boundary away from excluded papers
- **Typical starting weights**: α=1.0 (query), β=0.75 (learn from positives), γ=0.15 (learn less from negatives)
- **Processing speed**: ~200-500 papers/minute depending on model and system (SPECTER slower than MiniLM)
- **Memory usage**: ~2-4GB for SPECTER, ~1-2GB for MiniLM during batch processing
- **Recommended workflow**: Combine `keyword_screening` (fast, broad) followed by `rocchio_screening` (adaptive, semantic) for optimal coverage
- **Transparent decisions**: All paper decisions include similarity score and threshold comparison for auditability

### References

**Foundational - Rocchio Algorithm:**
- Rocchio, J. J. (1971). Relevance feedback in information retrieval. In *The SMART retrieval system: Experiments in automatic document processing* (pp. 313–323). Prentice-Hall.

**Classic IR Textbook:**
- Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to information retrieval*. Cambridge University Press. https://nlp.stanford.edu/IR-book/ (Chapters 9 & 14)

**SPECTER - Academic Document Embeddings:**
- Cohan, A., Feldman, S., Beltagy, I., Downey, D., & Weld, D. S. (2020). SPECTER: Document-level representation learning using citation-informed transformers. *Proceedings of ACL 2020*, 2270–2282. https://aclanthology.org/2020.acl-main.207/

**SPECTER2 - Improved Version:**
- Singh, A., D'Arcy, M., Cohan, A., Downey, D., & Feldman, S. (2023). SciRepEval: A multi-format benchmark for scientific document representations. *Proceedings of EMNLP 2023*.
