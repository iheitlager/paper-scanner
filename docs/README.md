# Paper Scanner Steps Documentation

This directory contains comprehensive documentation for all steps in the paper scanner pipeline.

## Pipeline Steps Overview

The paper scanner processes papers through a configurable pipeline of steps. Each step performs specific operations and can be combined to create flexible screening workflows.

**26 built-in steps** organized into 8 categories:
- 5 Data Import steps
- 2 Data Maintenance steps
- 3 Data Quality steps
- 2 Citation Management steps
- 6 Screening & Classification steps
- 2 Output & Reporting steps
- 1 Analysis step
- 3 Advanced/Utility steps

### Main Steps (Documented)

| # | Step | File | Purpose |
|---|------|------|---------|
| 1 | `bibtex_import` | [bibtex_import.md](./steps/bibtex_import.md) | Multi-source BibTeX import |
| 2 | `ris_import` | [ris_import.md](./steps/ris_import.md) | RIS file import |
| 3 | `input` | [input.md](./steps/input.md) | JSON Lines or stdin import |
| 4 | `load_files` | [load_files.md](./steps/load_files.md) | PDF scanning with Crossref metadata |
| 5 | `download_pdfs` | [download_pdfs.md](./steps/download_pdfs.md) | Multi-source PDF retrieval |
| 6 | `patch` | [patch.md](./steps/patch.md) | Update papers by DOI |
| 7 | `fix_cite_keys` | [fix_cite_keys.md](./steps/fix_cite_keys.md) | Fix citation keys |
| 8 | `deduplication` | [deduplication.md](./steps/deduplication.md) | Duplicate detection |
| 9 | `metadata_screening` | [metadata_screening.md](./steps/metadata_screening.md) | Filter by metadata |
| 10 | `categorization` | [categorization.md](./steps/categorization.md) | Filter by publication type |
| 11 | `citations` | [citations.md](./steps/citations.md) | Backward citation extraction |
| 12 | `retrieve_metadata` | [retrieve_metadata.md](./steps/retrieve_metadata.md) | Metadata enrichment from APIs |
| 13 | `keyword_screening` | [keyword_screening.md](./steps/keyword_screening.md) | Keyword-based filtering |
| 14 | `semantic_screening` | [semantic_screening.md](./steps/semantic_screening.md) | Embedding-based filtering |
| 15 | `rocchio_screening` | [rocchio_screening.md](./steps/rocchio_screening.md) | Adaptive Rocchio classification |
| 16 | `journal_screening` | [journal_screening.md](./steps/journal_screening.md) | Journal-based filtering |
| 17 | `llm_classification` | [llm_classification.md](./steps/llm_classification.md) | LLM-based classification |
| 18 | `rocchio_classifier` | [rocchio_classifier.md](./steps/rocchio_classifier.md) | Rocchio-based classifier |
| 19 | `report` | [report.md](./steps/report.md) | Statistics & reporting |
| 20 | `export` | [export.md](./steps/export.md) | Multi-format export |
| 21 | `generate_embeddings` | [generate_embeddings.md](./steps/generate_embeddings.md) | Generate text embeddings |
| 22 | `checkpoint` | [checkpoint.md](./steps/checkpoint.md) | Save pipeline state |
| 23 | `echo` | [echo.md](./steps/echo.md) | Display messages |
| 24 | `halt` | [halt.md](./steps/halt.md) | Conditional halt |
| 25 | `run_template` | [run_template.md](./steps/run_template.md) | Execute reusable template |
| 26 | `upload_database` | [upload_database.md](./steps/upload_database.md) | Upload to external database |

### Utility Steps (Internal)

| Step | Purpose |
|------|---------|
| `paper` | Utility: Create Paper objects from DOI specifications |

### Reference Documentation

| File | Purpose |
|------|---------|
| [cli_validate_command.md](./cli_validate_command.md) | Configuration validation reference |

### Step Categories

