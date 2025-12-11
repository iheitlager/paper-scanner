# Export

### Title
**Export** - Exports papers in multiple formats (JSONL, BibTeX, CSV) with filtering options

### Description

The Export step extracts papers from the database and saves them in standardized formats for use in external tools or for sharing results. It supports multiple output formats including JSONL (JSON Lines), BibTeX, and CSV, with options to filter included/excluded papers and remove duplicates.

Use this step at the end of your pipeline to generate the deliverables for your systematic review or literature analysis.

### Features

- ✅ **Multiple formats**: Export as JSONL, BibTeX, or CSV
- ✅ **Status filtering**: Export only included, excluded, or all papers
- ✅ **Duplicate removal**: Option to exclude deduplicated papers from export
- ✅ **Standardized output**: Consistent field mappings and structured data
- ✅ **Large dataset support**: Efficient batch processing for many papers
- ✅ **Metadata preservation**: Keeps screening decisions and source information

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `format` | `string` | Yes | - | Output format: `jsonl`, `bibtex`, or `csv` |
| `output_file` | `string` | Yes | - | Path for output file (relative or absolute) |
| `include_status` | `string` | No | `included` | Filter by status: `included`, `excluded`, or `all` |
| `exclude_duplicates` | `boolean` | No | `true` | Exclude papers marked as DEDUPLICATED |

#### YAML Definition

```yaml
- step: Export included papers
  builtin.export:
    format: "jsonl"
    output_file: "results/papers.jsonl"
    include_status: "included"
    exclude_duplicates: true
```

### Input/Output

#### Input
- **Format**: Papers from database with screening results
- **Source**: Database populated by pipeline steps
- **Requirements**: Database must be initialized with papers

#### Output
- **Format**: JSONL, BibTeX, or CSV files
- **File**: Written to specified output_file path
- **Metadata**: Includes all paper data and screening decisions
- **Encoding**: UTF-8 with proper special character handling

### Validation

The step validates:
- `format`: Must be one of `jsonl`, `bibtex`, or `csv`
- `output_file`: Must be a non-empty string and valid file path
- `include_status`: Must be one of `included`, `excluded`, or `all`
- `exclude_duplicates`: Must be boolean
- Output directory must exist and be writable

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid format" | format parameter not jsonl/bibtex/csv | Use valid format value |
| "Directory not found" | Output directory doesn't exist | Create directory or use existing path |
| "Permission denied" | Cannot write to output file | Check file permissions, use different directory |
| "Empty database" | No papers to export | Run prior steps to populate database |

### Examples

#### Basic Example - JSONL Export
```yaml
- step: Export papers to JSONL
  builtin.export:
    format: "jsonl"
    output_file: "results.jsonl"
```

#### Advanced Example - Multiple Format Exports
```yaml
- step: Export included papers as JSONL
  builtin.export:
    format: "jsonl"
    output_file: "results/included_papers.jsonl"
    include_status: "included"
    exclude_duplicates: true

- step: Export excluded papers for audit
  builtin.export:
    format: "jsonl"
    output_file: "results/excluded_papers.jsonl"
    include_status: "excluded"
    exclude_duplicates: true

- step: Export as BibTeX for reference managers
  builtin.export:
    format: "bibtex"
    output_file: "results/papers.bib"
    include_status: "included"

- step: Export as CSV for spreadsheet analysis
  builtin.export:
    format: "csv"
    output_file: "results/papers.csv"
    include_status: "included"
```

#### Full Pipeline with Export
```yaml
- step: Import papers
  builtin.bibtex_import:
    batch_id: "batch1"
    imports:
      - name: "Scopus"
        file_path: "data/scopus.bib"
        source_type: "scopus"

- step: Screening steps...
  # ... categorization, keyword, semantic steps ...

- step: Export final results
  builtin.export:
    format: "jsonl"
    output_file: "systematic_review_results.jsonl"
    include_status: "included"
    exclude_duplicates: true

- step: Export audit trail
  builtin.export:
    format: "jsonl"
    output_file: "systematic_review_excluded.jsonl"
    include_status: "excluded"
    exclude_duplicates: false
```

### Related Steps

- **Upstream**: All screening steps
- **Downstream**: None (usually final step)
- **Alternative**: Database direct access for custom queries

### Output Format Details

#### JSONL Format
```json
{"cite_key": "smith2024", "title": "...", "authors": [...], "year": 2024, "screening": {"final_decision": "INCLUDED", "notes": "...}}
{"cite_key": "jones2023", "title": "...", "authors": [...], "year": 2023, "screening": {"final_decision": "INCLUDED", "notes": "..."}}
```

#### BibTeX Format
```bibtex
@article{smith2024,
  title={...},
  author={Smith, J. and Brown, A.},
  journal={Journal Name},
  year={2024}
}
@article{jones2023,
  title={...},
  author={Jones, B.},
  journal={Another Journal},
  year={2023}
}
```

#### CSV Format
```csv
cite_key,title,authors,year,journal,final_decision,notes
smith2024,"...",Smith; Brown,2024,Journal Name,INCLUDED,"..."
jones2023,"...",Jones,2023,Another Journal,INCLUDED,"..."
```

### Related Steps

- **Upstream**: Screening and filtering steps
- **Downstream**: External tools, reference managers
- **Alternative**: None

### Notes

- **JSONL format** is most complete, preserving all metadata and screening decisions
- **BibTeX format** is ideal for use with reference managers (Zotero, Mendeley, etc.)
- **CSV format** is easiest to import into spreadsheets for additional analysis
- **include_status filtering** helps generate separate reports for included/excluded papers
- **exclude_duplicates option** removes papers marked DEDUPLICATED by deduplication step
- **File paths can be relative** (relative to working directory) or absolute
- **Overwrite behavior**: Existing files are overwritten without warning
- **Typical workflow**: Export both JSONL (for detailed analysis) and BibTeX (for reference managers)
