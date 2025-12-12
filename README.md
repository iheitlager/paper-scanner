# paper-scanner

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)

AI-powered literature review tool for analyzing academic research papers using LLM assistance.

## Overview

`paper-scanner` is a pre-alpha tool designed to streamline the analysis of academic research papers through an LLM-assisted pipeline. It automates the extraction and structuring of key information from PDFs, including bibliographic metadata, research questions, methodology, findings, and key concepts. Features a PostgreSQL-backed web interface for browsing, analyzing, and organizing research papers.

## Features

- 🔍 **PDF Scanning**: Recursively scan directories for PDF files with metadata extraction
- 🤖 **LLM Integration**: Leverage Anthropic's Claude API for intelligent paper analysis with structured extraction
- 📊 **Structured Output**: JSONLines-based streaming pipeline for efficient batch processing
- 🔬 **Paper Analysis**: Automated extraction of summaries, research questions, methodology, results, and key concepts
- 📚 **Bibliographic Metadata**: Extract and store titles, authors, DOI, citations, and publication details
- 🌐 **Web Interface**: PostgreSQL-backed web browser for viewing, searching, and managing papers
  - Multi-tab interface: PDF viewer, Analysis, Details, and Tags
  - Author/year header with DOI links
  - Bibliographic information display
  - Paper analysis with consistent styling (white titles, blue definitions, grey text)
- 🏷️ **Tagging System**: Organize papers with colon-separated tags and centralized tag lookup
- 🔗 **Deeplinking**: Generate shareable links to specific papers (e.g., `?paper=SmithA2025`)
- 📖 **Reference Extraction**: Extract and organize paper citations with optional Claude-powered bibliography parsing
  - Opt-in `--extract-references` flag for reference extraction during processing
  - Structured reference metadata: authors, year, title, DOI, URL, publication source
  - PostgreSQL-backed reference storage and citation relationships
  - References tab in web interface for browsing extracted citations
- ⚡ **Rate Limiting**: Built-in automatic retry logic and request throttling for API limits

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/iheitlager/paper-scanner.git
cd paper-scanner

# Install with uv (recommended)
uv sync

# Or install with development dependencies
uv sync --all-groups
```

### Basic Usage - Pipeline YAML

```bash
# Create a definition file
cat > definition.yml << 'EOF'
project:
  name: "Literature Review"

pipeline:
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch_001"
      imports:
        - name: "Papers"
          file_path: "data/papers.bib"
          source_type: "scopus"

  - step: Remove duplicates
    builtin.deduplication:
      method: "all"

  - step: Export results
    builtin.export:
      format: "jsonl"
      output: "results.jsonl"
EOF

# Validate the definition
python -m paper_scanner.cli validate definition.yml

# Run the pipeline
python -m paper_scanner.cli run definition.yml
```

### Web Interface
# Start the web server (requires PostgreSQL database)
#### Web Interface Features

- **📄 PDF Tab**: View full paper PDFs with embedded viewer
- **🔬 Analysis Tab**: Read structured paper analysis (summary, research questions, methodology, results, concepts)
- **📋 Details Tab**: Browse bibliographic information (title, authors, DOI, citation, file metadata)
- **📖 References Tab**: View extracted references from the paper's bibliography with structured metadata
- **🏷️ Tags Tab**: Manage paper tags for organization and filtering
- **🔗 Share**: Generate deeplinks to share specific papers via URL

## Core Tools

The paper-scanner now uses a unified **YAML-based pipeline** approach. All processing is configured through definition files and executed via a single CLI command:

```bash
python -m paper_scanner.cli run definition.yml
```

No separate CLI tools are needed - everything is configured declaratively in your YAML definition file.

## YAML Pipeline Configuration

All processing is configured through YAML definition files. See the [docs/steps](docs/steps/) directory for detailed documentation on each available pipeline step.

**Quick Example:**

```yaml
project:
  name: "My Literature Review"

pipeline:
  # Import papers from BibTeX
  - step: Import papers
    builtin.bibtex_import:
      batch_id: "batch_001"
      imports:
        - name: "Scopus Results"
          file_path: "data/scopus.bib"
          source_type: "scopus"

  # Remove duplicates
  - step: Deduplication
    builtin.deduplication:
      method: "all"

  # Export results
  - step: Export
    builtin.export:
      format: "jsonl"
      output: "results.jsonl"
