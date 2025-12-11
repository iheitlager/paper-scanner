# Summarize

### Title
**Summarize** - Generates statistics and displays screening progression across stages

### Description

The Summarize step generates comprehensive reports about your paper collection and screening results. It displays database statistics, screening progression through multiple stages (categorization, keyword screening, semantic screening), and detailed breakdown of inclusion/exclusion decisions.

Use this step before export to verify your screening results and understand the composition of your final dataset.

### Features

- ✅ **Database statistics**: Total papers, papers per source, papers per type
- ✅ **Screening results table**: Shows progression through screening stages
- ✅ **Stage tracking**: Displays papers excluded at each stage (categorization, keyword, semantic)
- ✅ **Decision breakdown**: Shows counts for INCLUDED, EXCLUDED, MANUAL_REVIEW statuses
- ✅ **Inclusion rates**: Calculates and displays percentages for each stage
- ✅ **Comprehensive output**: Rich formatted tables with clear organization

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `screening` | `boolean` | No | `false` | Display screening results table (true) or database stats only |

#### YAML Definition

```yaml
- step: Display summary statistics
  builtin.summarize:
    screening: false

- step: Display screening progression
  builtin.summarize:
    screening: true
```

### Input/Output

#### Input
- **Format**: Papers and screening results from database
- **Source**: Database populated by prior steps
- **Requirements**: Database must be initialized with papers

#### Output
- **Format**: Console output with formatted tables
- **Display**: Human-readable statistics and progression table
- **No database changes**: Read-only, reporting-only step

### Validation

The step validates:
- `screening`: Must be boolean value if provided

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Empty database" | No papers in database | Run bibtex_import first |
| "Invalid configuration" | screening parameter not boolean | Use true or false |

### Examples

#### Basic Example - Database Statistics
```yaml
- step: Display database statistics
  builtin.summarize:
    screening: false
```

#### Screening Results Example
```yaml
- step: Display screening progression
  builtin.summarize:
    screening: true
```

#### Full Pipeline with Both Summaries
```yaml
- step: Import papers
  builtin.bibtex_import:
    batch_id: "batch1"
    imports:
      - name: "Scopus"
        file_path: "data/scopus.bib"
        source_type: "scopus"

- step: Deduplication
  builtin.deduplication:
    method: "all"

- step: Display deduplicated count
  builtin.summarize:
    screening: false

- step: Categorize papers
  builtin.categorization:
    exclude_reviews: true

- step: Keyword screening
  builtin.keyword_screening:
    inclusion_keywords: ["digital transformation"]
    exclusion_keywords: ["game", "fiction"]

- step: Semantic screening
  builtin.semantic_screening:
    thresholds:
      auto_include: 0.65

- step: Display final results
  builtin.summarize:
    screening: true
```

### Related Steps

- **Upstream**: Any screening steps (`categorization`, `keyword_screening`, `semantic_screening`)
- **Downstream**: `export`, or pipeline end
- **Alternative**: None (summarize provides unique reporting)

### Output Explanation

#### Database Statistics (screening: false)
```
Database Summary:
  Total Papers: 543
  By Source:
    scopus: 245
    ieee_xplore: 182
    web_of_science: 116
  By Type:
    Article: 450
    Conference: 93
```

#### Screening Results (screening: true)
```
Screening Progression:
  Initial: 543
  After Categorization: 523 (excluded: 20)
  After Keyword: 312 (excluded: 211)
  After Semantic: 287 (excluded: 25)
  Manual Review: 18
  Final Included: 269
  Inclusion Rate: 49.5%
```

### Related Steps

- **Upstream**: Screening steps
- **Downstream**: `export`
- **Alternative**: None

### Notes

- **Screening table shows progression** from import through all screening stages
- **Exclusion numbers cumulative** across stages (not duplicate-counted)
- **Manual review papers** are shown separately and included in decision tracking
- **Inclusion rate calculation**: (Final Included / Initial) * 100
- **Use before export** to verify your screening produced expected results
- **Run twice**: First with screening=false for baseline, then screening=true for final results
