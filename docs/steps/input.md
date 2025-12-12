# Input

### Title
**Input** - Read JSON Lines data from file or stdin and import papers into the database

### Description

The Input step loads papers from JSON Lines format files or from standard input. This is useful for importing papers that have already been processed and serialized as JSON, or for integrating with other tools that output JSON Lines format. Each line should be a valid JSON object representing a paper with bibliographic metadata.

Unlike BibTeX Import or Load Files, the Input step performs minimal processing - it simply deserializes the JSON data and adds papers to the database without further enrichment or validation.

### Features

- ✅ **File input**: Import from JSON Lines files with path expansion (~)
- ✅ **Stdin input**: Read JSON Lines directly from standard input for pipeline integration
- ✅ **Flexible format**: Accepts any JSON object structure, converts to Paper model
- ✅ **Record counting**: Validates expected record count if specified
- ✅ **Error handling**: Skips invalid JSON lines and reports failures
- ✅ **Discovery tracking**: Records papers as manually imported
- ✅ **Minimal processing**: No enrichment or transformation, just import

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file` | `string` | No* | - | Path to JSON Lines file (relative, absolute, or with ~) |
| `input` | `string` | No* | - | Input source; currently only supports `stdin` |
| `expected_count` | `integer` | No | - | Expected number of records (validation only) |

*Either `file` or `input` must be specified. If both are provided, `file` takes precedence.

#### YAML Definition

```yaml
# Import from file
- step: Load papers from JSON file
  builtin.input:
    file: "data/papers.jsonl"
    expected_count: 100

# Read from stdin
- step: Load papers from pipe
  builtin.input:
    input: stdin

# Using both (file takes precedence)
- step: Load with fallback
  builtin.input:
    file: "data/papers.jsonl"
    input: stdin
    expected_count: 50
```

### Input/Output

#### Input
- **Format**: JSON Lines (.jsonl or stdin) - one JSON object per line
- **Source**: File system or standard input
- **Requirements**: Valid JSON objects with optional Paper fields (title, authors, year, etc.)

#### Output
- **Format**: Papers stored in database with Discovery metadata
- **Database**: `Paper` model with manually-set discovery method
- **Metadata**: Discovery method set to `MANUAL`
- **Fields**: All JSON fields are preserved in the paper record

### Validation

The step validates:
- At least one of `file` or `input` must be specified
- If `file` is specified, it must be a string
- If `input` is specified, it must be a string with value `stdin`
- `expected_count` if provided must be a non-negative integer
- File must exist and be readable (checked at runtime)
- Each JSON line must be valid JSON

### Error Handling

Common errors and how to resolve them:

| Error | Cause | Solution |
|-------|-------|----------|
| "Either 'file' or 'input' must be specified" | Missing both config options | Add either `file:` or `input: stdin` to config |
| "File not found" | File path doesn't exist | Check file path is correct and file exists |
| "Invalid JSON" on line N | Malformed JSON in file | Check that each line is valid JSON, fix syntax errors |
| "Expected N records but got M" | Mismatch with expected_count | Adjust expected_count or verify input data |

### Examples

#### Basic File Import
```yaml
- step: Load papers from JSON file
  builtin.input:
    file: "data/papers.jsonl"
```

#### Stdin Import (Pipeline Integration)
```bash
# Use with pipe from another tool
cat papers.jsonl | python -m paper_scanner.cli run definition.yml
```

```yaml
- step: Load papers from stdin
  builtin.input:
    input: stdin
    expected_count: 100
```

#### Advanced Example with Validation
```yaml
- step: Import papers with validation
  builtin.input:
    file: "data/systematic_review_papers.jsonl"
    expected_count: 245

- step: Display import statistics
  builtin.echo:
    message: "Papers imported successfully"

- step: Remove any duplicates
  builtin.deduplication:
    method: "all"

- step: Export results
  builtin.export:
    format: "jsonl"
    output: "results.jsonl"
```

### Related Steps

- **Upstream**: None (usually a first data import step, alternative to BibTeX Import or Load Files)
- **Downstream**: `deduplication`, `categorization`, `keyword_screening`
- **Alternative**: `bibtex_import` (for BibTeX files), `load_files` (for PDFs)

### Notes

- **JSON format**: Input should be standard JSON Lines format - one complete JSON object per line
- **Field mapping**: All JSON fields are preserved and mapped to Paper model fields where applicable
- **Discovery method**: All imported papers are marked with `MANUAL` discovery method
- **Error tolerance**: Invalid JSON lines are skipped with a warning; import continues
- **Empty lines**: Empty lines are silently skipped
- **Large files**: For very large files (>1GB), consider splitting into chunks and using stdin
- **Type conversion**: JSON values are converted to appropriate Python types automatically
