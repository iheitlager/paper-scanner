# CLI Validate Command

### Title
**Validate** - Validates definition YAML files and reports configuration errors

### Description

The validate command provides pre-flight configuration checking before running your paper screening pipeline. It parses the definition YAML file, validates all step configurations, and reports any errors or misconfigurations. Use this to catch typos, invalid parameters, or missing required fields before spending time waiting for a full pipeline run.

The validate command checks configuration syntax, parameter types, required fields, and step compatibility without modifying any data.

### Features

- ✅ **YAML syntax validation**: Catches malformed YAML files
- ✅ **Step configuration validation**: Validates each step's parameters
- ✅ **Type checking**: Ensures parameters are correct data types
- ✅ **Required field validation**: Verifies all required parameters are present
- ✅ **Value range checking**: Validates parameters are within acceptable ranges
- ✅ **Detailed error messages**: Clear explanations of what's wrong and how to fix it
- ✅ **Early error detection**: Run before pipeline to save time

### Usage

```bash
python -m paper_scanner.cli validate <definition_file>
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `definition_file` | `string` | Yes | Path to definition YAML file to validate |

### Examples

#### Basic Usage
```bash
python -m paper_scanner.cli validate definition.yml
```

Output on success:
```
✓ Definition file is valid
  9 steps validated successfully
  No configuration errors found
```

#### With Errors
```bash
python -m paper_scanner.cli validate bad_definition.yml
```

Output with errors:
```
✗ Definition file validation failed

Step "keyword_screening" (builtin.keyword_screening):
  ✗ Invalid threshold value: 150 (must be 0-100)
  ✗ Missing required parameter: exclusion_keywords

Fix these issues before running the pipeline.
```

#### File Not Found
```bash
python -m paper_scanner.cli validate nonexistent.yml
```

Output:
```
✗ Definition file not found: nonexistent.yml
```

### Validation Rules

The validate command checks:

#### YAML Structure
- File is valid YAML format
- Top-level structure contains required sections
- Steps are in correct list format

#### Step Configuration
- Step type is recognized (builtin or custom)
- All required parameters are present
- All parameters are correct data type
- Numeric parameters are in valid ranges
- String parameters are non-empty (where required)
- List parameters are properly formatted

#### Specific Step Validations

**bibtex_import**
- `batch_id`: non-empty string
- `imports`: list with ≥1 entry
- Each import has `name`, `file_path`, `source_type`
- `source_type` in: scopus, ieee_xplore, web_of_science, other

**deduplication**
- `method`: one of exact_doi, fuzzy, all
- `title_author_threshold`: 0-100
- `title_threshold`: 0-100
- `remove_duplicates`: boolean

**categorization**
- `exclude_types`: boolean
- `exclude_reviews`: boolean

**keyword_screening**
- `inclusion_keywords`: list of strings
- `exclusion_keywords`: list of strings
- `inclusion_threshold`: 0-100
- `exclusion_threshold`: 0-100

**semantic_screening**
- `model`: non-empty string
- `thresholds.auto_include`: 0-1
- `thresholds.manual_review`: 0-1
- `thresholds.auto_exclude`: 0-1

**checkpoint**
- `name`: non-empty string

**echo**
- `message`: string (optional)

**halt**
- `min_papers`: positive integer (optional)
- `message`: string (optional)

**summarize**
- `screening`: boolean (optional)

**export**
- `format`: one of jsonl, bibtex, csv
- `output_file`: non-empty string
- `include_status`: one of included, excluded, all
- `exclude_duplicates`: boolean

### Error Messages

#### Common Errors and Solutions

| Error | Solution |
|-------|----------|
| `YAML parse error: mapping values are not allowed here` | Check colons and indentation in YAML |
| `Unknown step type: my_step` | Use correct built-in step name or check capitalization |
| `Missing required parameter: batch_id` | Add required parameter to step configuration |
| `Invalid format: "xml"` (expected: jsonl, bibtex, csv) | Use valid format: jsonl, bibtex, or csv |
| `Invalid threshold: 150 (must be 0-100)` | Use value between 0 and 100 |
| `source_type "Scopus" not recognized` | Use lowercase: scopus (not Scopus or SCOPUS) |

### Examples

#### Valid Definition File
```yaml
project:
  name: "Digital Transformation Study"
  research_question: "How is digital transformation impacting supply chains?"

pipeline:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch1"
      imports:
        - name: "Scopus"
          file_path: "data/scopus.bib"
          source_type: "scopus"

  - step: Remove duplicates
    builtin.deduplication:
      method: "all"

  - step: Screen by keywords
    builtin.keyword_screening:
      inclusion_keywords: ["digital transformation"]
      exclusion_keywords: ["game"]

  - step: Export results
    builtin.export:
      format: "jsonl"
      output_file: "results.jsonl"
```

To validate:
```bash
python -m paper_scanner.cli validate definition.yml
```

Output:
```
✓ Definition file is valid
  4 steps validated successfully
  No configuration errors found
```

#### Invalid Definition File (with errors)
```yaml
project:
  name: "Bad Study"

pipeline:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch1"
      # Missing required 'imports' list

  - step: Export results
    builtin.export:
      format: "xml"  # Invalid format
      output_file: ""  # Empty file path
```

To validate:
```bash
python -m paper_scanner.cli validate bad_definition.yml
```

Output:
```
✗ Definition file validation failed

Step "Import papers" (builtin.bibtex_import):
  ✗ Missing required parameter: imports

Step "Export results" (builtin.export):
  ✗ Invalid format: "xml" (expected: jsonl, bibtex, csv)
  ✗ output_file cannot be empty

Fix these issues before running the pipeline.
```

### Related Commands

- `run`: Execute pipeline after successful validation
- `run --validate`: Validate before running (automatic pre-flight check)

### Best Practices

1. **Always validate before running** to catch configuration errors early
2. **Use descriptive step names** for clarity in error messages
3. **Check error messages carefully** for exact issues and solutions
4. **Validate after editing** to ensure changes are correct
5. **Use as CI/CD check** to catch broken configurations in version control

### Notes

- **Validate is read-only**: Does not modify database or files
- **Pre-flight check**: `run` command automatically validates before executing
- **Detailed errors**: Error messages include the exact issue and expected values
- **Fast execution**: Validation completes in seconds even for complex pipelines
