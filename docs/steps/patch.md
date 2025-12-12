# Patch Step

Updates existing paper records by DOI with field values from an external file or inline configuration. Supports both replacing existing field values and appending to list-based fields like keywords.

## Features

- **DOI-based matching**: Locate papers by DOI and update them
- **External or inline patches**: Load from YAML/JSON file or specify patches directly in pipeline config
- **Replace or append**: Replace field values or append to list-based fields
- **Fail on missing DOI**: Automatically fails if a DOI has no matching papers in the database
- **Multiple patches**: Apply many patch operations in a single step
- **Multiple fields per patch**: Update multiple fields in a single paper
- **Detailed error reporting**: See which patches succeeded and which failed

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | No | Path to external patch file (YAML or JSON). Mutually exclusive with `patches`. |
| `patches` | array | No | Array of inline patch objects. Mutually exclusive with `file`. |

Either `file` or `patches` must be specified.

### Patch Object Structure

Each patch object contains:

```yaml
doi: "10.1234/example.doi"          # Required: DOI to match
replace_fields:                      # Optional: fields to replace
  abstract: "new abstract text"
  title: "new title"
append_fields:                       # Optional: fields to append
  keywords: ["new", "keywords"]      # For list fields
  abstract: " more text"              # For string fields
```

## Examples

### YAML with External File

```yaml
steps:
  - name: patch
    file: "etc/patches.yaml"
```

**File: `etc/patches.yaml`**

```yaml
patches:
  - doi: "10.1080/10864415.2024.2332047"
    replace_fields:
      abstract: "blabla"
      title: "New Title"
    append_fields:
      keywords: ["machine-learning", "nlp"]
  
  - doi: "10.1234/another.doi"
    replace_fields:
      journal: "Updated Journal Name"
```

### YAML with Inline Patches

```yaml
steps:
  - name: patch
    patches:
      - doi: "10.1080/10864415.2024.2332047"
        replace_fields:
          abstract: "blabla"
      
      - doi: "10.1234/different.doi"
        replace_fields:
          title: "Updated Title"
        append_fields:
          keywords: ["new-keyword"]
```

### JSON Format

```json
{
  "patches": [
    {
      "doi": "10.1080/10864415.2024.2332047",
      "replace_fields": {
        "abstract": "blabla"
      },
      "append_fields": {
        "keywords": ["keyword1", "keyword2"]
      }
    }
  ]
}
```

## Field Types

### Replace Operations

Replace operations work on any field:
- String fields: `abstract`, `title`, `journal`, `booktitle`, etc.
- Numeric fields: `year`, `volume`, etc.
- Optional fields: `doi`, `arxiv_id`, `pmid`, etc.

### Append Operations

Append operations work on:
- **List fields** (keywords): New items are added to the list
  ```yaml
  keywords: ["new-keyword"]  # Extends existing keywords list
  ```
- **String fields** (abstract, title): Text is concatenated
  ```yaml
  abstract: " additional text"  # Appends to existing abstract
  ```

## Validation Rules

- Both `doi` values must reference papers in the database; the step fails if a DOI has no matching papers
- `replace_fields` and `append_fields` must be dictionaries
- Field names must exist on the Paper model
- Append operations only work on strings and lists

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No papers match DOI | Patch fails, error reported |
| Invalid field name | Patch fails with field error |
| Missing `doi` in patch | Patch skipped with warning |
| File not found | Step fails with error |
| Invalid YAML/JSON | Step fails with parse error |
| Invalid file format | Step fails, supports .yaml, .yml, .json only |

## Input/Output

### Input

Papers database with existing records

### Output

```python
{
    "status": "success" | "partial" | "error",
    "patches_found": 5,          # Total patches in config/file
    "patches_applied": 5,        # Successfully applied patches
    "patches_failed": 0,         # Failed patches
    "failed_details": [          # Details of failures (if any)
        (patch_index, error_message),
        ...
    ],
    "papers_count": 150          # Total papers in database after patch
}
```

## Related Steps

- **input**: Import new papers from JSON Lines
- **summarize**: Generate abstracts for papers
- **export**: Export patched papers to BibTeX or JSON

## Implementation Notes

- Uses DOI-based matching against primary papers only (not duplicates)
- Patches are applied sequentially in order
- Each patch is independent; if one fails, others still process
- Database updates are atomic per paper
- Supports path expansion via `~` in file paths
