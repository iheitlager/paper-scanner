# API Reference

paper-scanner provides both a Python API and a command-line interface for working with paper data.

## Python API

The main entry points for programmatic use:

### Definition API (Recommended)
Fluent interface for building pipelines:

```python
from paper_scanner.definition import Definition

pipeline = (Definition("My Review")
    .bibtex_import("references.bib")
    .citations(backward={"citations": ["crossref"]})
    .export("bibtex", output="out.bib")
)

result = pipeline.run()
```

See [Step Reference](../steps/overview.md) for available methods.

### Core API
Low-level access to databases and models:

```python
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.models import Paper, Author

# Create database
db = PapersDatabase("papers.db")

# Create paper
paper = Paper(
    cite_key="Smith2023",
    title="Example Paper",
    authors=[Author(first_name="John", last_name="Smith")],
    year=2023
)

# Save to database
db.add(paper)

# Query
papers = db.find(lambda p: p.year == 2023)
```

## Command-Line Interface

See [Installation Guide](../guide/installation.md) for CLI setup.

### Basic Commands

```bash
# Run a pipeline
paper-processor definition.yml

# Validate workflow
paper-processor validate definition.yml

# Show database info
paper-processor info

# Clear database
paper-processor --init --force

# Resume from checkpoint
paper-processor definition.yml --checkpoint step_name

# Dry run (preview without changes)
paper-processor definition.yml --dry-run

# Enable verbose output
paper-processor definition.yml --verbose

# Enable debug output
paper-processor definition.yml --debug
```

## Modules

| Module | Purpose | Docs |
|--------|---------|------|
| `paper_scanner.core` | Core models and database | [Core](core.md) |
| `paper_scanner.steps` | Pipeline steps | [Steps](steps.md) |
| `paper_scanner.cli` | Command-line interface | [CLI](cli.md) |
| `paper_scanner.definition` | Fluent API | [Definition](definition.md) |
| `paper_scanner.tools` | External tools and fetchers | [Tools](tools.md) |

## Related Documentation

- [Step Reference](../steps/overview.md) - All available pipeline steps
- [Architecture Overview](../architecture/overview.md) - System design
- [Quick Start](../guide/quick-start.md) - Getting started tutorial
