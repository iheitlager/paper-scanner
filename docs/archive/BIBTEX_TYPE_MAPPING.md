# BibTeX Paper Type Mapping

## Overview

The paper scanner now supports automatic evaluation and mapping of BibTeX entry types to standardized `paper_type` values. This feature:

- **Populates the `paper_type` field** on all imported papers from BibTeX files
- **Uses configurable YAML mappings** for BibTeX entry type → paper type conversion
- **Supports source-specific overrides** (Scopus, IEEE, Web of Science, etc.)
- **Provides confidence scores** for each type mapping
- **Allows custom type mappings** via configuration

## Configuration

### Default Configuration

The default BibTeX type mapping configuration is located at:
```
etc/bibtex_type_mapping.yaml
```

### Type Mappings

The configuration defines mappings from BibTeX entry types to standardized paper types:

```yaml
type_mappings:
  article:
    paper_type: "article"
    description: "Journal article"
    confidence: 0.95
  
  inproceedings:
    paper_type: "conference_paper"
    description: "Conference paper / proceedings"
    confidence: 0.95
  
  book:
    paper_type: "book"
    description: "Full book"
    confidence: 0.95
  
  # ... and many more
```

### Supported Paper Types

The following standard paper types are used (from `core/enum.py`):

- `article` - Journal articles
- `conference_paper` - Conference proceedings
- `book` - Full books
- `book_chapter` - Chapters in edited books
- `thesis` - PhD or Master's theses
- `technical_report` - Technical reports and standards
- `working_paper` - Working papers and unpublished work
- `preprint` - Preprints (e.g., arXiv)
- `patent` - Patents
- `other` - Miscellaneous/unknown types

### Source-Specific Overrides

The configuration includes source-specific refinements for different databases:

```yaml
source_overrides:
  scopus:
    article_type_field: "type"
    type_value_mappings:
      "Article": "article"
      "Conference Paper": "conference_paper"
      # ...
  
  ieee:
    article_type_field: "type"
    type_value_mappings:
      "Journals & Magazines": "article"
      "Conferences": "conference_paper"
      # ...
```

### Custom Mappings

You can define custom mappings in the YAML:

```yaml
custom_mappings:
  mytype:
    paper_type: "article"
    description: "Custom type mapping"
    confidence: 0.8
```

## Usage

### Basic Usage - Automatic Type Evaluation

When importing BibTeX files, paper types are automatically evaluated:

```python
from src.paper_scanner.io.bibtex import bibtex_file_to_papers

papers = bibtex_file_to_papers(
    "path/to/file.bib",
    source_type="scopus"  # Optional: helps with source-specific mappings
)

# Papers now have paper_type populated
for paper in papers:
    print(f"{paper.title} -> {paper.paper_type}")
```

### Using Custom Configuration

Specify a custom configuration file:

```python
papers = bibtex_file_to_papers(
    "path/to/file.bib",
    source_type="ieee",
    type_mapping_config=load_type_mapping_config("path/to/custom_config.yaml")
)
```

### In Import Steps

The bibtex_import step automatically loads and uses the type mapping configuration:

```yaml
# In your pipeline config
steps:
  - step: bibtex_import
    config:
      batch_id: my_import
      type_mapping_config_path: /path/to/bibtex_type_mapping.yaml
      imports:
        - name: "Scopus Import"
          file_path: data/scopus.bib
          source_type: scopus
```

### Programmatic Access

Load and examine the configuration:

```python
from src.paper_scanner.io.bibtex import load_type_mapping_config, evaluate_paper_type

# Load configuration
config = load_type_mapping_config()

# Evaluate paper type for a BibTeX entry
entry = {'ENTRYTYPE': 'article', 'ID': 'key123'}
paper_type, confidence = evaluate_paper_type(entry, source_type='scopus', type_mapping_config=config)

print(f"Paper Type: {paper_type} (confidence: {confidence})")
```

## Implementation Details

### Type Evaluation Strategy

The `evaluate_paper_type()` function uses a multi-strategy approach:

1. **Source-specific type field** - Check for source-specific `type` field with custom mappings
2. **Standard BibTeX entry type** - Use the standard BibTeX `ENTRYTYPE` mapping
3. **Custom mappings** - Check user-defined custom mappings
4. **Fallback heuristics** - Try to infer from common field names
5. **Last resort** - Case-insensitive match on entry type

### Confidence Scores

Each mapping includes a confidence score (0.0-1.0) indicating how reliable the mapping is:

- **0.95** - High confidence (e.g., @article → article)
- **0.90** - Good confidence (e.g., @book_chapter → book_chapter)
- **0.85** - Moderate confidence (e.g., source-specific mapping)
- **0.75-0.80** - Lower confidence (e.g., working papers)
- **0.5-0.6** - Low confidence (fallback heuristics)

## Testing

Run the test suite to verify type mapping functionality:

```bash
# Test configuration loading
pytest tests/unit/test_bibtex_paper_type.py::TestTypeMapping -xvs

# Test type evaluation
pytest tests/unit/test_bibtex_paper_type.py::TestPaperTypeEvaluation -xvs

# Test BibTeX file imports
pytest tests/unit/test_bibtex_paper_type.py::TestBibTeXFileImport -xvs

# Test with real data
pytest tests/unit/test_bibtex_paper_type.py::TestTypeEvaluationWithRealData -xvs
```

## Examples

### Example 1: Import Scopus Papers

```python
papers = bibtex_file_to_papers(
    "data/scopus.bib",
    source_type="scopus"
)

# Results:
# - 18 articles identified as 'article' type
# - 1 conference paper identified as 'conference_paper'
```

### Example 2: Import IEEE Papers

```python
papers = bibtex_file_to_papers(
    "data/ieee.bib",
    source_type="ieee"
)

# Results:
# - 18 conference papers identified as 'conference_paper'
# - 1 article identified as 'article'
# - 1 book chapter identified as 'book_chapter'
```

### Example 3: Import with Custom Config

Create a custom YAML configuration:

```yaml
# custom_mapping.yaml
type_mappings:
  article:
    paper_type: "article"
    confidence: 0.95
  
  inproceedings:
    paper_type: "conference_paper"
    confidence: 0.95

custom_mappings:
  internal_tech_report:
    paper_type: "technical_report"
    confidence: 0.9
```

Then use it:

```python
papers = bibtex_file_to_papers(
    "data/file.bib",
    type_mapping_config=load_type_mapping_config("custom_mapping.yaml")
)
```

## Future Enhancements

Potential improvements to the type mapping system:

1. **ML-based type prediction** - Use abstract and title to improve type prediction
2. **Cross-reference validation** - Validate types against external APIs (CrossRef, etc.)
3. **User feedback loop** - Allow users to correct and improve mappings
4. **Source detection** - Automatically detect source type from BibTeX content
5. **Type consolidation** - Merge similar types (e.g., `working_paper` and `preprint`)

## Troubleshooting

### Papers not getting paper_type

1. Check that the BibTeX file has valid `ENTRYTYPE` fields
2. Verify the configuration file is being loaded: check logs for configuration loading messages
3. Check that the `ENTRYTYPE` matches a known mapping in the configuration
4. Try adding a custom mapping for your type

### Wrong paper type assigned

1. Check the source database type - source-specific overrides may help
2. Review the BibTeX entry for a `type` field that might contain better information
3. Add a custom mapping for your specific case
4. Adjust confidence scores if needed

### Performance issues

1. Type mapping configuration is cached after first load
2. Call `load_type_mapping_config()` once and reuse the result
3. Large batches of files are processed sequentially to avoid memory issues
