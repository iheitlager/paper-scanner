# Paper Step

Create `Paper` objects from DOI specifications.

## Overview

The `builtin.paper` step enables batch creation of `Paper` objects with minimal required information. This is useful for initializing papers that will be enhanced with metadata and analysis in subsequent steps.

## Configuration

### Required Fields

- **`papers`**: Array of paper specifications. Each specification must include:
  - **`doi`**: Valid DOI string (required). Accepts multiple formats (raw stem, URL, doi: prefix).

### Optional Fields

- **`cite_key`**: Custom citation key. If omitted, auto-generated as `"doi_" + DOI.md5[:8]`
- **`paper_type`**: Paper type enum value (e.g., `"journal_article"`, `"conference_paper"`, `"book"`)
- **`study_type`**: Study type enum value (e.g., `"empirical_quantitative"`, `"empirical_qualitative"`, `"case_study"`) - reserved for future use

## Usage

### Minimal Example

Create papers with just DOI:

```yaml
- step: Create papers from DOI list
  builtin.paper:
    papers:
      - doi: "10.1000/182"
      - doi: "10.1000/183"
      - doi: "10.1000/184"
```

### With Custom Cite Key

```yaml
- step: Create papers with custom keys
  builtin.paper:
    papers:
      - doi: "10.1000/182"
        cite_key: "my_paper_1"
      - doi: "10.1000/183"
        cite_key: "my_paper_2"
```

### With Paper Type

```yaml
- step: Create typed papers
  builtin.paper:
    papers:
      - doi: "10.1080/10864415.2024.2332047"
        paper_type: "journal_article"
      - doi: "10.1145/3025453.3025761"
        paper_type: "conference_paper"
```

### Complete Example

```yaml
- step: Create papers with all metadata
  builtin.paper:
    papers:
      - doi: "10.1000/182"
      - doi: "10.1000/183"
        cite_key: "example_2023"
        paper_type: "journal_article"
        study_type: "empirical_quantitative"
      - doi: "https://doi.org/10.1000/184"
        paper_type: "conference_paper"
```

## DOI Format Support

The step accepts DOI in multiple formats and normalizes to stem format:

- Raw stem: `10.1000/182`
- HTTPS URL: `https://doi.org/10.1000/182`
- HTTP URL: `http://doi.org/10.1000/182`
- Prefix with colon: `doi:10.1000/182`
- Prefix with dot: `doi.10.1000/182`

All formats are normalized to `10.xxxx/yyyy` stem format for consistent storage.

## Cite Key Generation

If `cite_key` is not provided, it is automatically generated as:

```
"doi_" + MD5(normalized_doi)[:8]
```

This ensures:
- Deterministic generation (same DOI always produces same key)
- Uniqueness based on DOI content
- Safe for use as BibTeX citation keys

Example:
- DOI `10.1000/182` → cite_key `doi_91d574c9`

## Paper Type Enum

Valid `paper_type` values:

- `journal_article`
- `conference_paper`
- `book`
- `book_chapter`
- `thesis`
- `technical_report`
- `working_paper`
- `preprint`
- `patent`
- `other`

## Study Type Enum

Valid `study_type` values (for future categorization enhancement):

- `empirical_quantitative`
- `empirical_qualitative`
- `empirical_mixed`
- `case_study`
- `theoretical`
- `other`

## Output

The step returns created papers with:
- Auto-generated `id` (UUID)
- Provided or generated `cite_key`
- Normalized `doi`
- Optional `paper_type` if provided
- Discovery method set to `MANUAL`
- Empty `screening` object (for later enhancement)

## Error Handling

- **Invalid DOI format**: Paper creation fails, error recorded
- **Unknown enum value**: Configuration validation fails at parse time
- **Missing DOI**: Configuration validation fails at parse time

When errors occur during execution:
- Valid papers are still created and persisted
- Result status is `"partial"` or `"error"` depending on severity
- Error list included in result

## Integration with Other Steps

This step creates "skeleton" `Paper` objects meant for enhancement by downstream steps:

1. **`builtin.retrieve_metadata`**: Fetch title, abstract, authors from Crossref
2. **`builtin.categorization`**: Enhance with paper type, study type, quality tier
3. **`builtin.keyword_screening`**: Screen papers by keywords
4. **`builtin.semantic_screening`**: Screen papers by semantic similarity
5. **`builtin.report`**: Generate reports and statistics

## Examples

### Workflow 1: Simple Paper Import

```yaml
steps:
  - step: Create papers from DOI list
    builtin.paper:
      papers:
        - doi: "10.1000/182"
        - doi: "10.1000/183"

  - step: Retrieve metadata from Crossref
    builtin.retrieve_metadata:
      source: crossref
      
  - step: Export results
    builtin.export:
      format: bibtex
      output_path: output.bib
```

### Workflow 2: Typed Papers with Study Type

```yaml
steps:
  - step: Create empirical studies
    builtin.paper:
      papers:
        - doi: "10.1000/182"
          paper_type: "journal_article"
          study_type: "empirical_quantitative"
        - doi: "10.1000/183"
          paper_type: "journal_article"
          study_type: "empirical_qualitative"

  - step: Retrieve metadata
    builtin.retrieve_metadata:
      source: crossref
```

## See Also

- [Patch Step](patch.md) - Modify paper fields after creation
- [Retrieve Metadata Step](retrieve_metadata.md) - Fetch paper metadata
- [Categorization Step](categorization.md) - Categorize papers
- [Paper Model](../../src/paper_scanner/core/models.py) - Paper data structure
