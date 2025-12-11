# Deduplication

### Title
**Deduplication** - Removes duplicate papers using multi-method matching (DOI, fuzzy title+author, fuzzy title)

### Description

The Deduplication step identifies and removes duplicate papers that may have been imported from multiple databases or appear multiple times in the same import. It uses a three-tier matching strategy: exact DOI matching for precise identification, fuzzy title+author matching for variations in metadata, and fuzzy title-only matching for papers with missing author information.

Papers identified as duplicates are marked with a DEDUPLICATED status and hidden from downstream processing. The step preserves the first occurrence and marks subsequent duplicates, allowing traceability of deduplication decisions.

### Features

- ✅ **Multi-method matching**: DOI exact, title+author fuzzy, title-only fuzzy strategies
- ✅ **Configurable thresholds**: Set similarity thresholds for fuzzy matching (0-100 scale)
- ✅ **Incremental processing**: Efficiently deduplicates new batches against existing papers
- ✅ **Progress reporting**: Inline updates every 100 papers for large collections
- ✅ **Deduplication tracking**: Records which papers were marked as duplicates
- ✅ **Source preservation**: Keeps first occurrence with metadata from primary source

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `method` | `string` | No | `all` | Matching method: `exact_doi`, `fuzzy`, or `all` |
| `title_author_threshold` | `number` | No | `85` | Fuzzy match threshold for title+author (0-100) |
| `title_threshold` | `number` | No | `90` | Fuzzy match threshold for title-only (0-100) |
| `remove_duplicates` | `boolean` | No | `true` | Mark duplicates as DEDUPLICATED (true) or leave as-is |

#### YAML Definition

```yaml
- step: Remove duplicate papers
  builtin.deduplication:
    method: "all"
    title_author_threshold: 85
    title_threshold: 90
    remove_duplicates: true
```

### Input/Output

#### Input
- **Format**: Papers in database from prior imports
- **Source**: Database populated by bibtex_import or other data sources
- **Requirement**: At least one paper in database

#### Output
- **Format**: Papers with deduplication status set
- **Database**: Updates `Paper` model with `screening.status = DEDUPLICATED` for duplicates
- **Metrics**: Duplicates found and marked, deduplication percentage

### Validation

The step validates:
- `method`: Must be one of `exact_doi`, `fuzzy`, or `all`
- `title_author_threshold`: Must be a number between 0 and 100
- `title_threshold`: Must be a number between 0 and 100
- `remove_duplicates`: Must be boolean

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Empty database" | No papers to deduplicate | Run bibtex_import or other data source first |
| "Invalid threshold" | Threshold outside 0-100 range | Use values between 0 and 100 |
| "Database error" | Cannot read/write papers | Check database connection and permissions |

### Examples

#### Basic Example - Conservative Deduplication
```yaml
- step: Remove obvious duplicates
  builtin.deduplication:
    method: "exact_doi"
    remove_duplicates: true
```

#### Advanced Example - Aggressive Deduplication
```yaml
- step: Comprehensive deduplication
  builtin.deduplication:
    method: "all"
    title_author_threshold: 80
    title_threshold: 85
    remove_duplicates: true
```

#### Strict Matching Example
```yaml
- step: Strict fuzzy matching
  builtin.deduplication:
    method: "fuzzy"
    title_author_threshold: 95
    title_threshold: 98
    remove_duplicates: true
```

### Related Steps

- **Upstream**: `bibtex_import`, `checkpoint`
- **Downstream**: `categorization`, `keyword_screening`, `semantic_screening`
- **Alternative**: None (deduplication is essential step)

### Notes

- **DOI matching is exact** and most reliable when DOIs are present in the data
- **Fuzzy thresholds are configurable** to balance between false positives and false negatives
- **Higher thresholds are more conservative** (fewer duplicates marked) and safer for important data
- **Lower thresholds are more aggressive** but may incorrectly mark similar papers as duplicates
- **Recommended defaults**: title_author_threshold=85, title_threshold=90 for most use cases
- **Title-only matching** handles papers with missing or incomplete author information
- **Deduplication is incremental**: each run processes all papers but efficiently identifies new duplicates
