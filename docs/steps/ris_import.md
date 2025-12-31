# RIS Import

### Title
**RIS Import** - Sequentially imports RIS files and adds papers to the database

### Description

The RIS Import step loads bibliographic data from RIS (Research Information Systems) files into the paper scanner database. RIS is a widely-used format exported by academic databases including ProQuest, Scopus, Web of Science, Mendeley, and Zotero. Each paper is assigned a unique citation key derived from accession numbers or DOI when available, with automatic key generation as fallback. Papers are tracked with discovery metadata including source database and import timestamp.

This is typically the first step in the paper screening pipeline when importing from RIS-based sources. The step handles RIS format variations, normalizes field data (titles, authors, keywords), and maps paper types to standardized categories for consistent downstream processing.

### Features

- ✅ **Multi-source support**: ProQuest, Scopus, Web of Science, Mendeley, Zotero, and other RIS sources
- ✅ **Smart cite keys**: 3-tier fallback strategy (accession number → DOI → auto-generated hash)
- ✅ **Field normalization**: Title case, whitespace cleanup, ampersand normalization
- ✅ **Multi-value fields**: Handles multiple authors and keywords properly
- ✅ **Type inference**: Maps RIS entry types to standardized paper types
- ✅ **Flexible imports**: Single file or batch processing with limit and randomization
- ✅ **Discovery tracking**: Records source database and discovery method for traceability
- ✅ **Collision handling**: Optional cite_key collision detection and resolution

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | `string` | Yes | - | Path to RIS file (relative or absolute) |
| `source_database` | `string` | No | `other` | Source database: `proquest`, `scopus`, `web_of_science`, `mendeley`, `zotero`, `other` |
| `limit` | `integer` | No | - | Maximum number of papers to import (no limit if omitted) |
| `randomize` | `boolean` | No | `false` | Randomize paper order before applying limit |
| `random_seed` | `integer` | No | - | Seed for randomization (for reproducibility) |
| `expected_count` | `integer` | No | - | Expected number of papers (used for validation) |
| `fix_cite_key` | `boolean` | No | `false` | Auto-fix cite_key collisions with existing database entries |

#### YAML Definition

```yaml
- step: Import RIS file
  builtin.ris_import:
    file_path: "path/to/file.ris"
    source_database: "proquest"
```

#### YAML with Options

```yaml
- step: Import and randomize ProQuest papers
  builtin.ris_import:
    file_path: "data/proquest_export.ris"
    source_database: "proquest"
    limit: 100
    randomize: true
    random_seed: 42
    expected_count: 500
    fix_cite_key: true
```

### Input/Output

#### Input
- **Format**: RIS files (.ris) containing bibliographic records in RIS format
- **Structure**: Records delimited by `TY` (Type) start tag and `ER` (End Record) tag
- **Fields**: 18+ tags including AU (authors), TI (title), JF (journal), AN (accession number), etc.
- **Requirements**: Valid RIS format, readable text file

#### Output
- **Format**: Papers stored in database with structured metadata
- **Database**: `Paper` model instances with `Discovery` metadata
- **Cite Keys**: Generated from: accession number (ris_an_*) → DOI (ris_doi_*) → hash (ris_auto_*)
- **Discovery Method**: Set to `KEYWORD_SEARCH` for database exports
- **Metrics**: Number of papers imported, cite_key collisions fixed (if applicable)

### Field Mapping

| RIS Tag | Description | Paper Field | Notes |
|---------|-------------|-------------|-------|
| `TY` | Type | paper_type | Maps to JOUR, CONF, BOOK, etc. |
| `AU` | Author (repeating) | authors | Parsed as "Last, First" |
| `TI` | Title | title | Title case normalized |
| `JF` | Journal/Publication | journal | Title case normalized |
| `PY` | Publication year | year | Parsed as integer |
| `DO` | DOI | doi | Used for cite_key if AN unavailable |
| `AN` | Accession number | source_key | Primary source for cite_key |
| `AB` | Abstract | abstract | Whitespace normalized |
| `KW` | Keywords (repeating) | keywords | Lowercase normalized |
| `PB` | Publisher | publisher | Optional field |
| `VO` | Volume | volume | Optional field |
| `IS` | Issue | issue | Optional field |
| `SP` | Start page | pages_start | Optional field |
| `EP` | End page | pages_end | Optional field |

