# Pythonic Definition API - Examples

This directory contains comprehensive examples of using the paper-scanner Pythonic Definition API to build research review pipelines entirely in Python, without YAML.

## Overview

The Pythonic Definition API provides a fluent, type-safe alternative to YAML-based pipeline definitions. It combines the clarity of Python with full IDE support, autocomplete, and compile-time error detection.

## Quick Start

### Installation

```bash
# The definition API is part of paper-scanner
from paper_scanner.definition import Definition, BibtexSource
```

### Minimal Example

```python
from paper_scanner.definition import Definition, BibtexSource

# Create and execute a pipeline
definition = (
    Definition("My Project")
    .bibtex_import(
        batch_id="batch_1",
        imports=[BibtexSource.scopus("Scopus", "data.bib", 100)]
    )
    .export(format="jsonl", output_path="~/output.jsonl")
    .run()
)
```

## Examples

### [01_simple_import.py](01_simple_import.py)

**Goal:** Demonstrate the simplest use case - importing papers and exporting to JSONL.

**Key Features:**
- Single source import from Scopus
- Direct export to JSONL format
- Minimal configuration

**Use Case:** Quick paper import for small-scale reviews.

```bash
python examples/01_simple_import.py
```

### [02_full_pipeline.py](02_full_pipeline.py)

**Goal:** Show a complete research review pipeline with all major processing steps.

**Key Features:**
- Multi-source import (Scopus, IEEE, Web of Science)
- Deduplication with multiple methods (DOI exact, fuzzy title/author)
- Categorization and quality screening
- Checkpoints for resuming interrupted runs
- Summary statistics
- Multiple export formats (JSONL + BibTeX)

**Use Case:** Comprehensive systematic literature reviews.

```bash
python examples/02_full_pipeline.py --verbose
```

### [03_conditional_pipeline.py](03_conditional_pipeline.py)

**Goal:** Demonstrate conditional step inclusion based on runtime parameters.

**Key Features:**
- Factory function for pipeline creation
- Optional deduplication and categorization
- Optional keyword screening with custom keywords
- Runtime configuration of pipeline structure
- Three example scenarios:
  - Basic import-only
  - Comprehensive with all features
  - Specialized with keyword screening

**Use Case:** Flexible pipelines that adapt to different research scenarios.

```bash
python examples/03_conditional_pipeline.py
```

**Key Code Pattern:**
```python
def build_custom_pipeline(
    project_name: str,
    sources: List[BibtexSource],
    *,
    deduplicate: bool = True,
    categorize: bool = True,
    # ... more options
) -> Definition:
    definition = Definition(project_name)
    
    definition.bibtex_import(batch_id=..., imports=sources)
    
    if deduplicate:
        definition.deduplication(enabled=True, methods=[...])
    
    if categorize:
        definition.categorization(enabled=True)
    
    # ... more steps
    return definition
```

### [04_batch_processing.py](04_batch_processing.py)

**Goal:** Show how to create and manage multiple pipelines for batch processing.

**Key Features:**
- `ResearchConfig` dataclass for configuration
- Batch pipeline generation from configurations
- Processing multiple years of data
- Template-based pipeline creation
- Sequential and parallel execution patterns

**Use Case:** Processing research data across multiple time periods or topics.

```bash
python examples/04_batch_processing.py
```

**Key Code Pattern:**
```python
# Define multiple configurations
reviews = [
    ResearchConfig(year=2020, topic="innovation", sources=[...]),
    ResearchConfig(year=2021, topic="innovation", sources=[...]),
]

# Generate pipelines
pipelines = create_batch_pipelines(reviews)

# Execute in parallel
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(pipeline.run): year
        for year, pipeline in pipelines.items()
    }
```

## API Reference

### Definition Class

The main fluent builder class for creating pipelines.

```python
# Creation
definition = Definition(
    name="My Project",
    description="...",
    researcher="...",
    institution="..."
)

# Chaining steps
definition.bibtex_import(...).deduplication(...).export(...)

# Execution
results = definition.run(verbose=True, dry_run=False)

# Conversion
yaml_dict = definition.to_dict()
definition.to_yaml("pipeline.yml")
```

### Step Methods

All steps return `self` for method chaining.

```python
# Import steps
.bibtex_import(batch_id, imports)
.echo(message=None)

# Processing steps
.deduplication(enabled=True, methods=None)
.categorization(enabled=True)
.keyword_screening(enabled=True, keywords=None)
.semantic_screening(enabled=True)

# Management steps
.checkpoint(label=None)
.summarize(summary=True, tabulate=None)
.export(format, output_path, exclude_none=True, duplicates=False, overwrite=False)
.halt(message="")
```

### Configuration Classes

Type-safe configuration objects for each step type.

```python
from paper_scanner.definition import (
    BibtexSource,  # BibTeX import sources
    BibtexImportConfig,
    DeduplicationMethod,
    DeduplicationConfig,
    CategorizationConfig,
    ExportConfig,
    # ... more
)

# Create sources
source = BibtexSource.scopus("Name", "file.bib", 100)

# Configure steps
dedup_config = DeduplicationConfig(
    enabled=True,
    methods=[
        DeduplicationMethod(method="doi_exact", priority=1),
        DeduplicationMethod(method="title_fuzzy", priority=2, threshold=0.95),
    ]
)
```

