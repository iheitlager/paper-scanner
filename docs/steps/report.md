# Report

### Title
**Report** - Displays comprehensive database statistics and paper collection summary

### Description

The Report step generates and displays detailed statistics about your paper collection and screening results. It provides summaries of paper sources, screening decisions, bibliography information, and database structure. Use this step to gain insights into your data at various pipeline stages, especially before export.

### Features

- ✅ **Database summary**: Total papers, sources, types, and statistics
- ✅ **Screening results**: Shows included/excluded/manual review counts and percentages
- ✅ **Citation analysis**: Histograms of citation counts and patterns
- ✅ **Bibliography**: BibTeX-formatted reference list from database
- ✅ **Source breakdown**: Papers by source with counts
- ✅ **Debug output**: Detailed database inspection for troubleshooting
- ✅ **Flexible reporting**: Choose which reports to display

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `summary` | `boolean` | No | `false` | Display database summary statistics |
| `screening` | `boolean` | No | `false` | Display screening results breakdown |
| `citations` | `boolean` | No | `false` | Display citations histogram and analysis |
| `bibliography` | `boolean` | No | `false` | Display formatted bibliography from database |
| `source` | `boolean` | No | `false` | Display papers grouped by source |
| `histogram` | `boolean` | No | `false` | Display frequency histograms |
| `debug` | `boolean` | No | `false` | Display detailed debug information |
| `tabulate` | `dict` or `list` | No | - | Tabulate specific field values (advanced) |

#### YAML Definition

```yaml
# Display summary statistics
- step: Show database summary
  builtin.report:
    summary: true

# Display screening results
- step: Show screening results
  builtin.report:
    screening: true

# Multiple reports at once
- step: Comprehensive report
  builtin.report:
    summary: true
    screening: true
    citations: true
    source: true
```

### Input/Output

#### Input
- **Format**: Papers and screening results from database
- **Source**: Database populated by prior steps
- **Requirements**: Database must be initialized (for meaningful output)

#### Output
- **Format**: Console output with formatted tables and statistics
- **Display**: Rich formatted tables with clear organization
- **Effects**: Read-only, no database modifications

### Validation

The step validates:
- Each boolean parameter must be `true` or `false`
- Unknown parameters generate validation errors
- `tabulate` parameter must be dict or list of dicts with `field` key
- `tabulate.duplicates` must be `false`, `true`, or `'only'`

### Report Types

#### Summary Report
Shows:
- Total paper count
- Papers by source (import batch)
- Papers by type (article, conference, etc.)
- Average citation count
- Tag distribution

#### Screening Report
Shows:
- Papers in each screening stage (categorization, keyword, semantic)
- Inclusion/exclusion/manual review counts
- Percentages at each stage
- Progression through pipeline

#### Citations Report
Shows:
- Citation count histogram
- Most cited papers
- Citation patterns by source
- Average citations by paper type

#### Bibliography Report
Shows:
- BibTeX-formatted reference list
- All metadata for each paper
- Formatted for import into reference managers

#### Source Report
Shows:
- Papers grouped by import source
- Count per source
- Source-specific statistics

#### Debug Report
Shows:
- Raw database structure
- Index information
- Performance metrics
- Storage statistics

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid boolean value" | Parameter not true/false | Use lowercase true/false |
| "Unknown report key" | Unrecognized parameter | Check parameter name |
| "Database empty" | No papers in database | Run prior import steps first |
| "Invalid tabulate config" | Missing 'field' key | Add 'field' to tabulate dict |

### Examples

#### Basic Example - Show Summary
```yaml
- step: Display database summary
  builtin.report:
    summary: true
```

#### Advanced Example - Full Analysis Report
```yaml
- step: Comprehensive database analysis
  builtin.report:
    summary: true
    screening: true
    source: true
    citations: true

- step: Export complete dataset
  builtin.export:
    format: "jsonl"
    output_file: "results/papers.jsonl"
```

#### Debug Example - Detailed Inspection
```yaml
- step: Inspect database structure
  builtin.report:
    debug: true

- step: Tabulate author distribution
  builtin.report:
    tabulate:
      field: "authors"
      duplicates: false
```

#### Pipeline with Progress Reports
```yaml
- step: Import papers
  builtin.bibtex_import:
    batch_id: "batch1"
    imports:
      - name: "Scopus"
        file_path: "data/scopus.bib"

- step: Report after import
  builtin.report:
    summary: true

- step: Deduplication
  builtin.deduplication:
    method: "exact"

- step: Report after deduplication
  builtin.report:
    summary: true
    screening: true

- step: Keyword screening
  builtin.keyword_screening:
    keywords: ["machine learning", "neural networks"]

- step: Final screening report
  builtin.report:
    screening: true
    citations: true
```

### See Also

- [Export](export.md) - Save papers to disk in various formats
- [Echo](echo.md) - Display simple messages for documentation
- [Deduplication](deduplication.md) - Remove duplicate papers
