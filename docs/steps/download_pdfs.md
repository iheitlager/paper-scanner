# Download PDFs

### Title
**Download PDFs** - Fetches PDF files for papers from multiple sources (Unpaywall, CrossRef, OpenAlex, CORE, Publisher)

### Description

The Download PDFs step automatically retrieves PDF files for papers in your database that are missing PDF data. It integrates with multiple sources to fetch PDFs, including Unpaywall (open access), CrossRef metadata, OpenAlex, CORE, and publisher sites. The step downloads files to a specified directory and tracks successful retrievals.

Use this step to build a complete PDF collection for your literature review or to retrieve documents for full-text analysis.

### Features

- ✅ **Multi-source fetching**: Try multiple sources in configurable order
- ✅ **Selective download**: Only fetch for papers missing PDFs
- ✅ **Retry logic**: Built-in retry handling for network failures
- ✅ **Progress tracking**: Reports success/failure statistics
- ✅ **Error logging**: Optional detailed error output to file
- ✅ **Timeout control**: Configurable request timeouts
- ✅ **Large file support**: Handles files of various sizes

### Supported Sources

| Source | Coverage | Type | Notes |
|--------|----------|------|-------|
| `unpaywall` | ~20% OA | Open Access | Fastest, most direct |
| `crossref` | ~60% | Full Text Links | Via CrossRef API |
| `openalex` | ~50% | Links & Metadata | Through OpenAlex |
| `core` | ~30% | Open Access | CORE aggregator |
| `publisher` | ~40% | Official Source | Direct from publishers |

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `store_path` | `string` | Yes | - | Directory to store downloaded PDFs |
| `sources` | `list` | Yes | - | List of sources to try in order: `unpaywall`, `crossref`, `openalex`, `core`, `publisher` |
| `timeout` | `number` | No | `30` | Request timeout in seconds (must be >0) |
| `output_errors` | `string` | No | - | Optional file path to log download errors |

#### YAML Definition

```yaml
# Basic download with primary sources
- step: Download available PDFs
  builtin.download_pdfs:
    store_path: "pdfs"
    sources: ["unpaywall", "crossref", "publisher"]

# Comprehensive download with timeout and error logging
- step: Download PDFs from all sources
  builtin.download_pdfs:
    store_path: "data/pdfs"
    sources: ["unpaywall", "crossref", "openalex", "core", "publisher"]
    timeout: 60
    output_errors: "results/download_errors.jsonl"
```

### Input/Output

#### Input
- **Format**: Papers from database with DOI or metadata
- **Source**: Database populated by prior import steps
- **Requirements**: Papers with valid DOI or title/author metadata

#### Output
- **Files**: PDF files stored in `store_path` directory
- **Stats**: Count of successful downloads, failures, and skipped papers
- **Errors**: Optional error log in JSONL format if `output_errors` specified
- **Updates**: Database updated with PDF file paths

### Validation

The step validates:
- `store_path` is required and must be a string
- `sources` is required, must be a list, non-empty, with valid source names
- `timeout` must be a positive number if specified
- `output_errors` must be a valid file path string if specified
- Storage directory must be writable

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "store_path is required" | Missing parameter | Add store_path to configuration |
| "Invalid sources" | Unsupported source name | Use: unpaywall, crossref, openalex, core, publisher |
| "sources list is empty" | No sources specified | Add at least one valid source |
| "timeout must be positive" | Invalid timeout value | Use number > 0 |
| "Directory not writable" | Cannot write PDFs | Check directory permissions |
| "Network error" | Connection failure | Check internet, retry with higher timeout |

### Download Process

1. **Identify**: Find papers in database without PDF data
2. **Try sources**: Attempt each source in configured order
3. **Fetch**: Download first successful match
4. **Store**: Save to `store_path` with paper ID/DOI filename
5. **Track**: Update database with file path
6. **Report**: Output statistics and optional errors

### Examples

#### Basic Example - Simple Download
```yaml
- step: Download PDFs to local storage
  builtin.download_pdfs:
    store_path: "pdfs"
    sources: ["unpaywall", "crossref"]
```

#### Advanced Example - Comprehensive with Error Tracking
```yaml
- step: Import papers from BibTeX
  builtin.bibtex_import:
    batch_id: "batch1"
    imports:
      - name: "Scopus"
        file_path: "data/scopus.bib"

- step: Deduplicate
  builtin.deduplication:
    method: "exact"

- step: Download all PDFs with detailed error logging
  builtin.download_pdfs:
    store_path: "data/pdfs"
    sources: ["unpaywall", "crossref", "openalex", "core", "publisher"]
    timeout: 60
    output_errors: "results/pdf_download_errors.jsonl"

- step: Report results
  builtin.report:
    summary: true

- step: Export final dataset
  builtin.export:
    format: "jsonl"
    output_file: "results/papers_with_pdfs.jsonl"
```

#### Retry with Longer Timeout
```yaml
- step: Download PDFs with extended timeout for slow networks
  builtin.download_pdfs:
    store_path: "pdfs"
    sources: ["unpaywall", "crossref", "publisher"]
    timeout: 120
    output_errors: "errors.jsonl"
```

### Configuration Notes

- **Source order matters**: Try fastest/most reliable sources first
- **Timeout adjustment**: Increase for slow connections, decrease for fast networks
- **Error logging**: Always recommend using `output_errors` for production workflows
- **Storage**: Ensure `store_path` has sufficient disk space for all PDFs
- **Network**: Respect rate limits; many sources have strict API limits

### Statistics Output

The step reports:
- `total_papers`: Papers processed
- `downloaded`: Successfully downloaded PDFs
- `failed`: Failed to retrieve (after trying all sources)
- `skipped`: Already had PDF data
- `success_rate`: Percentage successfully downloaded

### See Also

- [Retrieve Metadata](retrieve_metadata.md) - Fetch paper metadata
- [Bibtex Import](bibtex_import.md) - Import papers with metadata
- [Export](export.md) - Save papers with PDF paths