#### **Data Import**
- [**BibTeX Import**](./steps/bibtex_import.md) - Load papers from BibTeX files with batch tracking
- [**RIS Import**](./steps/ris_import.md) - Load papers from RIS files
- [**Input**](./steps/input.md) - Import papers from JSON Lines files or stdin
- [**Load Files**](./steps/load_files.md) - Extract metadata from PDF files and fetch from Crossref
- [**Download PDFs**](./steps/download_pdfs.md) - Retrieve PDF files from multiple sources

#### **Data Maintenance**
- [**Patch**](./steps/patch.md) - Update existing papers by DOI with field replacements and appends
- [**Fix Cite Keys**](./steps/fix_cite_keys.md) - Fix and normalize citation keys

#### **Data Quality**
- [**Deduplication**](./steps/deduplication.md) - Remove duplicate papers using multi-method matching
- [**Metadata Screening**](./steps/metadata_screening.md) - Filter by metadata characteristics
- [**Categorization**](./steps/categorization.md) - Filter by publication type and quality

#### **Citation Management**
- [**Citations**](./steps/citations.md) - Extract and resolve backward citations, build citation graph
- [**Retrieve Metadata**](./steps/retrieve_metadata.md) - Enrich papers with complete metadata from external APIs

#### **Screening & Classification**
- [**Keyword Screening**](./steps/keyword_screening.md) - Filter using inclusion/exclusion keywords
- [**Semantic Screening**](./steps/semantic_screening.md) - Filter using embedding-based relevance
- [**Journal Screening**](./steps/journal_screening.md) - Filter by journal quality tiers
- [**Rocchio Screening**](./steps/rocchio_screening.md) - Adaptive Rocchio algorithm with persistent centroids
- [**LLM Classification**](./steps/llm_classification.md) - Claude-based multi-category classification
- [**Rocchio Classifier**](./steps/rocchio_classifier.md) - ML-based Rocchio classifier with training

#### **Analysis & Embeddings**
- [**Generate Embeddings**](./steps/generate_embeddings.md) - Generate vector embeddings for semantic search

#### **Control Flow**
- [**Checkpoint**](./steps/checkpoint.md) - Save pipeline state for resuming
- [**Echo**](./steps/echo.md) - Display informational messages
- [**Halt**](./steps/halt.md) - Conditionally stop pipeline execution
- [**Run Template**](./steps/run_template.md) - Execute reusable step templates

#### **Output & Reporting**
- [**Report**](./steps/report.md) - Display statistics and screening results
- [**Export**](./steps/export.md) - Export papers in multiple formats (JSONL, BibTeX, CSV)
- [**Upload Database**](./steps/upload_database.md) - Upload results to external databases

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
    builtin.report:
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
    builtin.report:
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
bibtex_import → deduplication → categorization → keyword_screening → semantic_screening → report → export
```

### Incremental Update (Resume)
```
checkpoint → keyword_screening → semantic_screening → report → export
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
| ris_import | batch_id, imports[] | - |
| input | - | source |
| load_files | file_path, store_path | source, download_details |
| download_pdfs | store_path, sources[] | timeout, output_errors |
| patch | updates[] | - |
| fix_cite_keys | - | - |
| deduplication | - | method, thresholds |
| metadata_screening | - | filters |
| categorization | - | exclude_types, exclude_reviews |
| citations | - | - |
| retrieve_metadata | - | sources, cache |
| keyword_screening | - | inclusion_keywords[], exclusion_keywords[], thresholds |
| semantic_screening | - | model, thresholds |
| journal_screening | - | journals_file |
| rocchio_screening | - | centroids_file |
| llm_classification | categories[] | confidence_threshold, batch_size |
| rocchio_classifier | - | - |
| generate_embeddings | - | model, chunk_size |
| checkpoint | label | - |
| echo | - | message |
| halt | - | min_papers, message |
| run_template | template | - |
| report | - | summary, screening, citations |
| export | format, output_file | include_status, exclude_duplicates |
| upload_database | - | database_url |

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
5. **Monitor Progress**: Use report steps to check data at different stages
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
