# Definition File Processor

Process YAML definition files and execute sequential steps for the Paper Scanner.

## Usage

```bash
# Basic usage
uv run process_definition.py <definition_file.yml>

# With verbose output
uv run process_definition.py <definition_file.yml> -v

# Dry run (preview without executing)
uv run process_definition.py <definition_file.yml> --dry-run

# Save results to JSON
uv run process_definition.py <definition_file.yml> -o results.json

# Combine options
uv run process_definition.py <definition_file.yml> -v --dry-run -o results.json
```

## Available Steps

### `bibtex_import`

Import BibTeX files and add papers to the database.

**Configuration:**
```yaml
- step: bibtex_import
  batch_id: "import_2024_12_09"
  imports:
    - name: "Source Name"
      description: "Optional description"
      file_path: "path/to/file.bib"
      source_type: "scopus|wos|ieee|manual"
      expected_count: 100  # Optional, for validation
```

### `database_summary`

Output database statistics and relevant facts.

**Configuration:**
```yaml
- step: database_summary
```

## Definition File Example

```yaml
# Project metadata
project:
  name: "My Research Project"
  description: "Project description"
  researcher: "Name"
  institution: "University"

# Search metadata (optional)
search:
  name: "Search name"
  date_range:
    from: 2015
    to: 2024
  databases:
    - scopus
    - web_of_science
    - ieee_xplore

# Sequential processing steps
steps:
  - step: bibtex_import
    batch_id: "import_2024_12_09"
    imports:
      - name: "Scopus Results"
        file_path: "data/scopus.bib"
        source_type: "scopus"
        expected_count: 500
      
      - name: "IEEE Results"
        file_path: "data/ieee.bib"
        source_type: "ieee"
        expected_count: 300
  
  - step: database_summary
```

## Options

- `-v, --verbose`: Enable verbose output with detailed information
- `--dry-run`: Don't actually execute steps, just show what would happen
- `-o, --output PATH`: Save execution results to JSON file

## Output

Without `-o`, results are printed to stdout. With `-o`, results are saved to JSON:

```json
{
  "definition_file": "path/to/file.yml",
  "timestamp": "2024-12-09T10:30:00",
  "dry_run": false,
  "steps_executed": [
    {
      "step": "bibtex_import",
      "batch_id": "import_2024_12_09",
      "total_files": 2,
      "files_processed": 2,
      "papers_imported": 800,
      "errors": [],
      "details": [...]
    },
    {
      "step": "database_summary",
      "statistics": {
        "total_papers": 800,
        "unique_authors": 1200,
        "year_range": "2015-2024",
        ...
      }
    }
  ],
  "total_papers": 800,
  "errors": []
}
```

## Examples

### Preview what would be imported
```bash
uv run process_definition.py definition.yml -v --dry-run
```

### Execute full import with results
```bash
uv run process_definition.py definition.yml -v -o results.json
```

### Quiet mode
```bash
uv run process_definition.py definition.yml
```