## Common Patterns

### Pattern 1: Reusable Pipeline Template

```python
def create_my_review_template(project_name: str, sources: List[BibtexSource]):
    return (
        Definition(project_name)
        .bibtex_import(batch_id=f"batch_{project_name}", imports=sources)
        .deduplication(enabled=True, methods=[...])
        .categorization(enabled=True)
        .export(format="jsonl", output_path=f"~/output_{project_name}.jsonl")
    )

# Use template
pipeline = create_my_review_template("review_2024", my_sources)
```

### Pattern 2: Conditional Steps Based on Data

```python
definition = Definition("Dynamic Pipeline")
definition.bibtex_import(batch_id="batch", imports=sources)

# Add steps based on conditions
if len(sources) > 5:  # Many sources
    definition.deduplication(enabled=True)

if "keyword_file" in config:  # Keyword file exists
    definition.keyword_screening(enabled=True, keywords=load_keywords())

definition.export(format="jsonl", output_path="~/output.jsonl")
```

### Pattern 3: Multi-Stage Processing with Checkpoints

```python
definition = (
    Definition("Multi-Stage Review")
    .bibtex_import(batch_id="batch", imports=sources)
    .checkpoint(label="stage_1_import")
    
    .deduplication(enabled=True, methods=[...])
    .checkpoint(label="stage_2_dedup")
    
    .categorization(enabled=True)
    .checkpoint(label="stage_3_categorization")
    
    .export(format="jsonl", output_path="~/final.jsonl")
)

# Can resume from checkpoint if interrupted
```

### Pattern 4: Pipeline Factory with Defaults

```python
def create_review(
    name: str,
    sources: List[BibtexSource],
    dedup_methods=None,
    **kwargs
):
    definition = Definition(name, **kwargs)
    definition.bibtex_import(
        batch_id=f"batch_{name}",
        imports=sources
    )
    
    if dedup_methods is None:
        dedup_methods = [
            DeduplicationMethod(method="doi_exact", priority=1),
            DeduplicationMethod(method="title_fuzzy", priority=2, threshold=0.95),
        ]
    
    definition.deduplication(enabled=True, methods=dedup_methods)
    
    return definition.export(
        format="jsonl",
        output_path=f"~/review_{name}.jsonl"
    )
```

## Benefits Over YAML

| Feature | YAML | Python |
|---------|------|--------|
| Type Safety | ❌ | ✅ |
| IDE Autocomplete | ❌ | ✅ |
| Validation | Runtime | Compile-time |
| Refactoring | Risky | Safe |
| Conditional Logic | Hard | Easy |
| Code Reuse | Limited | Excellent |
| Debugging | Limited | Full |
| Syntax Errors | Late Detection | Early Detection |
| IDE Support | None | Full |

## Running Examples

### Basic Execution

```bash
# Run example script
python examples/01_simple_import.py

# With verbose output
python examples/02_full_pipeline.py --verbose

# Dry run (don't execute, just show steps)
python examples/03_conditional_pipeline.py --dry-run
```

### Integration with CLI Tools

You can still use YAML with the CLI tools if needed:

```bash
# Convert Python definition to YAML
python -c "
from examples.example1 import pipeline
pipeline.to_yaml('definition.yml')
"

# Run with CLI tool
paper-processor definition.yml
```

## Advanced Usage

### Custom Steps

Extend with custom processing steps by implementing the `Step` interface:

```python
from paper_scanner.definition import Step
from typing import Dict, Any

class CustomStep(Step):
    def __init__(self, param: str):
        self.param = param
    
    def get_name(self) -> str:
        return "custom"
    
    def get_description(self) -> str:
        return f"Custom step: {self.param}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.custom": {"param": self.param}
        }

# Use custom step
definition.add_step(CustomStep("my_value"))
```

### Parallel Execution

For processing multiple pipelines in parallel:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

pipelines = [pipeline1, pipeline2, pipeline3]

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(p.run): p.name for p in pipelines}
    
    for future in as_completed(futures):
        name = futures[future]
        try:
            results = future.result()
            print(f"{name}: ✓ Complete")
        except Exception as e:
            print(f"{name}: ✗ Failed - {e}")
```

## Troubleshooting

### Common Issues

**Q: ImportError: No module named 'paper_scanner.definition'**

A: The definition module needs to be available. Ensure you're running from the paper-scanner directory or have it installed:

```bash
cd /path/to/paper-scanner
python examples/01_simple_import.py
```

**Q: How do I debug step execution?**

A: Use `verbose=True` in `.run()`:

```python
results = definition.run(verbose=True)
```

**Q: Can I use both YAML and Python?**

A: Yes! Convert between them:

```python
# Python to YAML
definition.to_yaml("pipeline.yml")

# YAML to Python
from paper_scanner.definition import from_yaml
definition = from_yaml("pipeline.yml")
```

## See Also

- [Pythonic Definition API Documentation](../docs/PYTHONIC_DEFINITION_API.md)
- [Paper Scanner Main Documentation](../README.md)
- [Step Documentation](../docs/steps/)