### Validation

The step validates:
- `file_path`: Must be a non-empty string pointing to existing readable file
- `source_database`: Must be one of: `proquest`, `scopus`, `web_of_science`, `mendeley`, `zotero`, `other`
- `limit`: If provided, must be positive integer
- `randomize`: Must be boolean
- `random_seed`: If provided, must be integer
- `expected_count`: If provided, must be non-negative integer
- `fix_cite_key`: Must be boolean
- File must exist and be readable

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "File not found" | RIS file path doesn't exist | Check file path is correct and file exists |
| "Invalid source_database" | Unknown database name | Use one of: proquest, scopus, web_of_science, mendeley, zotero, other |
| "Invalid limit" | Limit is not positive | Provide positive integer or omit limit |
| "Expected count mismatch" | Actual papers ≠ expected_count | Check file contains expected number of records |

### Normalization

RIS import includes automatic normalization for data quality:

1. **Titles**: Converted to title case, ampersands normalized
2. **Abstracts**: Whitespace collapsed, ampersands normalized
3. **Authors**: Parsed as "Last, First" format, normalized to title case
4. **Journals**: Title case applied, ampersands normalized
5. **Keywords**: Converted to lowercase, one per line
6. **Ampersands**: LaTeX `\&` and HTML `&amp;` forms converted to `&`
7. **Years**: Extracted as 4-digit integers where possible

### Cite Key Strategy

The step implements a 3-tier fallback strategy for generating unique cite keys:

1. **Accession Number** (Primary): If `AN` field present → `ris_an_{value}`
   - Most stable identifier from database exports
   - Example: `ris_an_20231234567`

2. **DOI** (Secondary): If `DO` field present → `ris_doi_{value}`
   - Used when accession number unavailable
   - Example: `ris_doi_10.1234/example`

3. **Auto-generated Hash** (Tertiary): MD5 hash of normalized title + first author
   - Used when neither AN nor DO available
   - Example: `ris_auto_a1b2c3d4e5f6`

### Examples

#### Basic ProQuest Import
```yaml
- step: Import ProQuest papers
  builtin.ris_import:
    file_path: "data/proquest.ris"
    source_database: "proquest"
```

#### Scopus with Limit
```yaml
- step: Import first 50 Scopus papers
  builtin.ris_import:
    file_path: "data/scopus_results.ris"
    source_database: "scopus"
    limit: 50
    expected_count: 342
```

#### Randomized Selection
```yaml
- step: Random sample from Web of Science
  builtin.ris_import:
    file_path: "data/wos_export.ris"
    source_database: "web_of_science"
    randomize: true
    random_seed: 2024
    limit: 100
    fix_cite_key: true
```

### Related Steps

- **Upstream**: None (usually the first step)
- **Downstream**: `checkpoint`, `deduplication`, `categorization`, `keyword_screening`
- **Alternative**: BibTeX import, CSV import, database query

### Notes

- **RIS is plain text**: No special encoding issues like LaTeX in BibTeX
- **Multi-value fields**: Authors and keywords are on separate lines in RIS format
- **Source database matters**: Different databases export slightly different RIS dialects
- **Accession numbers provide best stability**: For long-term tracking of paper origins
- **Large files process quickly**: RIS parsing is efficient even for 1000+ paper exports
- **Discovery method is KEYWORD_SEARCH**: Appropriate for database exports (not manual entry)

### Advanced: Collision Handling

When `fix_cite_key: true`, the step checks for cite_key collisions and resolves them:

```python
# Original cite_keys
paper1.cite_key = "ris_an_12345"
paper2.cite_key = "ris_an_12345"  # duplicate

# After collision fixing
paper1.cite_key = "ris_an_12345"
paper2.cite_key = "ris_an_12345_01"  # suffix added
```

This is useful when importing multiple RIS exports that might have overlapping records.

### See Also

- [BibTeX Import](bibtex_import.md) - For importing from BibTeX files
- [Base Step Documentation](base_step.md) - For understanding step architecture
- [Paper Model](../architecture/models.md) - For Paper and Discovery data structures
