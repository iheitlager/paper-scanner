# Pythonic Definition API - No YAML Required

A fully Pythonic, type-safe alternative to YAML-based step definitions using a fluent builder API.

## Overview

Instead of writing YAML like:

```yaml
steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "import_20241211"
      imports:
        - name: "Scopus"
          file_path: "data.bib"
          source_type: "scopus"

  - step: Export results
    builtin.export:
      format: "jsonl"
      output_path: "~/output.jsonl"
```

Write pure Python with full IDE support, type hints, and autocomplete:

```python
from paper_scanner.definition import Definition, BibtexImportConfig, ExportConfig

definition = (
    Definition("Supplier Digital Innovation Review")
    .bibtex_import(
        batch_id="import_20241211",
        imports=[
            BibtexImportConfig.scopus("Scopus Sample", "data/scopus_20.bib", 20),
        ]
    )
    .export(
        format="jsonl",
        output_path="~/output.jsonl"
    )
    .run()
)
```

## Core Architecture

### 1. Definition Class (Fluent Builder)

The `Definition` class provides a chainable API for building processing pipelines:

```python
from paper_scanner.definition import Definition

definition = Definition(
    name="My Research Review",
    description="Review on digital innovation",
    researcher="John Doe",
    institution="University"
)
```

**Attributes:**
- `name: str` - Project name
- `description: Optional[str]` - Project description
- `researcher: Optional[str]` - Researcher name
- `institution: Optional[str]` - Institution name
- `database: Optional[DatabaseConfig]` - Database connection config
- `steps: List[Step]` - Accumulated processing steps
- `project_metadata: Dict[str, Any]` - Additional metadata

### 2. Step Methods (Chainable)

Each step method returns `self` for chaining:

```python
definition = (
    Definition("My Project")
    .bibtex_import(...)    # Returns Definition
    .deduplication(...)    # Returns Definition
    .categorization(...)   # Returns Definition
    .export(...)          # Returns Definition
)
```

**Available Methods:**

```python
# Import steps
.bibtex_import(batch_id, imports)
.echo(message=None)

# Processing steps
.deduplication(enabled=True, methods=None)
.categorization(enabled=True, ...)
.keyword_screening(...)
.semantic_screening(...)

# Management steps
.checkpoint(label=None)
.summarize(summary=True, tabulate=None)
.export(format, output_path, ...)
.halt(message="")
```

### 3. Configuration Classes (Type-Safe)

Each step has a dedicated config dataclass:

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BibtexImportConfig:
    batch_id: str
    imports: List[BibtexSource]
    
    @staticmethod
    def scopus(name: str, file_path: str, expected_count: int):
        """Helper for Scopus imports"""
        return BibtexSource(
            name=name,
            file_path=file_path,
            source_type="scopus",
            expected_count=expected_count
        )
    
    @staticmethod
    def ieee(name: str, file_path: str, expected_count: int):
        """Helper for IEEE imports"""
        return BibtexSource(
            name=name,
            file_path=file_path,
            source_type="ieee_xplore",
            expected_count=expected_count
        )

@dataclass
class BibtexSource:
    name: str
    file_path: str
    source_type: str  # "scopus", "ieee_xplore", "web_of_science"
    expected_count: Optional[int] = None
```

### 4. Execution & Conversion

```python
definition = Definition("My Project").bibtex_import(...)

# Convert to YAML (for CLI/automation)
yaml_dict = definition.to_dict()

# Convert to YAML file
definition.to_yaml("definition.yml")

# Execute directly
results = definition.run(verbose=True, dry_run=False)

# Get step list for inspection
steps = definition.get_steps()
```

## Complete Examples

### Example 1: Simple Import + Export

```python
from paper_scanner.definition import Definition, ExportConfig

definition = (
    Definition(
        name="Quick Review",
        researcher="Alice"
    )
    .bibtex_import(
        batch_id="batch_001",
        imports=[
            BibtexSource.scopus("Scopus", "data/scopus.bib", 50),
            BibtexSource.ieee("IEEE", "data/ieee.bib", 30),
        ]
    )
    .export(
        format="jsonl",
        output_path="~/output.jsonl",
        overwrite=True
    )
)

