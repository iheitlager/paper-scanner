# Load Files

### Title
**Load Files** - Extract metadata from PDF files and fetch bibliographic data from Crossref API

### Description

The Load Files step processes PDF files in a folder to extract metadata and build bibliographic records. It scans the specified directory for PDF files, extracts DOI information from each PDF, fetches complete metadata from the Crossref API, and stores the papers in the database. This step is useful for literature reviews where you have collections of PDF papers but need structured bibliographic data.

The step performs the following operations:
1. Scans folder for PDF files
2. Extracts DOI from PDF metadata or content
3. Fetches bibliographic data from Crossref API
4. Transforms metadata into standardized Paper models
5. Stores papers in database with discovery metadata
6. Optionally copies PDF files to archive with DOI-based filenames

### Features

- ✅ **DOI extraction**: Automatically extracts DOI from PDF metadata
- ✅ **Crossref integration**: Fetches complete bibliographic metadata from Crossref API
- ✅ **Metadata transformation**: Converts Crossref data to standardized Paper models
- ✅ **PDF archiving**: Optional copying of PDFs to archive folder with DOI-based filenames
- ✅ **Discovery tracking**: Records that papers were discovered from PDF folder
- ✅ **Abstract extraction**: Extracts and cleans abstracts when available
- ✅ **Author parsing**: Extracts author information from Crossref metadata
- ✅ **Error handling**: Gracefully handles PDFs without DOI or failed Crossref lookups

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | `string` | Yes | - | Path to folder containing PDF files (relative or absolute) |
| `store_path` | `string` | Yes | - | Path to folder for archiving PDF files with DOI-based names |
| `source` | `list` | No | `["crossref"]` | List of metadata sources to use (currently supports: `crossref`, `other`) |
| `download_details` | `boolean` | No | `false` | Whether to download PDFs and create archive copies |
| `expected_count` | `integer` | No | - | Expected number of PDFs (for validation/progress tracking) |

#### YAML Definition

```yaml
- step: Load papers from PDF folder
  builtin.load_files:
    file_path: "data/pdfs"
    store_path: "data/pdf_archive"
    source: ["crossref"]
    download_details: true
    expected_count: 150
```

### Input/Output

#### Input
- **Format**: PDF files in specified directory
- **Source**: Local file system
- **Requirements**: 
  - PDF files must contain extractable DOI information
  - Crossref API must be accessible
  - Write permissions required for store_path

#### Output
- **Format**: Papers stored in database with complete bibliographic metadata
- **Database**: `Paper` model with `PDFInfo` and `Discovery` metadata
- **Files**: Archived PDFs (if `download_details: true`) stored as `{DOI_formatted}.pdf`
- **Metadata**: 
  - Title, authors, year, journal, volume, issue, pages
  - Abstract (if available from Crossref)
  - Paper type (inferred from Crossref metadata)
  - Discovery method tracked as PDF folder source

### Validation

The step validates:
- `file_path`: Must be provided and be a valid path string
- `store_path`: Must be provided and be a valid path string
- `source`: Must be a list containing only valid source types (crossref, other)
- `download_details`: If provided, must be a boolean
- `expected_count`: If provided, must be a non-negative integer

### Error Handling

Common errors and how to resolve them:

| Error | Cause | Solution |
|-------|-------|----------|
| "File path does not exist" | Folder path doesn't exist | Check file_path points to valid directory containing PDFs |
| "Cannot write to store_path" | No write permissions | Check store_path exists and you have write permissions |
| "DOI not found in PDF" | PDF metadata doesn't contain DOI | Extract DOI manually or use alternative metadata source |
| "Crossref API error" | API unavailable or DOI not in Crossref | Check internet connection, verify DOI is valid |
| "Failed to extract metadata" | PDF is corrupted or unreadable | Try opening PDF in reader, check file integrity |

### Examples

#### Basic Example
```yaml
# Simple: Load PDFs and fetch metadata from Crossref
- step: Load papers from PDFs
  builtin.load_files:
    file_path: "data/collected_papers"
    store_path: "data/pdf_archive"
```

#### Advanced Example
```yaml
# Advanced: Load PDFs with validation and archiving
- step: Load papers from multiple PDF sources
  builtin.load_files:
    file_path: "data/systematic_review_pdfs"
    store_path: "data/archive/pdfs"
    source: ["crossref"]
    download_details: true
    expected_count: 250

# Display progress after loading
- step: Check papers loaded from PDFs
  builtin.summarize:
    screening: false
```

### Related Steps

- **Upstream**: None (usually a first data import step, alternative to BibTeX Import)
- **Downstream**: `deduplication`, `categorization`, `keyword_screening`
- **Alternative**: `bibtex_import` (for importing from BibTeX files instead)

### Notes

- **DOI extraction**: PDFs must have extractable DOI information in metadata or embedded text
- **Crossref rate limiting**: The step respects Crossref API rate limits (50 req/sec in polite pool)
- **Large collections**: Processing hundreds of PDFs may take 10+ minutes due to API lookups
- **Archive naming**: PDFs are renamed to `{formatted_DOI}.pdf` for consistency (e.g., `10_1234_example_2024_123.pdf`)
- **Duplicate handling**: After loading, use the `deduplication` step to remove any duplicates
- **Metadata quality**: Completeness of extracted metadata depends on Crossref entry quality for each DOI
