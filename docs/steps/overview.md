# Steps Overview

This section documents all available pipeline steps in paper-scanner.

## What are Steps?

Steps are individual processing units that can be chained together to create pipelines. Each step:
- Has a specific responsibility (e.g., import, analyze, export)
- Takes configuration in YAML or Python
- Validates configuration before running
- Processes papers from the database
- Returns standardized results

## Available Steps

Click on each step to see detailed documentation:

| Step | Purpose | Status |
|------|---------|--------|
| [bibtex_import](overview.md) | Import papers from BibTeX files | ✅ Stable |
| [citations](overview.md) | Extract forward and backward citations | ✅ Stable |
| [deduplication](overview.md) | Find and remove duplicate papers | ✅ Stable |
| [export](overview.md) | Export papers to various formats | ✅ Stable |
| [patch](overview.md) | Update paper metadata | ✅ Stable |
| [retrieve_metadata](overview.md) | Fetch missing metadata | ✅ Stable |
| [run_template](overview.md) | Run analysis templates (LLM-based) | ✅ Stable |
| [semantic_screening](overview.md) | ML-based paper screening | ✅ Stable |
| [summarize](overview.md) | Summarize papers and generate reports | ✅ Stable |
| [upload_database](overview.md) | Upload papers to remote database | ✅ Stable |

## Common Usage Patterns

### Import and Process
```yaml
steps:
  - name: bibtex_import
    file: references.bib
  - name: retrieve_metadata
    methods: [crossref, openalex]
  - name: summarize
    summary: true
```

### Build Citation Network
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
      details: [openalex]
    forward:
      citations: [openalex]
```

### Find Duplicates
```yaml
steps:
  - name: deduplication
    strategy: doi_title_year
```

### Screen Papers
```yaml
steps:
  - name: semantic_screening
    model: sentence-transformers/all-MiniLM-L6-v2
    thresholds:
      include: 0.7
      exclude: 0.3
```

### Extract Findings
```yaml
steps:
  - name: run_template
    template: extract_findings
```

## Step Configuration

Each step has:
1. **Required fields** - Must be present
2. **Optional fields** - Improve functionality
3. **Defaults** - Used if not specified

All steps support:
- `dry_run` - Preview without database changes
- `verbose` - Show detailed output
- `debug` - Show debug information

## Validation

Steps validate their configuration:

```bash
# Validate without running
paper-processor definition.yml --validate-only

# Run with validation
paper-processor definition.yml --verbose
```

## Building Custom Steps

See [Architecture: Pipeline](../architecture/pipeline.md#step-development) for how to create custom steps.

## Chaining Steps

Steps execute sequentially:

```yaml
steps:
  - name: bibtex_import          # Step 1
    file: references.bib
  - name: citations               # Step 2 (runs after Step 1)
    backward:
      citations: [crossref]
  - name: export                  # Step 3 (runs after Step 2)
    format: bibtex
    output: processed.bib
```

Each step sees the results from previous steps and can operate on updated paper records.

## Error Handling

Steps provide detailed error information:

```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
    continue_on_not_found: true   # Don't fail on unresolved citations
    output_errors: errors.jsonl   # Log errors to file
```

## Performance Tips

1. **Batch Processing** - Most steps support batch_size
2. **Caching** - Results are cached; re-running is fast
3. **Filtering** - Process only relevant papers with filters
4. **Parallelization** - Some steps support parallel workers

## See Also

- [Quick Start](../guide/quick-start.md) - Tutorial with examples
- [Architecture: Pipeline](../architecture/pipeline.md) - How steps work
- [Step Development](../architecture/pipeline.md#step-development) - Create custom steps