```

**Running the Pipeline:**

```bash
# Run with validation
python -m paper_scanner.cli run definition.yml --validate

# Run and save checkpoint
python -m paper_scanner.cli run definition.yml

# Resume from checkpoint
python -m paper_scanner.cli run definition.yml --checkpoint last
```

For complete documentation on all available steps, see [Step Documentation](docs/README.md).

## Database

The web interface requires a PostgreSQL database. Configure via environment variables:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/pdfdb"
export PDF_BASE_DIR="/path/to/pdf/files"
```

Database schema is automatically initialized on first run.

## Development

### Requirements

- Python 3.11+
- `uv` package manager
- Anthropic API key (for paper processing)
- PostgreSQL (for web interface)

### Setting Up Development Environment

```bash
# Install all dependencies including dev tools
uv sync --all-groups

# Run tests
make test

# Run linting
make lint

# Format code
make format

# Type checking
make type-check
```

### Available Make Targets

```bash
# Development & Code Quality
make help          # Show all available targets
make check         # Verify required tooling is installed
make version       # Show project version
make env           # Create and setup development virtual environment
make sync          # Sync dependencies
make lock          # Lock dependencies into uv.lock
make test          # Run tests with coverage
make lint          # Lint code with ruff
make format        # Format code with ruff
make type-check    # Run type checks with mypy
make clean         # Clean up artifacts and caches

# Docker Commands
make start         # Start Colima (Docker runtime)
make stop          # Stop Colima and cleanup
make docker-up     # Start services with Docker Compose
make docker-down   # Stop Docker containers
make docker-logs   # View Docker logs
make docker-again  # Rebuild from cache and restart
make docker-rebuild # Rebuild web container
make docker-fresh  # Fresh database initialization
make cleanup       # Clean up all Docker resources
```

## Project Structure

```
paper-scanner/
├── src/paper_scanner/
│   ├── core/
│   │   └── advanced_section_parser.py    # Academic paper parsing logic
│   ├── tools/
│   │   ├── file_scanner.py               # PDF discovery
│   │   ├── paper_details.py              # Bibliographic extraction
│   │   ├── file_processor.py             # LLM processing
│   │   ├── file_parser.py                # Result parsing
│   │   ├── file_merge.py                 # Data merging
│   │   ├── file_reader.py                # CSV export
│   │   └── file_timer.py                 # Rate limiting
│   └── web/
│       ├── server.py                     # Flask web server
│       ├── exceptions.py                 # Error handling
│       ├── http_handlers.py              # HTTP route handlers
│       ├── templates/
│       │   └── index.html                # Web UI
│       └── static/
│           ├── style.css                 # Styling
│           └── script.js                 # Client logic
├── tests/
│   └── unit/
│       └── test_advanced_section_parser.py
├── pyproject.toml                        # Project configuration
├── Makefile                              # Development tasks
└── README.md                             # This file
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required for processing)
- `DATABASE_URL`: PostgreSQL connection string (required for web interface, default: `postgresql://pdfuser:pdfpass@localhost:5432/pdfdb`)
- `PDF_BASE_DIR`: Base directory for PDF files (default: `/Users/iheitlager/wc/papers`)
- `PORT`: Web server port (default: `8080`)
- `ENV`: Environment (default: `local`, set to `docker` for container deployment)

### Custom Prompts

You can provide custom system prompts to the file-processor tool:

```bash
file-processor -i input.jsonl -o output.jsonl --custom_prompt custom_prompt.txt
```

## Deployment

### Docker

A `docker-compose.yml` and `Dockerfile` are provided for containerized deployment:

```bash
docker-compose up
```

This starts both the web server and PostgreSQL database.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a complete history of changes

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

Ilja Heitlager (iheitlager@schubergphilis.com)

## Contributing

Contributions are welcome! This project is in pre-alpha, so expect breaking changes.

## Roadmap

- [ ] Enhanced paper section detection
- [ ] Support for additional document formats
- [ ] Caching layer for API responses
- [x] Web UI for interactive analysis (completed in v0.3+)
- [ ] Export to additional formats (JSON Schema, RDF)
- [ ] Full-text search across papers
- [ ] Paper recommendation based on analysis

