# paper-scanner

**paper-scanner** is a Python LLM-powered literature review tool for analyzing academic PDFs. It uses Claude API to extract structured information (metadata, research questions, findings) and organize papers via PostgreSQL backend with a web UI.

**Version:** 3.8.0 (pre-alpha)

!!! warning "Pre-alpha Notice"
    This project is in pre-alpha stage. Breaking changes may occur between minor versions. Feedback and contributions are welcome!

## Key Features

- 📄 **PDF Analysis** - Extract structured information from academic PDFs using Claude
- 🔗 **Citation Graphs** - Build forward and backward citation networks
- 🗄️ **PostgreSQL Backend** - Robust data persistence with indexed queries
- 🌐 **Web Interface** - Flask-based UI with PDF viewer and analysis tools
- 🔄 **Pipeline Architecture** - YAML-based or Pythonic fluent API for data processing
- ⚡ **Checkpointing** - Resume pipelines from specific steps

## Quick Navigation

- **[Getting Started](guide/getting-started.md)** - Installation and first steps
- **[Architecture Overview](architecture/overview.md)** - System design and components
- **[Step Documentation](steps/overview.md)** - Available pipeline steps
- **[API Reference](api/core.md)** - Python API documentation
- **[Architecture Decision Records](adr/index.md)** - Technical decisions and rationale

## Core Data Flow

```
PDF Input → Claude Analysis → Structured JSON → PostgreSQL DB → Web Interface
```

## Main Components

### Core
Located in `src/paper_scanner/core/`:
- **Database** - Paper and citation management
- **Models** - Data structures (Paper, Citation, Author, etc.)
- **DOI Handling** - DOI normalization and resolution
- **LLM Interactions** - Claude API integration

### Pipeline
Located in `src/paper_scanner/steps/`:
- **BaseStep** - Base class for all pipeline steps
- **BibtexImport** - Import from BibTeX files
- **Citations** - Extract and resolve citations
- **Export** - Export to various formats
- **Deduplication** - Identify duplicate papers
- Many more specialized steps

### Web Interface
Located in `src/paper_scanner/web/`:
- **Flask UI** - Web-based paper management
- **PDF Viewer** - Interactive PDF display
- **Analysis Views** - Paper analysis and tagging

## Running Pipelines

=== "YAML-based (Primary)"
    ```bash
    uv run paper-processor definition.yml --verbose
    ```

=== "Python API"
    ```python
    from paper_scanner.definition import Definition, BibtexSource
    
    pipeline = (Definition("Review")
        .bibtex_import(source="references.bib")
        .export(format="bibtex", output="cleaned.bib")
        .run())
    ```

## Development

```bash
# Setup
uv sync --all-groups

# Test
make test

# Lint & Format
make lint
make format

# Type checking
make type-check
```

## Project Status

- ✅ Core PDF analysis with Claude
- ✅ Database persistence
- ✅ Pipeline executor
- ✅ Citation extraction (backward & forward)
- 🚧 Web UI improvements
- 🔲 Advanced filtering and search
- 🔲 Collaboration features

## Documentation Structure

| Section | Purpose |
|---------|---------|
| [User Guide](guide/getting-started.md) | How to install and use paper-scanner |
| [Architecture](architecture/overview.md) | System design, components, data flow |
| [Steps](steps/overview.md) | Reference for all pipeline steps |
| [API Reference](api/core.md) | Python API documentation |
| [ADRs](adr/index.md) | Technical decisions and design rationale |
| [Contributing](contributing/setup.md) | Development guidelines |

## Community & Support

- 📚 [Read the Docs](https://paper-scanner.readthedocs.io)
- 🐛 [Issue Tracker](https://github.com/iheitlager/paper-scanner/issues)
- 💬 [Discussions](https://github.com/iheitlager/paper-scanner/discussions)

## License

MIT License - See LICENSE file for details.
