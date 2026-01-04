# Run Template

### Title
**Run Template** - Executes a reusable sequence of steps defined as a template

### Description

The Run Template step allows you to reference a predefined template of steps and execute all steps in that template inline. Templates are reusable sequences of steps defined in the `templates` section of a YAML definition file. Use this feature to avoid repeating common step sequences and to create modular, maintainable pipeline definitions.

Templates enable DRY (Don't Repeat Yourself) principles in pipeline configuration and make complex workflows more readable and manageable.

### Features

- ✅ **Reusable sequences**: Define common step sequences once, use many times
- ✅ **Modular pipelines**: Break complex workflows into reusable components
- ✅ **Template nesting**: Templates can reference other templates
- ✅ **Validation**: Validates template names at configuration time
- ✅ **Clear organization**: Group related steps logically
- ✅ **Readable pipelines**: Self-documenting step sequences

### Configuration

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `template` | `string` | Yes | - | Name of the template to execute |

#### YAML Definition

```yaml
templates:
  - name: "basic_screening"
    steps:
      - step: Remove duplicates
        builtin.deduplication:
          method: "exact"
      
      - step: Keyword filtering
        builtin.keyword_screening:
          keywords: ["machine learning"]
      
      - step: Export results
        builtin.export:
          format: "jsonl"
          output_file: "results.jsonl"

steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch1"
      imports:
        - name: "Scopus"
          file_path: "data/scopus.bib"
  
  - step: Apply screening template
    builtin.run-template:
      template: "basic_screening"
```

### Input/Output

#### Input
- **Format**: Current pipeline state (papers in database)
- **Source**: Prior steps in pipeline
- **Requirements**: Template must be defined in YAML

#### Output
- **Format**: Same as individual steps within template
- **Effects**: Depends on steps in template
- **Dependencies**: Template steps executed in order

### Validation

The step validates:
- `template` parameter is required
- Template name is non-empty string
- Named template exists in YAML definition
- All steps in template are valid

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Missing required 'template' parameter" | No template specified | Add template name to config |
| "Template name cannot be empty" | Empty string for template | Use non-empty template name |
| "Template not found" | Template name doesn't exist | Define template in templates section |
| "Recursive template depth exceeded" | Infinite template recursion | Remove circular references |

### Template Features

#### Template Definition

Templates are defined in the root `templates` section:

```yaml
templates:
  - name: "template_name"
    steps:
      - step: Description
        builtin.step_name:
          param: value
```

#### Using Templates

```yaml
steps:
  - step: Execute template
    builtin.run-template:
      template: "template_name"
```

### Examples

#### Basic Example - Simple Template
```yaml
templates:
  - name: "dedup_and_export"
    steps:
      - step: Remove duplicates
        builtin.deduplication:
          method: "exact"
      
      - step: Export results
        builtin.export:
          format: "jsonl"
          output_file: "dedup_results.jsonl"

steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch1"
      imports:
        - name: "Scopus"
          file_path: "scopus.bib"
  
  - step: Apply deduplication and export
    builtin.run-template:
      template: "dedup_and_export"
```

#### Advanced Example - Comprehensive Workflow Template
```yaml
templates:
  - name: "comprehensive_screening"
    steps:
      - step: Message - Starting comprehensive screening
        builtin.echo:
          message: "Starting comprehensive screening phase..."
      
      - step: Exact deduplication
        builtin.deduplication:
          method: "exact"
      
      - step: Keyword screening
        builtin.keyword_screening:
          keywords: ["machine learning", "neural networks"]
      
      - step: Journal screening
        builtin.journal_screening:
          journals_file: "high_quality_journals.yml"
      
      - step: Generate screening report
        builtin.report:
          screening: true
      
      - step: Export final results
        builtin.export:
          format: "jsonl"
          output_file: "final_results.jsonl"
          include_status: "included"

  - name: "quick_export"
    steps:
      - step: Export all papers
        builtin.export:
          format: "jsonl"
          output_file: "all_papers.jsonl"
          include_status: "all"
      
      - step: Export for reference managers
        builtin.export:
          format: "bibtex"
          output_file: "papers.bib"

steps:
  - step: Import from Scopus
    builtin.bibtex_import:
      batch_id: "scopus_2024"
      imports:
        - name: "Scopus"
          file_path: "data/scopus.bib"
  
  - step: Import from CrossRef
    builtin.retrieve_metadata:
      batch_id: "crossref_2024"
  
  - step: Run comprehensive screening
    builtin.run-template:
      template: "comprehensive_screening"
  
  - step: Export in multiple formats
    builtin.run-template:
      template: "quick_export"
```

#### Nested Templates Example
```yaml
templates:
  - name: "basic_dedup"
    steps:
      - step: Exact deduplication
        builtin.deduplication:
          method: "exact"

  - name: "basic_screening"
    steps:
      - step: Deduplication
        builtin.run-template:
          template: "basic_dedup"
      
      - step: Keyword screening
        builtin.keyword_screening:
          keywords: ["AI", "machine learning"]

  - name: "full_pipeline"
    steps:
      - step: Basic screening
        builtin.run-template:
          template: "basic_screening"
      
      - step: Export results
        builtin.export:
          format: "jsonl"
          output_file: "final.jsonl"

steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch1"
      imports:
        - name: "Scopus"
          file_path: "scopus.bib"
  
  - step: Execute full pipeline template
    builtin.run-template:
      template: "full_pipeline"
```

### Best Practices

- **Naming**: Use descriptive template names (`screening_and_export` vs `template1`)
- **Reusability**: Create templates for common sequences
- **Organization**: Group related steps into logical templates
- **Documentation**: Use `echo` steps within templates for clarity
- **Modularity**: Keep templates focused on specific purposes
- **Nesting**: Use judiciously; avoid excessive template depth

### Template Organization

Example project structure:

```
definition.yml (main pipeline)
├── templates:
│   ├── screening templates (dedup, keyword, journal)
│   ├── export templates (multiple formats)
│   └── report templates (summary, detailed)
└── steps:
    ├── Import
    ├── Execute templates
    └── Final export
```

### See Also

- [Deduplication](deduplication.md) - Remove duplicate papers
- [Keyword Screening](keyword_screening.md) - Filter by keywords
- [Export](export.md) - Save papers to files
- [Echo](echo.md) - Add messages for documentation
