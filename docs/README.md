# Paper Scanner Steps Documentation

This directory contains comprehensive documentation for all steps in the paper scanner pipeline.

## Pipeline Steps Overview

The paper scanner processes papers through a configurable pipeline of steps. Each step performs specific operations and can be combined to create flexible screening workflows.

### Documentation Files

| # | File | Purpose | Lines |
|---|------|---------|-------|
| 1 | `README.md` | Index, workflow patterns, best practices | 280+ |
| 2 | `cli_validate_command.md` | Configuration validation | 180+ |



| # | File | Purpose | Lines |
|---|------|---------|-------|
| 1 | `bibtex_import.md` | Multi-source BibTeX import step | 130+ |
| 2 | `input.md` | JSON Lines file or stdin import step | 130+ |
| 3 | `load_files.md` | PDF folder scanning and Crossref metadata fetching | 140+ |
| 4 | `patch.md` | Update existing papers by DOI with replace/append operations | 190+ |
| 5 | `deduplication.md` | Duplicate detection step | 120+ |
| 6 | `categorization.md` | Publication type filtering step | 120+ |
| 7 | `keyword_screening.md` | Keyword-based screening step | 140+ |
| 8 | `semantic_screening.md` | Embedding-based screening step | 144+ |
| 9 | `checkpoint.md` | State saving step | 100+ |
| 10 | `echo.md` | Messaging step | 90+ |
| 11 | `halt.md` | Conditional halt step | 100+ |
| 12 | `summarize.md` | Statistics/reporting step | 140+ |
| 13 | `export.md` | Multi-format export step | 150+ |

### Step Categories

#### **Data Import**
- [**BibTeX Import**](./steps/bibtex_import.md) - Load papers from BibTeX files with batch tracking
- [**Input**](./steps/input.md) - Import papers from JSON Lines files or stdin
- [**Load Files**](./steps/load_files.md) - Extract metadata from PDF files and fetch from Crossref

#### **Data Maintenance**
- [**Patch**](./steps/patch.md) - Update existing papers by DOI with field replacements and appends

#### **Data Quality**
- [**Deduplication**](./steps/deduplication.md) - Remove duplicate papers using multi-method matching
- [**Categorization**](./steps/categorization.md) - Filter by publication type and quality

#### **Screening & Filtering**
- [**Keyword Screening**](./steps/keyword_screening.md) - Filter using inclusion/exclusion keywords
- [**Semantic Screening**](./steps/semantic_screening.md) - Filter using embedding-based relevance

#### **Checkpoints & Control Flow**
- [**Checkpoint**](./steps/checkpoint.md) - Save pipeline state for resuming
- [**Echo**](./steps/echo.md) - Display informational messages
- [**Halt**](./steps/halt.md) - Conditionally stop pipeline execution

#### **Output & Reporting**
- [**Summarize**](./steps/summarize.md) - Display statistics and screening results
- [**Export**](./steps/export.md) - Export papers in multiple formats (JSONL, BibTeX, CSV)

#### **CLI Tools**
- [**Validate Command**](./cli_validate_command.md) - Validate definition YAML before running

## Complete Pipeline Example

```yaml
project:
  name: "Digital Transformation Systematic Review"
  research_question: "How is digital transformation impacting supply chain management?"

pipeline:
  # 1. Import papers from multiple databases
  - step: Import from Scopus
    builtin.bibtex_import:
      batch_id: "batch_2024"
      imports:
        - name: "Scopus Digital Transformation"
          file_path: "data/scopus.bib"
          source_type: "scopus"
        - name: "IEEE Xplore Supply Chain"
          file_path: "data/ieee.bib"
          source_type: "ieee_xplore"

  # 2. Remove duplicates
  - step: Remove duplicates
    builtin.deduplication:
      method: "all"
      title_author_threshold: 85
      title_threshold: 90

  # 3. Check baseline
  - step: Display after deduplication
    builtin.summarize:
      screening: false

  # 4. Filter to peer-reviewed research
  - step: Categorize papers
    builtin.categorization:
      exclude_types: true
      exclude_reviews: true

  # 5. Save checkpoint
  - step: Checkpoint after categorization
    builtin.checkpoint:
      name: "categorized"

  # 6. Keyword-based screening
  - step: Screen by keywords
    builtin.keyword_screening:
      inclusion_keywords:
        - "digital transformation"
        - "Industry 4.0"
        - "supply chain"
      exclusion_keywords:
        - "fiction"
        - "game"
      inclusion_threshold: 60

  # 7. Semantic relevance screening
  - step: Semantic screening
    builtin.semantic_screening:
      model: "all-mpnet-base-v2"
      thresholds:
        auto_include: 0.65
        manual_review: 0.55
        auto_exclude: 0.55

  # 8. Display screening results
  - step: Display screening progression
    builtin.summarize:
      screening: true

  # 9. Export results
  - step: Export included papers
    builtin.export:
      format: "jsonl"
      output_file: "results/papers_included.jsonl"
      include_status: "included"

  - step: Export for audit
    builtin.export:
      format: "jsonl"
      output_file: "results/papers_excluded.jsonl"
      include_status: "excluded"

  - step: Export for reference manager
    builtin.export:
      format: "bibtex"
      output_file: "results/papers.bib"
      include_status: "included"
```

