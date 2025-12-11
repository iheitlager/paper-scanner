# Keyword Screening

### Title
**Keyword Screening** - Filters papers using inclusion and exclusion keyword lists

### Description

The Keyword Screening step performs automated keyword-based filtering using user-defined inclusion and exclusion keywords. Papers are scored based on keyword presence in their title, abstract, and keywords field. Papers scoring above the inclusion threshold are marked INCLUDED, those below the exclusion threshold are marked EXCLUDED, and borderline papers are marked MANUAL_REVIEW for human assessment.

This step provides a fast, configurable first-pass filter that can significantly reduce the screening workload before semantic and manual screening stages.

### Features

- ✅ **Inclusion keywords**: Define keywords that papers must contain for automatic inclusion
- ✅ **Exclusion keywords**: Define keywords that automatically exclude papers
- ✅ **Scoring mechanism**: Keyword frequency-based scoring (0-100 scale)
- ✅ **Configurable thresholds**: Set inclusion and exclusion thresholds for decision points
- ✅ **Progress reporting**: Inline updates every 100 papers showing screening progress
- ✅ **Decision tracking**: Automatically sets final_decision based on keyword scores
- ✅ **Scoring details**: Logs keyword scores and matching keywords in screening notes

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `inclusion_keywords` | `list[string]` | No | `[]` | Keywords that support paper inclusion |
| `exclusion_keywords` | `list[string]` | No | `[]` | Keywords that support paper exclusion |
| `inclusion_threshold` | `number` | No | `60` | Inclusion score threshold (0-100) |
| `exclusion_threshold` | `number` | No | `40` | Exclusion score threshold (0-100) |

#### YAML Definition

```yaml
- step: Screen by keywords
  builtin.keyword_screening:
    inclusion_keywords:
      - "digital transformation"
      - "Industry 4.0"
      - "IoT"
    exclusion_keywords:
      - "fiction"
      - "game"
    inclusion_threshold: 60
    exclusion_threshold: 40
```

### Input/Output

#### Input
- **Format**: Papers from prior screening stages
- **Source**: Database with papers, titles, abstracts
- **Requirements**: Papers must have title/abstract content for matching

#### Output
- **Format**: Papers with keyword screening status
- **Database**: Updates `Paper` model with:
  - `screening.keyword_screening.status` set to INCLUDED/EXCLUDED/MANUAL_REVIEW
  - `screening.keyword_screening.final_decision` with decision
  - `screening.keyword_screening.score` with calculated score
  - `screening.keyword_screening.notes` with matching keywords
- **Metrics**: Papers by decision (included, excluded, manual review)

### Validation

The step validates:
- `inclusion_keywords`: Must be list of strings
- `exclusion_keywords`: Must be list of strings
- `inclusion_threshold`: Must be number between 0 and 100
- `exclusion_threshold`: Must be number between 0 and 100
- `inclusion_threshold` should be ≥ `exclusion_threshold`

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Empty keyword list" | Both inclusion and exclusion keywords are empty | Add at least some keywords |
| "Invalid threshold" | Threshold outside 0-100 range | Use values between 0 and 100 |
| "Malformed keywords" | Keywords contain invalid characters | Use plain text without special regex chars |
| "Missing content" | Papers lack title/abstract | Check bibtex_import included these fields |

### Examples

#### Basic Example - Simple Keywords
```yaml
- step: Screen by technology keywords
  builtin.keyword_screening:
    inclusion_keywords:
      - "artificial intelligence"
      - "machine learning"
      - "deep learning"
    exclusion_keywords:
      - "game"
      - "fiction"
    inclusion_threshold: 50
    exclusion_threshold: 30
```

#### Advanced Example - Topic-Specific Screening
```yaml
- step: Screen digital transformation papers
  builtin.keyword_screening:
    inclusion_keywords:
      - "digital transformation"
      - "digital disruption"
      - "Industry 4.0"
      - "IoT"
      - "blockchain"
      - "cloud computing"
      - "big data"
    exclusion_keywords:
      - "game"
      - "fiction"
      - "entertainment"
      - "social media"
      - "consumer"
    inclusion_threshold: 70
    exclusion_threshold: 35
```

#### Permissive Example - Broad Inclusion
```yaml
- step: Light keyword filtering
  builtin.keyword_screening:
    inclusion_keywords:
      - "innovation"
    exclusion_keywords:
      - "game"
    inclusion_threshold: 40
    exclusion_threshold: 20
```

### Related Steps

- **Upstream**: `categorization`, `checkpoint`
- **Downstream**: `semantic_screening`, `checkpoint`, `summarize`
- **Alternative**: `semantic_screening` for more sophisticated matching

### Notes

- **Keyword matching is case-insensitive** for flexibility
- **Partial word matching** is supported (e.g., "transform" matches "transformation")
- **Scoring mechanism**: Counts keyword occurrences in title (2x weight) and abstract/keywords (1x weight)
- **Thresholds are independent**: Papers can be manually reviewed even if above either threshold
- **Manual review zone**: Papers with scores between exclusion and inclusion thresholds
- **Empty keyword lists are allowed**: Step acts as no-op if both lists are empty
- **Combine with semantic screening** for more robust decisions on borderline papers
- **Typical values**: inclusion_threshold=60, exclusion_threshold=40 for balanced filtering
