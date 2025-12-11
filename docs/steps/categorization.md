# Categorization

### Title
**Categorization** - Validates paper types, filters by quality tiers, and excludes reviews/non-peer-reviewed papers

### Description

The Categorization step filters papers based on their publication type and quality characteristics. It validates that papers are peer-reviewed research articles (or conference papers if included in scope), excludes literature reviews and survey papers, and optionally excludes non-peer-reviewed content. This step ensures the paper collection contains only appropriate research for synthesis and analysis.

Papers that fail categorization are marked with EXCLUDED status and are hidden from downstream screening steps. The step provides detailed logging of exclusion reasons to support manual review if needed.

### Features

- ✅ **Publication type filtering**: Identifies and handles different paper types (journal articles, conference papers, books, etc.)
- ✅ **Review exclusion**: Automatically excludes literature reviews and survey papers
- ✅ **Peer-review validation**: Marks papers with missing peer-review information as needing manual review
- ✅ **Type-based exclusion**: Optional exclusion of conferences, books, and other non-journal types
- ✅ **Quality tier tracking**: Tracks papers across quality tiers (peer-reviewed, accepted, published)
- ✅ **Progress reporting**: Inline updates every 100 papers showing categorization progress
- ✅ **Traceability**: Logs exclusion reason in screening notes for transparency

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `exclude_types` | `boolean` | No | `true` | Exclude non-peer-reviewed conferences and books |
| `exclude_reviews` | `boolean` | No | `true` | Exclude literature reviews and survey papers |

#### YAML Definition

```yaml
- step: Categorize and validate papers
  builtin.categorization:
    exclude_types: true
    exclude_reviews: true
```

### Input/Output

#### Input
- **Format**: Papers from deduplication or bibtex_import
- **Source**: Database with papers and their metadata
- **Requirements**: Papers must have publication type information

#### Output
- **Format**: Papers with categorization status set
- **Database**: Updates `Paper` model with:
  - `screening.status` set to EXCLUDED for filtered papers
  - `screening.final_decision` set to EXCLUDED
  - `screening.notes` with exclusion reason
- **Metrics**: Papers categorized, excluded counts by reason, inclusion rate

### Validation

The step validates:
- `exclude_types`: Must be boolean
- `exclude_reviews`: Must be boolean
- All required paper metadata fields are present

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Empty database" | No papers to categorize | Run bibtex_import or deduplication first |
| "Missing metadata" | Papers lack publication type info | Ensure bibtex_import includes this field |
| "Invalid configuration" | exclude_types/exclude_reviews not boolean | Use true or false values |

### Examples

#### Basic Example - Standard Filtering
```yaml
- step: Filter to peer-reviewed research
  builtin.categorization:
    exclude_types: true
    exclude_reviews: true
```

#### Inclusive Example - Accept All Conferences
```yaml
- step: Include conference papers
  builtin.categorization:
    exclude_types: false
    exclude_reviews: true
```

#### Permissive Example - Include Reviews
```yaml
- step: Include literature reviews
  builtin.categorization:
    exclude_types: false
    exclude_reviews: false
```

### Related Steps

- **Upstream**: `deduplication`, `bibtex_import`, `checkpoint`
- **Downstream**: `keyword_screening`, `semantic_screening`, `checkpoint`, `summarize`
- **Alternative**: None (categorization is essential for quality control)

### Notes

- **exclude_types=true** removes conference papers and books, keeping only peer-reviewed journals
- **exclude_reviews=true** removes systematic reviews, literature reviews, and survey papers
- **Combined effect**: Both flags enable filtering to primary research in peer-reviewed journals only
- **Publication type detection** is based on BibTeX entry type mapping:
  - `article` → journal article (keep)
  - `inproceedings`, `conference` → conference paper (exclude if exclude_types=true)
  - `book`, `inbook` → book (exclude if exclude_types=true)
  - `review` → review paper (exclude if exclude_reviews=true)
- **Excluded papers are preserved** in database with EXCLUDED status for audit trail
- **Typical use**: Set both flags to true for high-quality systematic reviews
