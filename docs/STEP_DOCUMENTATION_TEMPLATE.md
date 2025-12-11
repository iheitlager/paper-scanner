# Step Documentation Template

Use this template to document each processing step in the paper-scanner pipeline.

---

## [Step Name]

### Title
**[Step Name]** - [One-line description of what the step does]

Example: **BibTeX Import** - Sequentially imports BibTeX files and adds papers to the database

### Description
[2-3 paragraph description of the step's purpose, how it works, and what outputs it produces]

Include:
- What problem the step solves
- When in the pipeline it runs
- What data it consumes and produces
- Any dependencies or prerequisites
- Links to related steps

Example:
> The BibTeX Import step loads bibliographic data from BibTeX files into the paper scanner database. It supports imports from multiple sources (Scopus, IEEE Xplore, Web of Science) and tracks the source database for each import. Each paper is assigned a unique citation key and discovery metadata including the import batch ID and source type.

### Features

List key features and capabilities:

- ✅ **Feature 1**: Description of feature
- ✅ **Feature 2**: Description of feature
- ✅ **Feature 3**: Description of feature
- ✅ **Feature 4**: Description of feature

Example for BibTeX Import:
- ✅ **Multi-source imports**: Supports Scopus, IEEE Xplore, Web of Science, and other BibTeX sources
- ✅ **Batch tracking**: Assigns batch ID to all papers from same import run
- ✅ **Entry type mapping**: Maps BibTeX entry types to standardized paper types
- ✅ **Progress reporting**: Shows inline progress for large import batches
- ✅ **Error handling**: Gracefully handles malformed BibTeX entries

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `param_1` | `string` | Yes | - | Description of parameter 1 |
| `param_2` | `integer` | No | `100` | Description of parameter 2 |
| `param_3` | `list` | No | `[]` | Description of parameter 3 |

Example for BibTeX Import:
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
- step: [Step Description]
  builtin.[step_name]:
    [parameter_1]: [value]
    [parameter_2]: [value]
    [parameter_3]:
      - [item_1]
      - [item_2]
```

**Example for BibTeX Import:**
```yaml
- step: Import sample BibTeX files from different sources
  builtin.bibtex_import:
    batch_id: "import_scopus_2024"
    imports:
      - name: "Scopus - Digital Innovation"
        file_path: "data/scopus_2024.bib"
        source_type: "scopus"
        expected_count: 250
      
      - name: "IEEE Xplore - IoT"
        file_path: "data/ieee_iot_2024.bib"
        source_type: "ieee_xplore"
        expected_count: 180
      
      - name: "Web of Science - Transformation"
        file_path: "data/wos_transformation_2024.bib"
        source_type: "web_of_science"
        expected_count: 300
```

### Input/Output

#### Input
- **Format**: [Describe input data format]
- **Source**: [Where input comes from]
- **Requirements**: [Any prerequisites or dependencies]

Example for BibTeX Import:
- **Format**: BibTeX files (.bib)
- **Source**: External files specified in configuration
- **Requirements**: Files must exist and be valid BibTeX format

#### Output
- **Format**: [Describe output data format and location]
- **Database**: [Which models/tables are updated]
- **Metrics**: [What statistics/metrics are generated]

Example for BibTeX Import:
- **Format**: Papers stored in database
- **Database**: `Paper` model with `Discovery` metadata
- **Metrics**: Papers imported, batch ID, source type, import timestamp

### Validation

The step includes validation for:
- [Validation rule 1]: Description
- [Validation rule 2]: Description
- [Validation rule 3]: Description

Example for BibTeX Import:
- `batch_id`: Must be a non-empty string
- `imports`: Must be a list with at least one entry
- Each import entry must have `name`, `file_path`, and `source_type`
- `source_type` must be one of: `scopus`, `ieee_xplore`, `web_of_science`, `other`
- `expected_count` if provided must be a positive integer

### Error Handling

Common errors and how to resolve them:

| Error | Cause | Solution |
|-------|-------|----------|
| Error 1 | What causes this | How to fix it |
| Error 2 | What causes this | How to fix it |

Example for BibTeX Import:
| Error | Cause | Solution |
|-------|-------|----------|
| "File not found" | BibTeX file path doesn't exist | Check file path is correct and file exists |
| "Invalid BibTeX" | File contains malformed entries | Run through BibTeX validator, fix syntax errors |
| "Unknown source_type" | Invalid source_type value | Use one of: scopus, ieee_xplore, web_of_science, other |

### Examples

#### Basic Example
[Simple, minimal example]

#### Advanced Example
[Complex example with many features]

Example for BibTeX Import:
```yaml
# Basic: Single file import
- step: Import papers
  builtin.bibtex_import:
    batch_id: "batch_001"
    imports:
      - name: "Papers"
        file_path: "papers.bib"
        source_type: "scopus"

# Advanced: Multiple sources with validation
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

- **Upstream**: [Steps that should run before this one]
- **Downstream**: [Steps that typically run after this one]
- **Alternative**: [Other steps that could be used instead]

Example for BibTeX Import:
- **Upstream**: None (usually the first step)
- **Downstream**: `deduplication`, `categorization`, `keyword_screening`
- **Alternative**: Database query import, CSV import

### Notes

[Any additional context, tips, or important information]

- Tips for optimal configuration
- Performance considerations
- Known limitations
- Future enhancements

Example for BibTeX Import:
- **Batch IDs should be unique** to track imports separately in the database
- **Large files (>10MB)** may take several minutes to process
- **Progress is reported every 100 papers** for large imports
- **Source type affects how metadata is extracted** from the BibTeX entry