# Run it
results = definition.run(verbose=True)
```

### Example 2: Full Pipeline with Deduplication

```python
from paper_scanner.definition import Definition
from paper_scanner.definition.steps import (
    DeduplicationConfig,
    DeduplicationMethod,
)

definition = (
    Definition(
        name="Comprehensive Review",
        researcher="Bob",
        institution="MIT"
    )
    .bibtex_import(
        batch_id="comprehensive_2024",
        imports=[
            BibtexSource.scopus("Scopus", "data/scopus_500.bib", 500),
            BibtexSource.ieee("IEEE", "data/ieee_300.bib", 300),
            BibtexSource.wos("Web of Science", "data/wos_200.bib", 200),
        ]
    )
    .echo(message="Imported all sources")
    .checkpoint(label="post_import")
    .deduplication(
        enabled=True,
        methods=[
            DeduplicationMethod(method="doi_exact", priority=1),
            DeduplicationMethod(
                method="title_author_fuzzy",
                priority=2,
                threshold=0.90
            ),
            DeduplicationMethod(
                method="title_fuzzy",
                priority=3,
                threshold=0.95
            ),
        ]
    )
    .echo(message="Deduplication complete")
    .checkpoint(label="post_dedup")
    .categorization(enabled=True)
    .checkpoint(label="post_categorization")
    .summarize(
        summary=True,
        tabulate=[
            {"field": "paper_type", "duplicates": False},
            {"field": "journal", "duplicates": False},
        ]
    )
    .export(
        format="jsonl",
        output_path="~/output_deduped.jsonl",
        duplicates=False,
        overwrite=True
    )
    .export(
        format="bibtex",
        output_path="~/output_duplicates.bib",
        duplicates="only",
        overwrite=True
    )
)

# Run with detailed output
results = definition.run(verbose=True, show_timings=True)
```

### Example 3: Multiple Batch Processing

```python
from paper_scanner.definition import Definition

# Reusable configuration
sources = [
    BibtexSource.scopus("Scopus 2024", "data/2024/scopus.bib"),
    BibtexSource.ieee("IEEE 2024", "data/2024/ieee.bib"),
]

for year in [2020, 2021, 2022, 2023, 2024]:
    definition = (
        Definition(
            name=f"Innovation Review {year}",
            researcher="Carol"
        )
        .bibtex_import(
            batch_id=f"batch_{year}",
            imports=[
                BibtexSource.scopus(f"Scopus {year}", f"data/{year}/scopus.bib"),
            ]
        )
        .deduplication(enabled=True)
        .export(
            format="jsonl",
            output_path=f"~/results_{year}.jsonl",
            overwrite=True
        )
    )
    
    results = definition.run()
    print(f"Processed {year}: {results['papers_processed']} papers")
```

### Example 4: Conditional Steps with Python Logic

```python
from paper_scanner.definition import Definition

definition = Definition("Conditional Pipeline", researcher="Dave")

# Add common steps
definition.bibtex_import(batch_id="batch_1", imports=[...])

# Conditionally add deduplication
if should_deduplicate:
    definition.deduplication(enabled=True, methods=[...])

# Conditionally add categorization
if run_categorization:
    definition.categorization(enabled=True)
    definition.checkpoint(label="post_cat")

# Always export
definition.export(
    format="jsonl",
    output_path="~/final.jsonl",
    overwrite=True
)

results = definition.run()
```

## Implementation Details

### Step Class Hierarchy

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class Step(ABC):
    """Base class for all steps"""
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert to YAML-compatible dictionary"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get step name (e.g., 'bibtex_import')"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description"""
        pass

class BibtexImportStep(Step):
    def __init__(self, config: BibtexImportConfig):
        self.config = config
    
    def get_name(self) -> str:
        return "bibtex_import"
    
    def get_description(self) -> str:
        return f"Import {len(self.config.imports)} BibTeX source(s)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to YAML-compatible format"""
        return {
            "step": self.get_description(),
            "builtin.bibtex_import": asdict(self.config)
        }
```

### Definition Execution Flow

```python
class Definition:
    def run(self, verbose=False, dry_run=False) -> ExecutionResult:
        """Execute all accumulated steps"""
        
        # Initialize database
        papers_db = PapersDatabase()
        
        # Execute each step
        for step in self.steps:
            step_dict = step.to_dict()
            result = StepExecutor.execute_step(
                step_dict,
                papers_db,
                verbose=verbose,
                dry_run=dry_run
            )
            
            # Track results
            yield result
        
        return ExecutionResult(...)
```

