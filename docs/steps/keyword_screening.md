# Keyword Screening

### Title
**Keyword Screening** - Automated keyword-based screening with implicit study type detection

### Description

The Keyword Screening step performs advanced keyword-based screening with two key features:

1. **Study Type Detection**: Automatically detects research methodology (empirical, literature review, conceptual, editorial, case study, unknown) from paper content using 60+ regex patterns
2. **Keyword Filtering**: Filters papers using inclusion/exclusion keywords with wildcard support and configurable matching modes

Papers are classified by study type, matched against inclusion/exclusion keywords, and marked with screening decisions. The study type classification helps identify the research approach, which is valuable for downstream analysis and manual review prioritization.

### Features

- ✅ **Metadata Completeness Validation**: First-pass validation excludes papers with missing title, abstract, or keywords (EXCLUDED_INCOMPLETE decision)
- ✅ **Implicit Study Type Detection**: Automatically detects empirical (qualitative/quantitative), literature review, case study, conceptual, editorial, and unknown types
- ✅ **Sophisticated Pattern Matching**: Uses 60+ regex patterns across 8 categories (quantitative methods, qualitative methods, case studies, methodology indicators, etc.)
- ✅ **Wildcard Keyword Matching**: Support for exact (`keyword`), prefix (`*keyword`), suffix (`keyword*`), and full (`*keyword*`) wildcards
- ✅ **Flexible Screening Modes**: `inclusion_required`, `exclusion_only`, or `soft` matching modes
- ✅ **Study Type Exclusion**: Can exclude papers by study type (e.g., exclude editorials, exclude conceptual papers)
- ✅ **Missing Abstract Handling**: Automatically flags papers with missing abstracts as UNKNOWN study type
- ✅ **Confidence Scoring**: Provides keyword matching confidence (0-1 scale)
- ✅ **Detailed Results**: Tracks matched keywords, exclusion reasons, and processing metadata

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `complete` | `bool` | No | True | keyword required (default) | 
| `mode` | `string` | No | `inclusion_required` | Screening mode: `inclusion_required`, `exclusion_only`, or `soft` |
| `include.keywords` | `dict` or `list` | No | `{}` | Inclusion keywords (nested dict or flat list) |
| `exclude.keywords` | `dict` or `list` | No | `{}` | Exclusion keywords (nested dict or flat list) |
| `exclude.study_types` | `list[string]` | No | `[]` | Study types to exclude (e.g., `["editorial", "conceptual"]`) |

#### Wildcard Syntax

Keywords support flexible wildcard patterns:

| Pattern | Example | Matches |
|---------|---------|---------|
| Exact | `agile` | "agile", "Agile", "AGILE" |
| Suffix | `agile*` | "agile", "agile-based", "agilely" |
| Prefix | `*agile` | "agile", "be-agile", "more-agile" |
| Both | `*agile*` | "agile" anywhere in text |

### Screening Modes

- **`inclusion_required`** (default): Paper must match inclusion keywords AND not match exclusion keywords AND not be excluded study type
- **`exclusion_only`**: Exclude based on exclusion keywords and study types; no inclusion requirement
- **`soft`**: Permissive mode; performs matching but doesn't enforce exclusion (accept for StudyType)

#### Metadata Completeness Check

Before any keyword matching occurs, the step validates that papers have complete metadata:

- **title**: Must be non-empty string
- **abstract**: Must be non-empty and not "N/A"
- **keywords**: Must be non-empty list with at least one non-empty keyword

Papers failing this validation are marked with **EXCLUDED_INCOMPLETE** decision and reason `"incomplete metadata: missing {title|abstract|keywords}"`. This ensures downstream analysis only processes papers with sufficient information for meaningful screening.

#### YAML Definition

```yaml
- step: Keyword screening with study type detection
  builtin.keyword_screening:
    mode: inclusion_required  # or exclusion_only, soft
    include:
      keywords:
        - "digital transformation"
        - "Industry 4.0"
        - "IoT"
        - "blockchain*"
        - "*agile*"
    exclude:
      keywords:
        - "game"
        - "fiction"
        - "entertainment"
      study_types:
        - "editorial"
        - "conceptual"
```

### Input/Output

#### Input
- **Format**: Papers from database
- **Source**: Results from `bibtex_import`, `deduplication`, or prior screening steps
- **Requirements**: Papers should have title/abstract for accurate study type detection; handles missing abstracts gracefully

#### Output
- **Format**: Papers with keyword screening results and study type classification
- **Screening Decisions**: Papers can receive one of several decision types:
  - **PASSED**: Paper passes keyword screening and study type validation
  - **EXCLUDED**: Paper fails keyword screening (doesn't match inclusion keywords or matches exclusion keywords or fails study type exclusion)
  - **EXCLUDED_INCOMPLETE**: Paper has incomplete metadata (missing title, abstract, or keywords) - first-pass validation
- **Database Updates**:
  - `screening.keyword_screening.study_type`: Detected study type enum
  - `screening.keyword_screening.passed`: Boolean inclusion/exclusion decision
  - `screening.keyword_screening.inclusion_keywords`: Matched inclusion keywords (list)
  - `screening.keyword_screening.exclusion_keywords`: Matched exclusion keywords (list)
  - `screening.keyword_screening.keyword_screening_confidence`: Keyword match confidence (0-1)
  - `screening.keyword_screening.exclusion_reason`: Explanation if excluded (e.g., "incomplete metadata: missing keywords")
  - `screening.keyword_screening.is_empirical`: Whether detected as empirical research
  - `screening.keyword_screening.is_conceptual`: Whether detected as conceptual
  - `screening.keyword_screening.is_literature_review`: Whether detected as literature review
  - `screening.final_decision`: Set to EXCLUDED or EXCLUDED_INCOMPLETE if failed screening
  - `screening.final_decision_by`: Set to "automated:keyword_screening"
- **Metrics**: 
  - `total_papers`: Papers processed
  - `screened`: Papers evaluated
  - `passed`: Papers included
  - `failed`: Papers excluded
  - `study_types`: Distribution across detected study types
  - `exclusion_reasons`: Breakdown of exclusion reasons

### Validation

The step validates:
- `mode`: Must be `inclusion_required`, `exclusion_only`, or `soft`
- `include.keywords`: Must be dict or list of strings
- `exclude.keywords`: Must be dict or list of strings
- `exclude.study_types`: Must be list of valid study type values

### Error Handling

The step handles:
- **Missing abstracts**: Classifies as UNKNOWN study type; useful for exclusion
- **Empty keyword lists**: Acts as pass-through (all papers pass/fail based on study type only)
- **No matches**: Papers with no keyword matches are excluded in `inclusion_required` mode
- **Ambiguous signals**: Papers with 1 empirical pattern (but <2 total) classified as UNKNOWN for manual review

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

- **Metadata completeness is validated first**: Papers missing title, abstract, or keywords are immediately excluded with EXCLUDED_INCOMPLETE decision before any keyword matching
- **Keyword matching is case-insensitive** for flexibility
- **Partial word matching** is supported (e.g., "transform" matches "transformation")
- **Scoring mechanism**: Counts keyword occurrences in title (2x weight) and abstract/keywords (1x weight)
- **Thresholds are independent**: Papers can be manually reviewed even if above either threshold
- **Manual review zone**: Papers with scores between exclusion and inclusion thresholds
- **Empty keyword lists are allowed**: Step acts as no-op if both lists are empty
- **Combine with semantic screening** for more robust decisions on borderline papers
- **Typical values**: inclusion_threshold=60, exclusion_threshold=40 for balanced filtering