## Step Workflow Patterns

### Quick Screening (Fast)
```
bibtex_import → deduplication → categorization → keyword_screening → export
```

### Comprehensive Screening (High Quality)
```
bibtex_import → deduplication → categorization → keyword_screening → semantic_screening → summarize → export
```

### Incremental Update (Resume)
```
checkpoint → keyword_screening → semantic_screening → summarize → export
```

### Development & Testing
```
bibtex_import → checkpoint → categorization → halt (min_papers: 10) → keyword_screening → export
```

## Configuration Quick Reference

### Common Parameters

| Step | Required Parameters | Optional Parameters |
|------|-------------------|-------------------|
| bibtex_import | batch_id, imports[] | - |
| deduplication | - | method, title_author_threshold, title_threshold |
| categorization | - | exclude_types, exclude_reviews |
| keyword_screening | - | inclusion_keywords[], exclusion_keywords[], thresholds |
| semantic_screening | - | model, thresholds |
| checkpoint | name | - |
| echo | - | message |
| halt | - | min_papers, message |
| summarize | - | screening |
| export | format, output_file | include_status, exclude_duplicates |

## Validation

Always validate your definition file before running:

```bash
python -m paper_scanner.cli validate definition.yml
```

See [**Validate Command**](./cli_validate_command.md) documentation for detailed validation rules.

## Running the Pipeline

### Basic Run
```bash
python -m paper_scanner.cli run definition.yml
```

### Run with Automatic Validation
```bash
python -m paper_scanner.cli run definition.yml --validate
```

### Database Selection
```bash
python -m paper_scanner.cli run definition.yml --db postgresql://user:pass@localhost/papers
```

## Best Practices

1. **Start Simple**: Begin with basic import → deduplication → export pipeline
2. **Add Screening Incrementally**: Add keyword screening, then semantic screening
3. **Use Checkpoints**: Save state after expensive operations (deduplication, semantic screening)
4. **Validate Early**: Run validate command before running full pipeline
5. **Monitor Progress**: Use summarize steps to check data at different stages
6. **Export Multiple Formats**: JSONL for analysis, BibTeX for reference managers
7. **Review Manual Cases**: Always check papers marked for manual_review
8. **Audit Trail**: Keep excluded papers for transparency in systematic reviews

## Performance Tips

- **Large imports (>5000 papers)**: Place checkpoint after deduplication
- **Semantic screening**: Most expensive operation, second to last step
- **Batch efficiency**: Process all papers in one run vs. multiple small batches
- **Memory**: Semantic screening with large models may need 4GB+ RAM
- **Parallel**: Currently runs single-threaded; consider external parallelization

## Troubleshooting

### No papers imported
- Check BibTeX file paths are correct
- Verify BibTeX file has valid entries
- Check batch_id is unique (not conflict with prior imports)

### Too many papers excluded
- Review keyword thresholds in keyword_screening
- Check semantic_screening thresholds aren't too strict
- Verify categorization filters match your scope

### Pipeline runs slowly
- Semantic screening is slower for large datasets
- Consider using checkpoint before semantic_screening
- Reduce batch size if memory issues occur

### Manual review has many papers
- Lower manual_review thresholds in semantic_screening
- Add more inclusion keywords to keyword_screening
- Review research_question for clarity

## Advanced Topics

### Custom Steps
While this documentation covers built-in steps, the framework supports custom step implementations. See main documentation for custom step development.

### Database Options
Steps work with both SQLite (default, single-file) and PostgreSQL (production, multi-user). See main documentation for database configuration.

### Research Question Optimization
Semantic screening quality depends on research_question clarity:
- Be specific: "How is digital transformation impacting supply chains?" > "What is innovation?"
- Include key concepts: Combine domain terms with scope terms
- Iterate: Test different questions and compare results

## Related Documentation

- [Main README](../README.md) - Project overview and setup
- [CLI Tools](../CLI_TOOLS.md) - Command-line interface reference
- [Paper Processor](../PAPER_PROCESSOR.md) - Detailed processor documentation
- [Testing](../TESTING.md) - Test suite documentation

## Step Implementation Details

For developers implementing custom steps, see the built-in step implementations:
- Location: `/src/paper_scanner/steps/`
- Pattern: Each step is a module with `validate()` and `execute()` functions
- Naming: `builtin.{step_name}` corresponds to file `{step_name}.py`

## Version History

- **v1.0**: All 11 built-in steps fully documented with examples
- Semantic screening: Latest addition (embedding-based relevance)
- Validation: Pre-flight configuration checking
- Progress reporting: Inline updates during long operations