## Type Safety Benefits

```python
# ✅ IDE autocomplete and type checking
definition = Definition("Project")
definition.bibtex_import(
    batch_id="b1",
    imports=[
        BibtexSource.scopus("Name", "file.bib", 50)  # Type-safe!
    ]
)

# ❌ Catches errors at development time
definition.bibtex_import(
    batch_id="b1",
    imports=[
        BibtexSource.scopus("Name", "file.bib", "50")  # Type error!
    ]
)

# ✅ Refactoring is safe with IDE support
# Rename method -> automatically updates all calls

# ✅ Runtime validation
try:
    definition.run()
except ValidationError as e:
    print(f"Configuration error: {e}")
```

## Interoperability

### Convert Python to YAML

```python
definition = Definition("My Project").bibtex_import(...)

# Get YAML dict
yaml_dict = definition.to_dict()

# Save to file
definition.to_yaml("pipeline.yml")

# Use with YAML CLI
# paper-processor pipeline.yml
```

### Convert YAML to Python

```python
from paper_scanner.definition import from_yaml

definition = from_yaml("pipeline.yml")

# Continue building in Python
definition.export(format="jsonl", output_path="~/out.jsonl")
```

## Comparison Table

| Feature | YAML | Pythonic API |
|---------|------|--------------|
| Type Safety | ❌ No | ✅ Full |
| IDE Autocomplete | ❌ No | ✅ Yes |
| Refactoring | ❌ Risky | ✅ Safe |
| Syntax Validation | ❌ Runtime | ✅ Compile-time |
| Conditional Logic | ❌ Hard | ✅ Easy |
| Code Reuse | ⚠️ Limited | ✅ Excellent |
| Programmatic Generation | ⚠️ Messy | ✅ Clean |
| Human Readable | ✅ Yes | ✅ Yes |
| Debuggable | ⚠️ Limited | ✅ Excellent |
| Learning Curve | ⚠️ Medium | ✅ Low |

## Migration Guide

### Before (YAML):
```yaml
steps:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: import_001
      imports:
        - name: Scopus
          file_path: data.bib
          source_type: scopus
          expected_count: 100
```

### After (Python):
```python
definition = (
    Definition("My Project")
    .bibtex_import(
        batch_id="import_001",
        imports=[
            BibtexSource.scopus("Scopus", "data.bib", 100)
        ]
    )
)
```

## Advanced Usage

### Custom Step Extensions

```python
from paper_scanner.definition.steps import Step

class CustomStep(Step):
    def __init__(self, name: str, custom_param: str):
        self.name = name
        self.custom_param = custom_param
    
    def get_name(self) -> str:
        return "custom"
    
    def get_description(self) -> str:
        return f"Custom step: {self.name}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.get_description(),
            "builtin.custom": {
                "param": self.custom_param
            }
        }

# Use in Definition
definition = Definition("Project")
definition.add_step(CustomStep("My Custom", "value"))
```

### Factory Functions

```python
def create_standard_pipeline(project_name: str, sources: List[str]):
    """Standard pipeline factory"""
    definition = Definition(project_name)
    
    for source_file in sources:
        definition.bibtex_import(
            batch_id=f"batch_{source_file}",
            imports=[BibtexSource.scopus(source_file, source_file)]
        )
    
    return (
        definition
        .deduplication(enabled=True)
        .categorization(enabled=True)
        .export(format="jsonl", output_path="~/output.jsonl")
    )

# Use factory
pipeline = create_standard_pipeline("My Review", ["scopus.bib", "ieee.bib"])
results = pipeline.run()
```

## Summary

The Pythonic Definition API provides:

1. **Type Safety** - Compile-time error detection
2. **IDE Support** - Autocomplete and refactoring
3. **Readability** - Clear, expressive Python code
4. **Composability** - Easy to build reusable pipelines
5. **Debuggability** - Full Python debugging support
6. **Flexibility** - Conditional logic and dynamic step construction
7. **Interoperability** - Convert to/from YAML as needed

This approach leverages Python's strengths while maintaining YAML compatibility for legacy workflows.
