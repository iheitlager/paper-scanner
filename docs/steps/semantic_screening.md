# Semantic Screening

### Title
**Semantic Screening** - Filters papers using embedding-based semantic relevance to a research question

### Description

The Semantic Screening step performs sophisticated relevance filtering using semantic embeddings. It embeds the research question and each paper (using title and abstract) into a high-dimensional vector space, then computes cosine similarity between them. Papers are automatically included, excluded, or flagged for manual review based on configurable similarity thresholds.

This approach captures semantic meaning beyond keyword matching, enabling more nuanced relevance decisions and reducing manual review burden for relevance judgments.

### Features

- ✅ **Embedding-based relevance**: Uses sentence-transformers to compute semantic similarity
- ✅ **Research question driven**: Measures relevance to your specific research question
- ✅ **Configurable thresholds**: Set thresholds for auto-include, manual-review, and auto-exclude
- ✅ **Efficient processing**: Batches papers for optimal embedding performance
- ✅ **Progress reporting**: Inline updates every 100 papers showing screening progress
- ✅ **Detailed scoring**: Logs similarity scores for transparency and review
- ✅ **Suppressed verbosity**: Quiet model downloading and loading without terminal noise

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | `string` | No | `all-mpnet-base-v2` | Embedding model (HuggingFace identifier) |
| `thresholds.auto_include` | `number` | No | `0.65` | Similarity score for automatic inclusion (0-1 scale) |
| `thresholds.manual_review` | `number` | No | `0.55` | Similarity score for manual review threshold (0-1 scale) |
| `thresholds.auto_exclude` | `number` | No | `0.55` | Similarity score for automatic exclusion (0-1 scale) |

#### YAML Definition

```yaml
- step: Semantic relevance screening
  builtin.semantic_screening:
    model: "all-mpnet-base-v2"
    thresholds:
      auto_include: 0.65
      manual_review: 0.55
      auto_exclude: 0.55
```

### Input/Output

#### Input
- **Format**: Papers from prior screening stages
- **Source**: Database with papers, titles, abstracts
- **Requirements**: Papers must have title and abstract content
- **Project Config**: Requires `research_question` field from project configuration

#### Output
- **Format**: Papers with semantic screening status
- **Database**: Updates `Paper` model with:
  - `screening.semantic_screening.status` set to INCLUDED/EXCLUDED/MANUAL_REVIEW
  - `screening.semantic_screening.final_decision` with decision
  - `screening.semantic_screening.score` with similarity score (0-1)
  - `screening.semantic_screening.notes` with detailed reasoning
- **Metrics**: Papers by decision (included, excluded, manual review), score distribution

### Validation

The step validates:
- `model`: Must be valid HuggingFace model identifier
- `thresholds.auto_include`: Must be number between 0 and 1, should be ≥ manual_review
- `thresholds.manual_review`: Must be number between 0 and 1
- `thresholds.auto_exclude`: Must be number between 0 and 1, should be ≤ manual_review
- Project configuration must include `research_question` field

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Model download failed" | Cannot fetch embedding model from HuggingFace | Check internet connection, try alternative model |
| "Missing research_question" | Project config lacks research_question field | Add research_question to project config |
| "Invalid threshold" | Threshold outside 0-1 range | Use values between 0 and 1 |
| "Empty papers" | No papers to process | Ensure prior steps ran successfully |

### Examples

#### Basic Example - Standard Research Question
```yaml
project:
  research_question: "How is digital transformation impacting supply chains?"

pipeline:
  - step: Screen by semantic relevance
    builtin.semantic_screening:
      model: "all-mpnet-base-v2"
      thresholds:
        auto_include: 0.65
        manual_review: 0.55
        auto_exclude: 0.55
```

#### Advanced Example - Strict Screening
```yaml
project:
  research_question: "What are the barriers to Industry 4.0 adoption in manufacturing?"

pipeline:
  - step: Strict semantic screening
    builtin.semantic_screening:
      model: "all-mpnet-base-v2"
      thresholds:
        auto_include: 0.75
        manual_review: 0.60
        auto_exclude: 0.50
```

#### Permissive Example - Broad Relevance
```yaml
project:
  research_question: "What innovations in technology exist?"

pipeline:
  - step: Broad semantic screening
    builtin.semantic_screening:
      model: "all-mpnet-base-v2"
      thresholds:
        auto_include: 0.55
        manual_review: 0.45
        auto_exclude: 0.35
```

### Related Steps

- **Upstream**: `keyword_screening`, `categorization`, `checkpoint`
- **Downstream**: `checkpoint`, `summarize`, `export`
- **Alternative**: `keyword_screening` for simpler keyword-based matching

### Notes

- **Embedding model choice**: `all-mpnet-base-v2` is a good general-purpose model; alternatives include `all-MiniLM-L6-v2` (faster, slightly lower quality) or domain-specific models
- **Similarity scale is 0-1**: Where 1.0 is perfect semantic match and 0.0 is completely dissimilar
- **First model download** may take 1-5 minutes depending on internet speed; subsequent runs use cached model
- **Threshold tuning** should be based on inspection of borderline cases (score 0.50-0.70)
- **Research question quality** significantly impacts results; more specific questions give better decisions
- **Manual review papers** (between thresholds) should be reviewed by domain experts
- **Processing speed**: ~200-500 papers per minute depending on system and model choice
- **Memory usage**: ~2-4GB for typical models processing large batches
- **Recommended defaults**: auto_include=0.65, manual_review=0.55 for most use cases
