# BibTeX Import

### Title
**BibTeX Import** - Sequentially imports BibTeX files and adds papers to the database

### Description

The BibTeX Import step loads bibliographic data from BibTeX files into the paper scanner database. It supports imports from multiple sources (Scopus, IEEE Xplore, Web of Science) and tracks the source database for each import. Each paper is assigned a unique citation key and discovery metadata including the import batch ID and source type.

This is typically the first step in the paper screening pipeline, as it populates the database with papers to be analyzed. The step handles BibTeX format variations and entry types, mapping them to standardized paper types for consistent downstream processing.

### Features

- ✅ **Multi-source imports**: Supports Scopus, IEEE Xplore, Web of Science, and other BibTeX sources
- ✅ **Batch tracking**: Assigns batch ID to all papers from same import run for traceability
- ✅ **Entry type mapping**: Maps BibTeX entry types to standardized paper types (article, conference_paper, book, etc.)
- ✅ **Progress reporting**: Shows inline progress every 100 papers for large import batches
- ✅ **Error handling**: Gracefully handles malformed BibTeX entries and logs issues
- ✅ **Duplicate prevention**: Checks for existing papers before import
- ✅ **Discovery metadata**: Tracks import batch ID, source database, and import timestamp

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `batch_id` | `string` | Yes | - | Unique identifier for this import batch |
| `imports` | `list` | Yes | - | List of BibTeX files to import |
| `imports[].name` | `string` | Yes | - | Human-readable name for this import |
| `imports[].file_path` | `string` | Yes | - | Path to BibTeX file (relative or absolute) |
| `imports[].source_type` | `string` | Yes | - | Source database: `scopus`, `ieee_xplore`, `web_of_science`, or `other` |
| `imports[].expected_count` | `integer` | No | - | Expected number of entries (for validation) |

#### YAML Definition

```yaml
- step: Import BibTeX files
  builtin.bibtex_import:
    batch_id: "batch_id_value"
    imports:
      - name: "Source Name"
        file_path: "path/to/file.bib"
        source_type: scopus
        expected_count: 100
```

### Input/Output

#### Input
- **Format**: BibTeX files (.bib) containing bibliographic records
- **Source**: External files specified in configuration
- **Requirements**: Files must exist and contain valid BibTeX format entries

#### Output
- **Format**: Papers stored in database with metadata
- **Database**: `Paper` model with `Discovery` metadata
- **Metrics**: Papers imported, batch ID, source type, import timestamp

### Validation

The step validates:
- `batch_id`: Must be a non-empty string
- `imports`: Must be a list with at least one entry
- Each import entry must have `name`, `file_path`, and `source_type`
- `source_type` must be one of: `scopus`, `ieee_xplore`, `web_of_science`, `other`
- `expected_count` if provided must be a positive integer
- BibTeX files must exist at specified paths

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "File not found" | BibTeX file path doesn't exist | Check file path is correct and file exists |
| "Invalid BibTeX" | File contains malformed entries | Run through BibTeX validator, fix syntax errors |
| "Unknown source_type" | Invalid source_type value | Use one of: scopus, ieee_xplore, web_of_science, other |
| "Duplicate entry" | Paper with same cite_key already exists | Use different batch_id or remove duplicates from BibTeX |

### Examples

#### Basic Example
```yaml
- step: Import papers from Scopus
  builtin.bibtex_import:
    batch_id: "scopus_2024"
    imports:
      - name: "Scopus Papers"
        file_path: "data/scopus.bib"
        source_type: "scopus"
```

#### Advanced Example
```yaml
- step: Import from multiple databases
  builtin.bibtex_import:
    batch_id: "systematic_review_2024"
    imports:
      - name: "Scopus Digital Innovation"
        file_path: "data/scopus_digital_innovation.bib"
        source_type: "scopus"
        expected_count: 245
      
      - name: "IEEE Transformation"
        file_path: "data/ieee_transformation.bib"
        source_type: "ieee_xplore"
        expected_count: 182
      
      - name: "WoS Supplier Innovation"
        file_path: "data/wos_supplier_innovation.bib"
        source_type: "web_of_science"
        expected_count: 321
```

### Related Steps

- **Upstream**: None (usually the first step)
- **Downstream**: `checkpoint`, `deduplication`, `categorization`, `keyword_screening`
- **Alternative**: Database query import, CSV import

### Notes

- **Batch IDs should be unique** to track imports separately in the database and enable selective reprocessing
- **Large files (>10MB)** may take several minutes to process depending on system resources
- **Progress is reported every 100 papers** for large imports to provide feedback
- **Source type affects metadata extraction** and helps categorize papers appropriately
- **Expected count is optional** but recommended for validation and progress tracking
