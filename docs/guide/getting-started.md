# Getting Started

Welcome to paper-scanner! This guide will help you get up and running with the paper-scanner literature review tool.

## What is paper-scanner?

paper-scanner is a Python tool that helps you analyze academic papers at scale:

- **Extract Information** - Uses Claude to analyze PDFs and extract structured data
- **Manage Citations** - Build and explore citation networks
- **Organize Papers** - Store and search papers in a PostgreSQL database
- **Process Pipelines** - Define reproducible data processing workflows

## Installation

See [Installation Guide](installation.md) for detailed setup instructions.

Quick start:
```bash
git clone https://github.com/your-org/paper-scanner.git
cd paper-scanner
uv sync --all-groups
```

## Your First Pipeline

See [Quick Start](quick-start.md) for a complete walkthrough.

## Key Concepts

### Papers
The core entity - represents a single academic paper with metadata:
- Title, authors, year
- DOI and URLs
- Abstract and keywords
- Citation relationships

### Pipelines
Workflows that process papers through multiple steps:
- Import (BibTeX, CSV, etc.)
- Analyze (extract citations, extract findings, etc.)
- Transform (deduplicate, patch, tag, etc.)
- Export (to various formats)

### Steps
Individual units of work in a pipeline - each step does one thing well:
- Can be chained together
- Support checkpointing for resumable execution
- Have configuration and runtime options

### Citation Graph
Network of papers and their relationships:
- **Backward Citations**: Papers cited by a paper (references)
- **Forward Citations**: Papers that cite a paper (cited by)

## Common Tasks

### Import Papers from BibTeX
```yaml
steps:
  - name: bibtex_import
    file: references.bib
    
  - name: export
    format: bibtex
    output: cleaned.bib
```

### Extract Citation Networks
```yaml
steps:
  - name: citations
    backward:
      citations: [crossref]
```

### Find and Remove Duplicates
```yaml
steps:
  - name: deduplication
    strategy: doi_title_year
```

## Next Steps

1. **[Installation](installation.md)** - Set up the environment
2. **[Quick Start](quick-start.md)** - Run your first pipeline
3. **[Architecture Overview](../architecture/overview.md)** - Understand the system
4. **[Step Reference](../steps/overview.md)** - All available steps
5. **[API Documentation](../api/core.md)** - Python API reference

## Getting Help

- 📖 [Full Documentation](https://paper-scanner.readthedocs.io)
- 🐛 [Report Issues](https://github.com/your-org/paper-scanner/issues)
- 💬 [Discussions](https://github.com/your-org/paper-scanner/discussions)
- 📝 [Architecture Decisions](../adr/index.md) - Why things are designed this way
